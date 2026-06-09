"""Tests de base : échange atomique, limites, retrait, dépôt simulé."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import DailyLimit
from wallet.models import Beneficiary, Wallet

from .models import NGN, XOF, Deposit, ExchangeRate, Withdrawal
from .services import limits
from .views import _create_withdrawal, _credit_deposit, _execute_exchange

User = get_user_model()


class BaseData(TestCase):
    def setUp(self):
        DailyLimit.objects.create(level=1, label="Standard",
                                  deposit_xof_per_day=Decimal("50000"),
                                  withdraw_xof_per_day=Decimal("50000"))
        self.rate = ExchangeRate.objects.create(
            xof_per_ngn=Decimal("0.385000"), fee_percent=Decimal("1.50"), is_active=True)
        self.user = User.objects.create_user(email="u@test.com", password="pass12345",
                                             email_verified=True)
        self.wallet = Wallet.objects.get(user=self.user)


class ExchangeTests(BaseData):
    def test_exchange_debits_credits_and_freezes_rate(self):
        self.wallet.balance_ngn = Decimal("100000")
        self.wallet.save()
        tx = _execute_exchange(self.user, NGN, XOF, Decimal("10000"), self.rate)
        # 10000 NGN * 0.385 = 3850 XOF brut ; frais 1.5% = 57.75 ; net = 3792.25
        self.assertEqual(tx.amount_to, Decimal("3792.25"))
        self.assertEqual(tx.fee_amount, Decimal("57.75"))
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance_ngn, Decimal("90000"))
        self.assertEqual(self.wallet.balance_xof, Decimal("3792.25"))

    def test_exchange_insufficient_balance_raises(self):
        with self.assertRaises(ValueError):
            _execute_exchange(self.user, NGN, XOF, Decimal("10000"), self.rate)


class DepositTests(BaseData):
    def test_credit_deposit_is_idempotent(self):
        dep = Deposit.objects.create(user=self.user, currency=XOF, amount=Decimal("5000"),
                                     provider=Deposit.PROVIDER_PAYDUNYA, reference="DEP-T-1")
        self.assertTrue(_credit_deposit(dep))
        self.assertFalse(_credit_deposit(dep))  # 2e fois : pas de double crédit
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance_xof, Decimal("5000"))


class LimitTests(BaseData):
    def test_deposit_over_limit_blocked(self):
        ok, msg, remaining = limits.check_deposit_limit(self.user, Decimal("60000"), XOF)
        self.assertFalse(ok)
        self.assertEqual(remaining, Decimal("50000"))

    def test_deposit_within_limit_ok(self):
        ok, _, _ = limits.check_deposit_limit(self.user, Decimal("40000"), XOF)
        self.assertTrue(ok)


class WithdrawalTests(BaseData):
    def test_withdrawal_debits_wallet(self):
        self.wallet.balance_xof = Decimal("20000")
        self.wallet.save()
        ben = Beneficiary.objects.create(user=self.user, kind=Beneficiary.KIND_MOMO,
                                         operator="mtn", phone="+22990000000")
        wd = _create_withdrawal(self.user, ben, Decimal("8000"), XOF)
        self.assertEqual(wd.status, Withdrawal.STATUS_PENDING)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance_xof, Decimal("12000"))
