"""Vues espace connecté, API internes et webhooks — GoChange."""
import csv
import json
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from wallet.models import Beneficiary, Wallet

from . import services
from .forms import (
    BeneficiaireBanqueForm,
    BeneficiaireMomoForm,
    DepotForm,
    EchangeForm,
    RetraitForm,
)
from .models import (
    NGN,
    XOF,
    Deposit,
    ExchangeRate,
    ExchangeTransaction,
    WebhookLog,
    Withdrawal,
)
from .services import fedapay, limits, paydunya, paystack


def _email_required(request):
    if not request.user.email_verified:
        messages.warning(
            request,
            "Confirmez d'abord votre adresse e-mail pour accéder à cette opération.",
        )
        return True
    return False


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
@login_required
def dashboard(request):
    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    rate = ExchangeRate.current()
    lim = limits.limits_summary(request.user)

    recent = _recent_activity(request.user, limit=8)
    chart = _exchange_volume_chart(request.user, days=30)
    month_volume = sum(chart["values"])

    alerts = []
    if request.user.kyc.level < 2:
        alerts.append("Passez au niveau 2 pour porter vos limites à 500 000 FCFA/jour.")
    if not request.user.email_verified:
        alerts.append("Votre e-mail n'est pas encore confirmé.")

    return render(request, "app/dashboard.html", {
        "wallet": wallet,
        "rate": rate,
        "limits": lim,
        "recent": recent,
        "chart_json": json.dumps(chart),
        "month_volume": month_volume,
        "alerts": alerts,
        "active": "dashboard",
    })


def _recent_activity(user, limit=10):
    items = []
    for d in user.deposits.all()[:limit]:
        items.append({"type": "Dépôt", "amount": d.amount, "currency": d.currency,
                      "status": d.get_status_display(), "status_key": d.status, "date": d.created_at})
    for e in user.exchanges.all()[:limit]:
        items.append({"type": "Échange", "amount": e.amount_to, "currency": e.to_currency,
                      "status": "Effectué", "status_key": "completed", "date": e.created_at})
    for w in user.withdrawals.all()[:limit]:
        items.append({"type": "Retrait", "amount": w.amount, "currency": w.currency,
                      "status": w.get_status_display(), "status_key": w.status, "date": w.created_at})
    for t in user.transfers_sent.all()[:limit]:
        items.append({"type": "Envoi", "amount": t.amount, "currency": t.currency,
                      "status": "Envoyé", "status_key": "completed", "date": t.created_at})
    for t in user.transfers_received.all()[:limit]:
        items.append({"type": "Reçu", "amount": t.amount, "currency": t.currency,
                      "status": "Reçu", "status_key": "completed", "date": t.created_at})
    items.sort(key=lambda x: x["date"], reverse=True)
    return items[:limit]


def _exchange_volume_chart(user, days=30):
    rate = ExchangeRate.current()
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
    buckets = {(start + timedelta(days=i)).date().isoformat(): 0.0 for i in range(days)}
    for e in user.exchanges.filter(created_at__gte=start):
        key = timezone.localtime(e.created_at).date().isoformat()
        if key in buckets:
            if e.to_currency == XOF:
                xof = float(e.amount_to)
            elif rate:
                xof = float(rate.convert(e.amount_to, NGN))
            else:
                xof = 0.0
            buckets[key] += xof
    return {"labels": list(buckets.keys()), "values": [round(v, 2) for v in buckets.values()]}


# --------------------------------------------------------------------------- #
# Dépôt
# --------------------------------------------------------------------------- #
@login_required
def deposer(request):
    if _email_required(request):
        return redirect("exchange:dashboard")
    form = DepotForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        currency = form.cleaned_data["currency"]
        amount = form.cleaned_data["amount"]

        ok, msg, _ = limits.check_deposit_limit(request.user, amount, currency)
        if not ok:
            messages.error(request, msg)
            return render(request, "app/deposer.html", {"form": form, "active": "deposer"})

        if currency == XOF:
            provider = (Deposit.PROVIDER_FEDAPAY
                        if form.cleaned_data.get("xof_provider") == "fedapay"
                        else Deposit.PROVIDER_PAYDUNYA)
        else:
            provider = Deposit.PROVIDER_PAYSTACK
        deposit = Deposit.objects.create(
            user=request.user, currency=currency, amount=amount, provider=provider,
            operator=form.cleaned_data.get("operator", ""),
            reference=services.make_reference("DEP"),
        )
        try:
            if provider == Deposit.PROVIDER_FEDAPAY:
                url, token = fedapay.create_transaction(request, deposit)
                deposit.provider_token = token
            elif provider == Deposit.PROVIDER_PAYDUNYA:
                url, token = paydunya.create_invoice(request, deposit)
                deposit.provider_token = token
            else:
                url, ref, access = paystack.initialize_transaction(request, deposit)
                deposit.provider_token = access
            deposit.checkout_url = url
            deposit.save(update_fields=["provider_token", "checkout_url"])
        except RuntimeError as exc:
            deposit.status = Deposit.STATUS_FAILED
            deposit.save(update_fields=["status"])
            messages.error(request, str(exc))
            return render(request, "app/deposer.html", {"form": form, "active": "deposer"})

        return redirect(deposit.checkout_url)

    return render(request, "app/deposer.html", {"form": form, "active": "deposer"})


@login_required
def depot_retour(request, reference):
    """Page de retour après paiement. En simulation, confirme le dépôt."""
    deposit = get_object_or_404(Deposit, reference=reference, user=request.user)

    if request.GET.get("sim") == "1" and deposit.status == Deposit.STATUS_PENDING:
        _credit_deposit(deposit, source="simulation")
        messages.success(
            request,
            f"Dépôt confirmé (mode simulation) : votre solde {deposit.currency} a été crédité.",
        )
    elif deposit.status == Deposit.STATUS_COMPLETED:
        messages.success(request, "Dépôt déjà confirmé.")
    else:
        messages.info(
            request,
            "Paiement en cours de confirmation. Votre solde sera crédité dès réception de la confirmation.",
        )
    return redirect("exchange:dashboard")


def _credit_deposit(deposit, source=""):
    """Crédite le portefeuille de façon idempotente et atomique."""
    with transaction.atomic():
        dep = Deposit.objects.select_for_update().get(pk=deposit.pk)
        if dep.status == Deposit.STATUS_COMPLETED:
            return False
        wallet = Wallet.objects.select_for_update().get(user=dep.user)
        wallet.credit(dep.currency, dep.amount)
        wallet.save()
        dep.mark_completed()
        dep.save(update_fields=["status", "completed_at"])
    return True


# --------------------------------------------------------------------------- #
# Échange
# --------------------------------------------------------------------------- #
@login_required
def echanger(request):
    if _email_required(request):
        return redirect("exchange:dashboard")
    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    rate = ExchangeRate.current()
    form = EchangeForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        if not rate:
            messages.error(request, "Aucun taux actif. Réessayez plus tard.")
            return redirect("exchange:echanger")
        from_cur = form.cleaned_data["from_currency"]
        to_cur = NGN if from_cur == XOF else XOF
        amount = form.cleaned_data["amount"]

        try:
            tx = _execute_exchange(request.user, from_cur, to_cur, amount, rate)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("exchange:echanger")

        messages.success(
            request,
            f"Échange effectué : {tx.amount_from:,.0f} {tx.from_currency} → "
            f"{tx.amount_to:,.0f} {tx.to_currency} (frais {tx.fee_amount:,.0f} {tx.to_currency}).",
        )
        return redirect("exchange:dashboard")

    return render(request, "app/echanger.html", {
        "form": form, "wallet": wallet, "rate": rate, "active": "echanger",
    })


def _execute_exchange(user, from_cur, to_cur, amount, rate):
    """Échange atomique, taux figé. Lève ValueError si solde insuffisant."""
    gross = rate.convert(amount, from_cur)  # avant frais, en to_cur
    fee = (gross * rate.fee_percent / Decimal("100")).quantize(Decimal("0.01"))
    net = gross - fee
    rate_used = rate.xof_per_ngn if from_cur == NGN else rate.ngn_per_xof

    with transaction.atomic():
        wallet = Wallet.objects.select_for_update().get(user=user)
        if wallet.balance(from_cur) < amount:
            raise ValueError("Solde insuffisant pour cet échange.")
        wallet.debit(from_cur, amount)
        wallet.credit(to_cur, net)
        wallet.save()
        tx = ExchangeTransaction.objects.create(
            user=user, from_currency=from_cur, to_currency=to_cur,
            amount_from=amount, rate_used=rate_used,
            fee_percent=rate.fee_percent, fee_amount=fee, amount_to=net,
            reference=services.make_reference("ECH"),
        )
    return tx


# --------------------------------------------------------------------------- #
# Retrait
# --------------------------------------------------------------------------- #
@login_required
def retirer(request):
    if _email_required(request):
        return redirect("exchange:dashboard")
    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    form = RetraitForm(request.POST or None, user=request.user)

    if request.method == "POST" and form.is_valid():
        ben = form.cleaned_data["beneficiary"]
        amount = form.cleaned_data["amount"]
        currency = ben.currency

        if not request.POST.get("confirm_beneficiary"):
            messages.error(request, "Veuillez confirmer le bénéficiaire avant de valider.")
            return render(request, "app/retirer.html",
                          {"form": form, "wallet": wallet, "active": "retirer"})

        # Confirmation par code PIN de transaction
        if request.user.has_pin:
            if not request.user.check_pin(request.POST.get("pin", "")):
                messages.error(request, "Code PIN incorrect.")
                return render(request, "app/retirer.html",
                              {"form": form, "wallet": wallet, "active": "retirer"})
        else:
            messages.warning(request, "Définissez d'abord un code PIN de transaction dans vos paramètres.")
            return redirect("accounts:parametres")

        ok, msg, _ = limits.check_withdraw_limit(request.user, amount, currency)
        if not ok:
            messages.error(request, msg)
            return render(request, "app/retirer.html",
                          {"form": form, "wallet": wallet, "active": "retirer"})

        try:
            wd = _create_withdrawal(request.user, ben, amount, currency)
        except ValueError as exc:
            messages.error(request, str(exc))
            return render(request, "app/retirer.html",
                          {"form": form, "wallet": wallet, "active": "retirer"})

        messages.success(
            request,
            f"Demande de retrait enregistrée ({wd.reference}). "
            "Elle est en cours de traitement, vous serez notifié dès le paiement.",
        )
        return redirect("exchange:dashboard")

    if request.user.beneficiaries.count() == 0:
        messages.info(request, "Ajoutez d'abord un bénéficiaire pour retirer.")
        return redirect("exchange:beneficiaires")

    return render(request, "app/retirer.html",
                  {"form": form, "wallet": wallet, "active": "retirer"})


def _create_withdrawal(user, ben, amount, currency):
    """Débite le solde et crée le retrait (statut en attente d'approbation)."""
    with transaction.atomic():
        wallet = Wallet.objects.select_for_update().get(user=user)
        if wallet.balance(currency) < amount:
            raise ValueError("Solde insuffisant pour ce retrait.")
        wallet.debit(currency, amount)
        wallet.save()
        wd = Withdrawal.objects.create(
            user=user, currency=currency, amount=amount, beneficiary=ben,
            operator=ben.operator, phone=ben.phone,
            bank_code=ben.bank_code, bank_name=ben.bank_name,
            account_number=ben.account_number, account_name=ben.account_name,
            reference=services.make_reference("RET"),
        )
    return wd


# --------------------------------------------------------------------------- #
# Transfert interne (compte à compte GoChange)
# --------------------------------------------------------------------------- #
@login_required
def transferer(request):
    from django.contrib.auth import get_user_model
    from .forms import TransfertInterneForm
    from .models import InternalTransfer

    User = get_user_model()
    if _email_required(request):
        return redirect("exchange:dashboard")
    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    form = TransfertInterneForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        ident = form.cleaned_data["recipient"]
        currency = form.cleaned_data["currency"]
        amount = form.cleaned_data["amount"]
        note = form.cleaned_data["note"]

        # Recherche du destinataire par code unique ou téléphone
        recipient = (User.objects.filter(account_code__iexact=ident).first()
                     or User.objects.filter(phone=ident).exclude(phone="").first())
        if not recipient:
            messages.error(request, "Aucun compte GoChange trouvé pour ce code ou ce numéro.")
        elif recipient == request.user:
            messages.error(request, "Vous ne pouvez pas vous transférer à vous-même.")
        elif request.user.has_pin and not request.user.check_pin(request.POST.get("pin", "")):
            messages.error(request, "Code PIN incorrect.")
        elif not request.user.has_pin:
            messages.warning(request, "Définissez d'abord un code PIN dans vos paramètres.")
            return redirect("accounts:parametres")
        else:
            try:
                tx = _execute_internal_transfer(request.user, recipient, currency, amount, note)
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(
                    request,
                    f"Transfert de {tx.amount:,.0f} {tx.currency} envoyé à "
                    f"{recipient.display_name} ({recipient.account_code}).",
                )
                return redirect("exchange:dashboard")

    return render(request, "app/transferer.html", {
        "form": form, "wallet": wallet, "active": "transferer",
    })


def _execute_internal_transfer(sender, recipient, currency, amount, note):
    from .models import InternalTransfer

    with transaction.atomic():
        sw = Wallet.objects.select_for_update().get(user=sender)
        rw = Wallet.objects.select_for_update().get(user=recipient)
        if sw.balance(currency) < amount:
            raise ValueError("Solde insuffisant pour ce transfert.")
        sw.debit(currency, amount); sw.save()
        rw.credit(currency, amount); rw.save()
        tx = InternalTransfer.objects.create(
            sender=sender, recipient=recipient, currency=currency,
            amount=amount, note=note, reference=services.make_reference("TRF"),
        )
    return tx


# --------------------------------------------------------------------------- #
# Transactions
# --------------------------------------------------------------------------- #
@login_required
def transactions(request):
    type_filter = request.GET.get("type", "")
    rows = _recent_activity(request.user, limit=500)
    if type_filter in {"Dépôt", "Échange", "Retrait"}:
        rows = [r for r in rows if r["type"] == type_filter]
    return render(request, "app/transactions.html", {
        "rows": rows, "type_filter": type_filter, "active": "transactions",
    })


@login_required
def transactions_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="transactions-gochange.csv"'
    writer = csv.writer(response)
    writer.writerow(["Date", "Type", "Montant", "Devise", "Statut"])
    for r in _recent_activity(request.user, limit=1000):
        writer.writerow([
            timezone.localtime(r["date"]).strftime("%Y-%m-%d %H:%M"),
            r["type"], f"{r['amount']:.2f}", r["currency"], r["status"],
        ])
    return response


# --------------------------------------------------------------------------- #
# Bénéficiaires
# --------------------------------------------------------------------------- #
@login_required
def beneficiaires(request):
    momo_form = BeneficiaireMomoForm(prefix="momo")
    bank_form = BeneficiaireBanqueForm(prefix="bank")

    if request.method == "POST":
        kind = request.POST.get("kind")
        if kind == "momo":
            momo_form = BeneficiaireMomoForm(request.POST, prefix="momo")
            if momo_form.is_valid():
                momo_form.save(request.user)
                messages.success(request, "Bénéficiaire Mobile Money ajouté.")
                return redirect("exchange:beneficiaires")
        elif kind == "bank":
            bank_form = BeneficiaireBanqueForm(request.POST, prefix="bank")
            if bank_form.is_valid():
                bank_form.save(request.user)
                messages.success(request, "Compte bancaire ajouté.")
                return redirect("exchange:beneficiaires")

    return render(request, "app/beneficiaires.html", {
        "beneficiaires": request.user.beneficiaries.all(),
        "momo_form": momo_form, "bank_form": bank_form,
        "banks": paystack.list_banks(), "active": "beneficiaires",
    })


@login_required
@require_POST
def beneficiaire_supprimer(request, pk):
    ben = get_object_or_404(Beneficiary, pk=pk, user=request.user)
    ben.delete()
    messages.info(request, "Bénéficiaire supprimé.")
    return redirect("exchange:beneficiaires")


# --------------------------------------------------------------------------- #
# API internes (JSON) — la clé Paystack reste côté serveur
# --------------------------------------------------------------------------- #
@login_required
def api_banques(request):
    return JsonResponse({"banks": paystack.list_banks()})


@login_required
def api_resoudre_compte(request):
    account_number = request.GET.get("account_number", "").strip()
    bank_code = request.GET.get("bank_code", "").strip()
    if not account_number or not bank_code:
        return JsonResponse({"ok": False, "message": "Paramètres manquants."}, status=400)
    ok, name, message = paystack.resolve_account(account_number, bank_code)
    return JsonResponse({"ok": ok, "account_name": name, "message": message})


# --------------------------------------------------------------------------- #
# Webhooks
# --------------------------------------------------------------------------- #
@csrf_exempt
@require_POST
def webhook_paydunya(request):
    token, status, reference = paydunya.parse_ipn(request.POST)
    log = WebhookLog.objects.create(
        provider="paydunya", event=status, reference=reference or token,
        signature_valid=True, payload=dict(request.POST),
    )
    if status == "completed":
        dep = Deposit.objects.filter(
            provider_token=token, status=Deposit.STATUS_PENDING
        ).first() or Deposit.objects.filter(
            reference=reference, status=Deposit.STATUS_PENDING
        ).first()
        if dep:
            _credit_deposit(dep, source="paydunya-ipn")
            log.processed = True
            log.save(update_fields=["processed"])
    return HttpResponse("OK")


@csrf_exempt
@require_POST
def webhook_paystack(request):
    raw = request.body
    signature = request.headers.get("x-paystack-signature", "")
    valid = paystack.verify_signature(raw, signature)

    try:
        payload = json.loads(raw.decode() or "{}")
    except json.JSONDecodeError:
        payload = {}

    event = payload.get("event", "")
    data = payload.get("data", {})
    reference = data.get("reference", "")
    log = WebhookLog.objects.create(
        provider="paystack", event=event, reference=reference,
        signature_valid=valid, payload=payload,
    )
    if not valid:
        return HttpResponse(status=400)

    if event == "charge.success":
        dep = Deposit.objects.filter(reference=reference, status=Deposit.STATUS_PENDING).first()
        if dep:
            ok, _ = paystack.verify_transaction(reference)
            if ok:
                _credit_deposit(dep, source="paystack-webhook")
                log.processed = True
                log.save(update_fields=["processed"])
    elif event in {"transfer.success", "transfer.failed", "transfer.reversed"}:
        wd = Withdrawal.objects.filter(reference=reference).first()
        if wd:
            if event == "transfer.success":
                wd.status = Withdrawal.STATUS_COMPLETED
            else:
                wd.status = Withdrawal.STATUS_FAILED
                _refund_withdrawal(wd)
            wd.processed_at = timezone.now()
            wd.save(update_fields=["status", "processed_at"])
            log.processed = True
            log.save(update_fields=["processed"])
    return HttpResponse("OK")


def _refund_withdrawal(withdrawal):
    """Recrédite le solde si un retrait échoue."""
    with transaction.atomic():
        wallet = Wallet.objects.select_for_update().get(user=withdrawal.user)
        wallet.credit(withdrawal.currency, withdrawal.amount)
        wallet.save()
