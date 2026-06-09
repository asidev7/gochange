"""Intégration Paystack — paiements NGN (carte / virement / banques nigérianes).

La clé secrète n'est JAMAIS exposée au frontend : la résolution de compte
(`bank/resolve`) passe par un endpoint Django proxy.
En l'absence de clé (settings.PAYMENTS_SIMULATION), les appels sont simulés.
Documentation : https://paystack.com/docs/api/
"""
import hashlib
import hmac
import logging

import requests
from django.conf import settings
from django.urls import reverse

logger = logging.getLogger("gochange.payments")

BASE = "https://api.paystack.co"

# Liste de secours (banques NGN courantes) pour le mode simulation / hors-ligne.
FALLBACK_BANKS = [
    {"name": "GTBank", "code": "058"},
    {"name": "Access Bank", "code": "044"},
    {"name": "Zenith Bank", "code": "057"},
    {"name": "United Bank for Africa (UBA)", "code": "033"},
    {"name": "First Bank of Nigeria", "code": "011"},
    {"name": "Opay", "code": "999992"},
    {"name": "PalmPay", "code": "999991"},
    {"name": "Kuda Bank", "code": "50211"},
]


def _headers():
    return {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }


def initialize_transaction(request, deposit):
    """Initialise une transaction (montant en kobo). Retourne (checkout_url, reference, access_code)."""
    callback_url = request.build_absolute_uri(
        reverse("exchange:depot_retour", args=[deposit.reference])
    )
    if settings.PAYMENTS_SIMULATION:
        logger.info("[SIMULATION] Transaction Paystack %s", deposit.reference)
        return callback_url + "?sim=1", deposit.reference, f"SIM-{deposit.reference}"

    payload = {
        "email": deposit.user.email,
        "amount": int(deposit.amount * 100),  # kobo
        "reference": deposit.reference,
        "currency": "NGN",
        "callback_url": callback_url,
    }
    try:
        resp = requests.post(
            f"{BASE}/transaction/initialize",
            json=payload, headers=_headers(), timeout=20,
        )
        data = resp.json()
        if data.get("status"):
            d = data["data"]
            return d["authorization_url"], d["reference"], d["access_code"]
        raise RuntimeError(data.get("message", "Erreur Paystack"))
    except requests.RequestException as exc:
        logger.error("Paystack initialize indisponible : %s", exc)
        raise RuntimeError("Service Paystack momentanément indisponible.")


def verify_transaction(reference):
    """Vérifie une transaction. Retourne (is_success, amount_naira)."""
    if settings.PAYMENTS_SIMULATION:
        return True, None
    try:
        resp = requests.get(
            f"{BASE}/transaction/verify/{reference}",
            headers=_headers(), timeout=20,
        )
        data = resp.json()
        if data.get("status") and data["data"].get("status") == "success":
            return True, data["data"]["amount"] / 100
        return False, None
    except requests.RequestException as exc:
        logger.error("Paystack verify indisponible : %s", exc)
        return False, None


def list_banks():
    """Liste des banques NGN. Bascule sur FALLBACK_BANKS si indisponible."""
    if settings.PAYMENTS_SIMULATION:
        return FALLBACK_BANKS
    try:
        resp = requests.get(
            f"{BASE}/bank", params={"currency": "NGN"}, headers=_headers(), timeout=20,
        )
        data = resp.json()
        if data.get("status"):
            return [{"name": b["name"], "code": b["code"]} for b in data["data"]]
    except requests.RequestException as exc:
        logger.error("Paystack bank list indisponible : %s", exc)
    return FALLBACK_BANKS


def resolve_account(account_number, bank_code):
    """Résolution du nom du titulaire. Retourne (ok, account_name, message).

    En simulation, renvoie un nom déterministe pour démontrer le flux de confirmation.
    """
    if settings.PAYMENTS_SIMULATION:
        if len(account_number) == 10 and account_number.isdigit():
            seed = int(account_number[-2:])
            noms = ["ADEBAYO O.", "CHINWE E.", "IBRAHIM M.", "FUNKE A.", "EMEKA N.", "YAKUBU S."]
            return True, f"{noms[seed % len(noms)]} (compte test)", ""
        return False, "", "Numéro de compte invalide (10 chiffres attendus)."

    try:
        resp = requests.get(
            f"{BASE}/bank/resolve",
            params={"account_number": account_number, "bank_code": bank_code},
            headers=_headers(), timeout=20,
        )
        data = resp.json()
        if data.get("status"):
            return True, data["data"]["account_name"], ""
        return False, "", data.get("message", "Compte introuvable.")
    except requests.RequestException as exc:
        logger.error("Paystack resolve indisponible : %s", exc)
        return False, "", "Service de vérification indisponible."


def create_transfer(withdrawal):
    """Crée un destinataire puis lance le virement. Retourne (ok, provider_ref, message)."""
    if settings.PAYMENTS_SIMULATION:
        logger.info("[SIMULATION] Virement Paystack %s", withdrawal.reference)
        return True, f"SIM-TRF-{withdrawal.reference}", "Virement simulé."

    try:
        # 1. transferrecipient
        rcp = requests.post(
            f"{BASE}/transferrecipient",
            json={
                "type": "nuban",
                "name": withdrawal.account_name,
                "account_number": withdrawal.account_number,
                "bank_code": withdrawal.bank_code,
                "currency": "NGN",
            },
            headers=_headers(), timeout=20,
        ).json()
        if not rcp.get("status"):
            return False, "", rcp.get("message", "Destinataire refusé.")
        recipient_code = rcp["data"]["recipient_code"]

        # 2. transfer
        trf = requests.post(
            f"{BASE}/transfer",
            json={
                "source": "balance",
                "amount": int(withdrawal.amount * 100),
                "recipient": recipient_code,
                "reference": withdrawal.reference,
                "reason": "Retrait GoChange",
            },
            headers=_headers(), timeout=25,
        ).json()
        if trf.get("status"):
            return True, trf["data"].get("transfer_code", ""), ""
        return False, "", trf.get("message", "Virement refusé.")
    except requests.RequestException as exc:
        logger.error("Paystack transfer indisponible : %s", exc)
        return False, "", "Service de virement indisponible."


def verify_signature(raw_body, signature):
    """Vérifie la signature HMAC SHA512 d'un webhook Paystack."""
    if settings.PAYMENTS_SIMULATION or not settings.PAYSTACK_SECRET_KEY:
        return True  # pas de clé => on accepte en mode démo
    computed = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode(), raw_body, hashlib.sha512
    ).hexdigest()
    return hmac.compare_digest(computed, signature or "")
