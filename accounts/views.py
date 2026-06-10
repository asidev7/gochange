"""Vues comptes, authentification, profil et KYC — GoChange."""
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from . import emails
from .forms import (
    ChangerMotDePasseForm,
    ConnexionForm,
    EmailOnlyForm,
    InscriptionForm,
    KYCUpgradeForm,
    NouveauMotDePasseForm,
    ParametresForm,
    PinForm,
    ProfilForm,
)
from .models import CustomUser, EmailVerificationToken, KYCDocument, KYCProfile


# --------------------------------------------------------------------------- #
# Inscription / connexion
# --------------------------------------------------------------------------- #
def inscription(request):
    if request.user.is_authenticated:
        return redirect("exchange:dashboard")
    form = InscriptionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        # L1 = email + téléphone (vérification email envoyée tout de suite)
        emails.send_verification_email(request, user)
        messages.success(
            request,
            "Votre compte est créé. Vérifiez votre boîte mail pour confirmer votre adresse.",
        )
        login(request, user)
        return redirect("accounts:renvoyer_verification")
    return render(request, "account/inscription.html", {"form": form})


def connexion(request):
    if request.user.is_authenticated:
        return redirect("exchange:dashboard")
    form = ConnexionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        from django.contrib.auth import authenticate

        user = authenticate(
            request,
            username=form.cleaned_data["email"],
            password=form.cleaned_data["password"],
        )
        if user is None:
            messages.error(request, "E-mail ou mot de passe incorrect.")
        else:
            login(request, user)
            messages.success(request, f"Bienvenue, {user.display_name}.")
            return redirect(request.GET.get("next") or "exchange:dashboard")
    return render(request, "account/connexion.html", {"form": form})


@require_http_methods(["POST", "GET"])
def deconnexion(request):
    logout(request)
    messages.info(request, "Vous êtes déconnecté.")
    return redirect("core:landing")


# --------------------------------------------------------------------------- #
# Vérification e-mail
# --------------------------------------------------------------------------- #
def verifier_email(request, token):
    obj = EmailVerificationToken.objects.filter(
        token=token, purpose=EmailVerificationToken.PURPOSE_VERIFY
    ).select_related("user").first()
    if not obj or not obj.is_valid():
        messages.error(request, "Ce lien de vérification est invalide ou expiré.")
        return render(request, "account/verif_email.html", {"ok": False})
    user = obj.user
    user.email_verified = True
    user.phone_verified = True  # L1 automatique
    user.save(update_fields=["email_verified", "phone_verified"])
    obj.used = True
    obj.save(update_fields=["used"])
    messages.success(request, "Adresse e-mail confirmée. Votre compte est au niveau 1.")
    return render(request, "account/verif_email.html", {"ok": True})


@login_required
def renvoyer_verification(request):
    if request.user.email_verified:
        return redirect("exchange:dashboard")
    if request.method == "POST":
        emails.send_verification_email(request, request.user)
        messages.success(request, "E-mail de vérification renvoyé.")
    return render(request, "account/verif_email.html", {"ok": None, "pending": True})


# --------------------------------------------------------------------------- #
# Mot de passe oublié
# --------------------------------------------------------------------------- #
def mot_de_passe_oublie(request):
    form = EmailOnlyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = CustomUser.objects.filter(email__iexact=form.cleaned_data["email"]).first()
        if user:
            emails.send_password_reset_email(request, user)
        # On répond toujours pareil (anti-énumération)
        messages.success(
            request,
            "Si un compte existe pour cette adresse, un e-mail de réinitialisation vient d'être envoyé.",
        )
        return redirect("accounts:connexion")
    return render(request, "account/mot_de_passe_oublie.html", {"form": form})


def reinitialiser_mot_de_passe(request, token):
    obj = EmailVerificationToken.objects.filter(
        token=token, purpose=EmailVerificationToken.PURPOSE_RESET
    ).select_related("user").first()
    if not obj or not obj.is_valid():
        messages.error(request, "Ce lien de réinitialisation est invalide ou expiré.")
        return redirect("accounts:mot_de_passe_oublie")
    form = NouveauMotDePasseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = obj.user
        user.set_password(form.cleaned_data["password1"])
        user.save()
        obj.used = True
        obj.save(update_fields=["used"])
        messages.success(request, "Mot de passe modifié. Vous pouvez vous connecter.")
        return redirect("accounts:connexion")
    return render(request, "account/reinitialiser.html", {"form": form})


# --------------------------------------------------------------------------- #
# Profil
# --------------------------------------------------------------------------- #
@login_required
def profil(request):
    form = ProfilForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profil mis à jour.")
        return redirect("accounts:profil")
    kyc = request.user.kyc
    from accounts.models import DailyLimit

    limits = {d.level: d for d in DailyLimit.objects.all()}
    return render(
        request,
        "app/profil.html",
        {"form": form, "kyc": kyc, "limits": limits, "active": "compte"},
    )


@login_required
def changer_mot_de_passe(request):
    form = ChangerMotDePasseForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        request.user.set_password(form.cleaned_data["new_password1"])
        request.user.save()
        update_session_auth_hash(request, request.user)
        messages.success(request, "Mot de passe modifié.")
        return redirect("accounts:profil")
    return render(request, "app/changer_mot_de_passe.html", {"form": form, "active": "compte"})


@login_required
def kyc_upgrade(request):
    kyc = request.user.kyc
    target_level = min(kyc.level + 1, 3)
    if not kyc.can_upgrade:
        messages.info(request, "Aucune mise à niveau disponible pour le moment.")
        return redirect("accounts:profil")

    form = KYCUpgradeForm(
        request.POST or None, request.FILES or None, target_level=target_level
    )
    if request.method == "POST" and form.is_valid():
        kyc.full_name = form.cleaned_data["full_name"]
        kyc.pending_level = target_level
        kyc.status = KYCProfile.STATUS_PENDING
        kyc.save()

        files = {
            KYCDocument.TYPE_ID: form.cleaned_data.get("id_document"),
            KYCDocument.TYPE_SELFIE: form.cleaned_data.get("selfie"),
            KYCDocument.TYPE_ADDRESS: form.cleaned_data.get("address_document"),
        }
        for doc_type, f in files.items():
            if f:
                KYCDocument.objects.create(
                    profile=kyc, doc_type=doc_type, target_level=target_level, file=f
                )
        messages.success(
            request,
            "Documents envoyés. Notre équipe les vérifie sous 24 h ouvrées. "
            "Vous recevrez un e-mail dès la décision.",
        )
        return redirect("accounts:profil")
    return render(
        request,
        "app/kyc.html",
        {"form": form, "kyc": kyc, "target_level": target_level, "active": "compte"},
    )


# --------------------------------------------------------------------------- #
# Paramètres
# --------------------------------------------------------------------------- #
@login_required
def parametres(request):
    form = ParametresForm(instance=request.user)
    pin_form = PinForm()
    action = request.POST.get("action") if request.method == "POST" else None

    if action == "prefs":
        form = ParametresForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Préférences enregistrées.")
            return redirect("accounts:parametres")
    elif action == "pin":
        pin_form = PinForm(request.POST)
        if pin_form.is_valid():
            request.user.set_pin(pin_form.cleaned_data["pin1"])
            request.user.save(update_fields=["pin_hash"])
            messages.success(request, "Votre code PIN de transaction est enregistré.")
            return redirect("accounts:parametres")

    return render(request, "app/parametres.html", {
        "form": form, "pin_form": pin_form, "active": "compte",
    })


@login_required
@require_http_methods(["POST"])
def supprimer_compte(request):
    user = request.user
    wallet = getattr(user, "wallet", None)
    if wallet and (wallet.balance_ngn > 0 or wallet.balance_xof > 0):
        messages.error(
            request,
            "Votre portefeuille n'est pas vide. Retirez vos fonds avant de supprimer le compte.",
        )
        return redirect("accounts:parametres")
    logout(request)
    user.delete()
    messages.info(request, "Votre compte a été supprimé. À bientôt.")
    return redirect("core:landing")
