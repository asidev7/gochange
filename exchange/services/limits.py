"""Vérification des limites journalières (compteur remis à zéro à minuit)."""
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from accounts.models import DailyLimit


def _today_range():
    now = timezone.localtime()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start


def _limit_for(level):
    return DailyLimit.objects.filter(level=level).first()


def deposit_used_today(user):
    """Montant déposé (équivalent XOF) aujourd'hui — pour comparaison à la limite."""
    from exchange.models import Deposit, ExchangeRate

    start = _today_range()
    rate = ExchangeRate.current()
    total = Decimal("0")
    qs = Deposit.objects.filter(
        user=user, status=Deposit.STATUS_COMPLETED, completed_at__gte=start
    )
    for dep in qs:
        if dep.currency == "XOF":
            total += dep.amount
        elif rate:
            total += rate.convert(dep.amount, "NGN")
    return total


def withdraw_used_today(user):
    from exchange.models import Withdrawal, ExchangeRate

    start = _today_range()
    rate = ExchangeRate.current()
    total = Decimal("0")
    qs = Withdrawal.objects.filter(user=user, created_at__gte=start).exclude(
        status=Withdrawal.STATUS_FAILED
    )
    for w in qs:
        if w.currency == "XOF":
            total += w.amount
        elif rate:
            total += rate.convert(w.amount, "NGN")
    return total


def to_xof_equivalent(amount, currency):
    from exchange.models import ExchangeRate

    if currency == "XOF":
        return Decimal(amount)
    rate = ExchangeRate.current()
    return rate.convert(amount, "NGN") if rate else Decimal(amount)


def check_deposit_limit(user, amount, currency):
    """Retourne (ok, message, remaining_xof)."""
    level = user.kyc_level
    limit = _limit_for(level)
    if not limit:
        return True, "", None
    used = deposit_used_today(user)
    incoming = to_xof_equivalent(amount, currency)
    remaining = limit.deposit_xof_per_day - used
    if incoming > remaining:
        return (
            False,
            f"Ce dépôt dépasse votre limite journalière (niveau {level}). "
            f"Il vous reste {remaining:,.0f} FCFA aujourd'hui. "
            f"Passez au niveau supérieur pour augmenter vos limites.",
            remaining,
        )
    return True, "", remaining


def check_withdraw_limit(user, amount, currency):
    level = user.kyc_level
    limit = _limit_for(level)
    if not limit:
        return True, "", None
    used = withdraw_used_today(user)
    outgoing = to_xof_equivalent(amount, currency)
    remaining = limit.withdraw_xof_per_day - used
    if outgoing > remaining:
        return (
            False,
            f"Ce retrait dépasse votre limite journalière (niveau {level}). "
            f"Il vous reste {remaining:,.0f} FCFA aujourd'hui.",
            remaining,
        )
    return True, "", remaining


def limits_summary(user):
    """Données pour le dashboard : limites, utilisé, restant (en XOF)."""
    level = user.kyc_level
    limit = _limit_for(level)
    dep_used = deposit_used_today(user)
    wit_used = withdraw_used_today(user)
    dep_cap = limit.deposit_xof_per_day if limit else Decimal("0")
    wit_cap = limit.withdraw_xof_per_day if limit else Decimal("0")
    return {
        "level": level,
        "deposit_cap": dep_cap,
        "deposit_used": dep_used,
        "deposit_remaining": max(dep_cap - dep_used, Decimal("0")),
        "deposit_pct": int(min(dep_used / dep_cap * 100, 100)) if dep_cap else 0,
        "withdraw_cap": wit_cap,
        "withdraw_used": wit_used,
        "withdraw_remaining": max(wit_cap - wit_used, Decimal("0")),
        "withdraw_pct": int(min(wit_used / wit_cap * 100, 100)) if wit_cap else 0,
    }
