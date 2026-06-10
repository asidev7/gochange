"""Intégration FedaPay — recharge de compte en XOF (Bénin).

En l'absence de clé (settings.PAYMENTS_SIMULATION), les appels sont simulés :
le dépôt est confirmable via la vue de retour, sans appel réseau.
Documentation : https://docs.fedapay.com
"""
import logging

import requests
from django.conf import settings
from django.urls import reverse

logger = logging.getLogger("gochange.payments")

BASE_SANDBOX = "https://sandbox-api.fedapay.com/v1"
BASE_LIVE = "https://api.fedapay.com/v1"


def _base_url():
    return BASE_LIVE if settings.FEDAPAY_MODE == "live" else BASE_SANDBOX


def _headers():
    return {
        "Authorization": f"Bearer {settings.FEDAPAY_SECRET_KEY}",
        "Content-Type": "application/json",
    }


def create_transaction(request, deposit):
    """Crée une transaction FedaPay et retourne (checkout_url, token).

    En simulation, renvoie l'URL de retour interne pour confirmer la recharge.
    """
    return_url = request.build_absolute_uri(
        reverse("exchange:depot_retour", args=[deposit.reference])
    )
    callback_url = request.build_absolute_uri(reverse("exchange:webhook_paydunya"))

    if settings.PAYMENTS_SIMULATION or not settings.FEDAPAY_SECRET_KEY:
        logger.info("[SIMULATION] Transaction FedaPay %s", deposit.reference)
        return return_url + "?sim=1", f"SIM-{deposit.reference}"

    payload = {
        "description": f"Recharge GoChange {deposit.reference}",
        "amount": int(deposit.amount),
        "currency": {"iso": "XOF"},
        "callback_url": return_url,
        "custom_metadata": {"reference": deposit.reference},
    }
    try:
        # 1. Créer la transaction
        resp = requests.post(
            f"{_base_url()}/transactions", json=payload, headers=_headers(), timeout=20
        )
        data = resp.json()
        tx = data.get("v1/transaction") or data.get("transaction") or {}
        tx_id = tx.get("id")
        if not tx_id:
            raise RuntimeError(data.get("message", "Erreur FedaPay"))

        # 2. Générer le lien de paiement (token)
        tok = requests.post(
            f"{_base_url()}/transactions/{tx_id}/token", headers=_headers(), timeout=20
        ).json()
        token = tok.get("token", "")
        url = tok.get("url") or (f"https://{'' if settings.FEDAPAY_MODE=='live' else 'sandbox-'}process.fedapay.com/{token}")
        return url, str(tx_id)
    except requests.RequestException as exc:
        logger.error("FedaPay indisponible : %s", exc)
        raise RuntimeError("Service FedaPay momentanément indisponible.")
