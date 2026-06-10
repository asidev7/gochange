"""Taux, dépôts, échanges, retraits et journal des webhooks — GoChange."""
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

XOF = "XOF"
NGN = "NGN"
CURRENCY_CHOICES = [(XOF, "FCFA (XOF)"), (NGN, "Naira (NGN)")]


class ExchangeRate(models.Model):
    """Taux NGN⇄XOF du jour et frais d'échange. Un seul enregistrement actif."""

    # 1 NGN = xof_per_ngn XOF  (ex. 1 NGN ≈ 0.385 XOF)
    xof_per_ngn = models.DecimalField(max_digits=12, decimal_places=6, default=Decimal("0.385000"))
    # Frais d'échange en pourcentage (ex. 1.50 => 1,5 %)
    fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("1.50"))
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "taux de change"
        verbose_name_plural = "taux de change"
        ordering = ["-created_at"]

    def __str__(self):
        return f"1 NGN = {self.xof_per_ngn} XOF (frais {self.fee_percent} %)"

    @property
    def ngn_per_xof(self):
        if self.xof_per_ngn:
            return (Decimal("1") / self.xof_per_ngn).quantize(Decimal("0.000001"))
        return Decimal("0")

    @classmethod
    def current(cls):
        return cls.objects.filter(is_active=True).order_by("-created_at").first()

    def convert(self, amount, from_currency):
        """Convertit `amount` depuis from_currency vers l'autre devise (avant frais)."""
        amount = Decimal(amount)
        if from_currency == NGN:
            return (amount * self.xof_per_ngn).quantize(Decimal("0.01"))
        return (amount * self.ngn_per_xof).quantize(Decimal("0.01"))


class Deposit(models.Model):
    """Dépôt entrant via PayDunya (XOF) ou Paystack (NGN)."""

    STATUS_PENDING = "pending"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "En attente"),
        (STATUS_COMPLETED, "Confirmé"),
        (STATUS_FAILED, "Échoué"),
    ]

    PROVIDER_PAYDUNYA = "paydunya"
    PROVIDER_PAYSTACK = "paystack"
    PROVIDER_FEDAPAY = "fedapay"
    PROVIDER_CHOICES = [
        (PROVIDER_PAYDUNYA, "PayDunya"),
        (PROVIDER_FEDAPAY, "FedaPay"),
        (PROVIDER_PAYSTACK, "Paystack"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="deposits")
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES)
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    provider = models.CharField(max_length=10, choices=PROVIDER_CHOICES)
    operator = models.CharField(max_length=20, blank=True)  # mtn / moov / celtiis (XOF)

    reference = models.CharField(max_length=64, unique=True, db_index=True)
    provider_token = models.CharField(max_length=255, blank=True)  # token/invoice/access_code
    checkout_url = models.URLField(blank=True)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "dépôt"
        verbose_name_plural = "dépôts"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Dépôt {self.reference} — {self.amount} {self.currency}"

    def mark_completed(self):
        self.status = self.STATUS_COMPLETED
        self.completed_at = timezone.now()


class ExchangeTransaction(models.Model):
    """Échange NGN⇄XOF. Taux figé à la validation, opération atomique."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="exchanges")
    from_currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES)
    to_currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES)

    amount_from = models.DecimalField(max_digits=16, decimal_places=2)
    rate_used = models.DecimalField(max_digits=12, decimal_places=6)
    fee_percent = models.DecimalField(max_digits=5, decimal_places=2)
    fee_amount = models.DecimalField(max_digits=16, decimal_places=2)  # exprimé en to_currency
    amount_to = models.DecimalField(max_digits=16, decimal_places=2)  # net reçu

    reference = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "échange"
        verbose_name_plural = "échanges"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Échange {self.amount_from} {self.from_currency} → {self.amount_to} {self.to_currency}"


class Withdrawal(models.Model):
    """Retrait sortant : Mobile Money (XOF / PayDunya) ou banque (NGN / Paystack)."""

    STATUS_PENDING = "pending"        # créé, en attente d'approbation admin
    STATUS_PROCESSING = "processing"  # décaissement envoyé au provider
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "En attente"),
        (STATUS_PROCESSING, "En traitement"),
        (STATUS_COMPLETED, "Payé"),
        (STATUS_FAILED, "Échoué"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="withdrawals")
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES)
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    beneficiary = models.ForeignKey("wallet.Beneficiary", on_delete=models.SET_NULL, null=True, blank=True)

    # Instantané du bénéficiaire au moment du retrait
    operator = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    bank_code = models.CharField(max_length=10, blank=True)
    bank_name = models.CharField(max_length=80, blank=True)
    account_number = models.CharField(max_length=10, blank=True)
    account_name = models.CharField(max_length=120, blank=True)

    reference = models.CharField(max_length=64, unique=True, db_index=True)
    provider_reference = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING)
    failure_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "retrait"
        verbose_name_plural = "retraits"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Retrait {self.reference} — {self.amount} {self.currency}"

    @property
    def destination(self):
        if self.currency == NGN:
            return f"{self.account_name} — {self.bank_name} ({self.account_number})"
        return f"{self.get_operator_display() if self.operator else ''} {self.phone}".strip()


class InternalTransfer(models.Model):
    """Transfert interne instantané entre deux comptes GoChange (via code/téléphone)."""

    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transfers_sent")
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transfers_received")
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES)
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    note = models.CharField("note", max_length=140, blank=True)
    reference = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "transfert interne"
        verbose_name_plural = "transferts internes"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.sender} → {self.recipient} : {self.amount} {self.currency}"


class WebhookLog(models.Model):
    """Journal idempotent des webhooks reçus (IPN PayDunya / Paystack)."""

    provider = models.CharField(max_length=10)
    event = models.CharField(max_length=60, blank=True)
    reference = models.CharField(max_length=120, db_index=True, blank=True)
    signature_valid = models.BooleanField(default=False)
    processed = models.BooleanField(default=False)
    payload = models.JSONField(default=dict, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "log webhook"
        verbose_name_plural = "logs webhooks"
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.provider} — {self.event} — {self.reference}"
