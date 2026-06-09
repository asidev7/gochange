"""Intégration PayDunya — paiements XOF (Mobile Money Bénin).

En l'absence de clés (settings.PAYMENTS_SIMULATION), tous les appels sont
simulés : aucune requête réseau, et le dépôt est confirmable via la vue de retour.
Documentation : https://paydunya.com/developers
"""
import logging

import requests
from django.conf import settings
from django.urls import reverse

logger = logging.getLogger("gochange.payments")

BASE_TEST = "https://app.paydunya.com/sandbox-api/v1"
BASE_LIVE = "https://app.paydunya.com/api/v1"


def _base_url():
    return BASE_TEST if settings.PAYDUNYA_MODE != "live" else BASE_LIVE


def _headers():
    return {
        "Content-Type": "application/json",
        "PAYDUNYA-MASTER-KEY": settings.PAYDUNYA_MASTER_KEY,
        "PAYDUNYA-PRIVATE-KEY": settings.PAYDUNYA_PRIVATE_KEY,
        "PAYDUNYA-PUBLIC-KEY": settings.PAYDUNYA_PUBLIC_KEY,
        "PAYDUNYA-TOKEN": settings.PAYDUNYA_TOKEN,
    }


def create_invoice(request, deposit):
    """Crée une facture PayDunya et retourne (checkout_url, token).

    En mode simulation, renvoie l'URL de retour interne pour confirmer le dépôt.
    """
    callback_url = request.build_absolute_uri(
        reverse("exchange:webhook_paydunya")
    )
    return_url = request.build_absolute_uri(
        reverse("exchange:depot_retour", args=[deposit.reference])
    )

    if settings.PAYMENTS_SIMULATION:
        logger.info("[SIMULATION] Facture PayDunya pour %s", deposit.reference)
        deposit.provider_token = f"SIM-{deposit.reference}"
        return return_url + "?sim=1", deposit.provider_token

    payload = {
        "invoice": {
            "total_amount": float(deposit.amount),
            "description": f"Dépôt GoChange {deposit.reference}",
        },
        "store": {"name": "GoChange"},
        "custom_data": {"reference": deposit.reference, "operator": deposit.operator},
        "actions": {
            "cancel_url": return_url,
            "return_url": return_url,
            "callback_url": callback_url,
        },
    }
    try:
        resp = requests.post(
            f"{_base_url()}/checkout-invoice/create",
            json=payload, headers=_headers(), timeout=20,
        )
        data = resp.json()
        logger.info("PayDunya create-invoice %s -> %s", deposit.reference, data.get("response_code"))
        if str(data.get("response_code")) == "00":
            return data.get("response_text"), data.get("token")
        raise RuntimeError(data.get("response_text", "Erreur PayDunya"))
    except requests.RequestException as exc:
        logger.error("PayDunya indisponible : %s", exc)
        raise RuntimeError("Service PayDunya momentanément indisponible.")


def confirm_invoice(token):
    """Vérifie le statut d'une facture. Retourne (is_completed, custom_data)."""
    if settings.PAYMENTS_SIMULATION:
        return True, {}
    try:
        resp = requests.get(
            f"{_base_url()}/checkout-invoice/confirm/{token}",
            headers=_headers(), timeout=20,
        )
        data = resp.json()
        completed = data.get("status") == "completed"
        return completed, data.get("custom_data", {})
    except requests.RequestException as exc:
        logger.error("PayDunya confirm indisponible : %s", exc)
        return False, {}


def disburse(withdrawal):
    """Décaissement Mobile Money (retrait XOF). Retourne (ok, provider_ref, message)."""
    if settings.PAYMENTS_SIMULATION:
        logger.info("[SIMULATION] Décaissement PayDunya %s", withdrawal.reference)
        return True, f"SIM-DISB-{withdrawal.reference}", "Décaissement simulé."

    payload = {
        "account_alias": withdrawal.phone,
        "amount": float(withdrawal.amount),
        "withdraw_mode": withdrawal.operator,  # mtn / moov / celtiis (selon compte)
    }
    try:
        resp = requests.post(
            f"{_base_url()}/disburse/get-invoice",
            json=payload, headers=_headers(), timeout=25,
        )
        data = resp.json()
        ok = str(data.get("response_code")) == "00"
        return ok, data.get("transaction_id", ""), data.get("response_text", "")
    except requests.RequestException as exc:
        logger.error("PayDunya disburse indisponible : %s", exc)
        return False, "", "Service de décaissement indisponible."


def parse_ipn(post_data):
    """Extrait (token, status, reference) d'une notification IPN PayDunya."""
    token = post_data.get("data[invoice][token]") or post_data.get("token", "")
    status = post_data.get("data[status]") or post_data.get("status", "")
    reference = (
        post_data.get("data[custom_data][reference]")
        or post_data.get("custom_data[reference]", "")
    )
    return token, status, reference
