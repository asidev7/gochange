"""Services de paiement et logique métier — GoChange."""
import secrets
from datetime import datetime


def make_reference(prefix):
    """Génère une référence unique lisible, ex. DEP-20260609-AB12CD."""
    stamp = datetime.now().strftime("%Y%m%d")
    rnd = secrets.token_hex(3).upper()
    return f"{prefix}-{stamp}-{rnd}"
