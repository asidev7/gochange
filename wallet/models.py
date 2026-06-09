"""Portefeuille et bénéficiaires — GoChange."""
from decimal import Decimal

from django.conf import settings
from django.db import models


class Wallet(models.Model):
    """Soldes NGN et XOF d'un utilisateur. Mises à jour sous select_for_update."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallet")
    balance_ngn = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0"))
    balance_xof = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0"))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "portefeuille"
        verbose_name_plural = "portefeuilles"

    def __str__(self):
        return f"Portefeuille {self.user.email}"

    def balance(self, currency):
        return self.balance_xof if currency == "XOF" else self.balance_ngn

    def credit(self, currency, amount):
        if currency == "XOF":
            self.balance_xof += amount
        else:
            self.balance_ngn += amount

    def debit(self, currency, amount):
        if currency == "XOF":
            self.balance_xof -= amount
        else:
            self.balance_ngn -= amount


class Beneficiary(models.Model):
    """Compte bénéficiaire enregistré : Mobile Money (XOF) ou banque (NGN)."""

    KIND_MOMO = "momo"
    KIND_BANK = "bank"
    KIND_CHOICES = [(KIND_MOMO, "Mobile Money (XOF)"), (KIND_BANK, "Compte bancaire (NGN)")]

    # Opérateurs Mobile Money (Bénin)
    OPERATOR_CHOICES = [
        ("mtn", "MTN MoMo"),
        ("moov", "Moov Money"),
        ("celtiis", "Celtiis Cash"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="beneficiaries")
    kind = models.CharField(max_length=4, choices=KIND_CHOICES)
    label = models.CharField("libellé", max_length=80, blank=True)

    # XOF / Mobile Money
    operator = models.CharField(max_length=10, choices=OPERATOR_CHOICES, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    # NGN / Banque
    bank_code = models.CharField(max_length=10, blank=True)
    bank_name = models.CharField(max_length=80, blank=True)
    account_number = models.CharField(max_length=10, blank=True)
    account_name = models.CharField("nom du titulaire", max_length=120, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "bénéficiaire"
        verbose_name_plural = "bénéficiaires"
        ordering = ["-created_at"]

    def __str__(self):
        if self.kind == self.KIND_BANK:
            return f"{self.account_name} — {self.bank_name} ({self.account_number})"
        return f"{self.get_operator_display()} — {self.phone}"

    @property
    def currency(self):
        return "NGN" if self.kind == self.KIND_BANK else "XOF"
