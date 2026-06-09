"""Administration taux, dépôts, échanges, retraits — GoChange."""
from django.contrib import admin, messages
from django.utils import timezone

from .models import (
    Deposit,
    ExchangeRate,
    ExchangeTransaction,
    WebhookLog,
    Withdrawal,
)
from .services import paydunya, paystack


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ("__str__", "xof_per_ngn", "fee_percent", "is_active", "created_at")
    list_editable = ("is_active",)
    list_filter = ("is_active",)


@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display = ("reference", "user", "amount", "currency", "provider", "status", "created_at")
    list_filter = ("status", "provider", "currency")
    search_fields = ("reference", "user__email")
    readonly_fields = ("created_at", "completed_at", "provider_token", "checkout_url")


@admin.register(ExchangeTransaction)
class ExchangeTransactionAdmin(admin.ModelAdmin):
    list_display = ("reference", "user", "amount_from", "from_currency", "amount_to", "to_currency", "fee_amount", "created_at")
    list_filter = ("from_currency", "to_currency")
    search_fields = ("reference", "user__email")
    readonly_fields = [f.name for f in ExchangeTransaction._meta.fields]


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ("reference", "user", "amount", "currency", "destination", "status", "created_at")
    list_filter = ("status", "currency")
    search_fields = ("reference", "user__email", "account_number", "phone")
    readonly_fields = ("created_at", "processed_at", "provider_reference")
    actions = ["approuver_et_payer"]

    @admin.action(description="Approuver et exécuter le décaissement")
    def approuver_et_payer(self, request, queryset):
        ok_count = 0
        for wd in queryset.filter(status=Withdrawal.STATUS_PENDING):
            wd.status = Withdrawal.STATUS_PROCESSING
            wd.save(update_fields=["status"])
            if wd.currency == "XOF":
                ok, ref, msg = paydunya.disburse(wd)
            else:
                ok, ref, msg = paystack.create_transfer(wd)
            if ok:
                wd.provider_reference = ref
                wd.status = Withdrawal.STATUS_COMPLETED
                wd.processed_at = timezone.now()
                ok_count += 1
            else:
                wd.status = Withdrawal.STATUS_FAILED
                wd.failure_reason = msg
            wd.save()
        self.message_user(request, f"{ok_count} retrait(s) décaissé(s).", messages.SUCCESS)


@admin.register(WebhookLog)
class WebhookLogAdmin(admin.ModelAdmin):
    list_display = ("provider", "event", "reference", "signature_valid", "processed", "received_at")
    list_filter = ("provider", "processed", "signature_valid")
    search_fields = ("reference",)
    readonly_fields = [f.name for f in WebhookLog._meta.fields]
