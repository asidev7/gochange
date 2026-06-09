"""Administration portefeuilles & bénéficiaires — GoChange."""
from django.contrib import admin

from .models import Beneficiary, Wallet


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "balance_xof", "balance_ngn", "updated_at")
    search_fields = ("user__email",)
    readonly_fields = ("updated_at",)


@admin.register(Beneficiary)
class BeneficiaryAdmin(admin.ModelAdmin):
    list_display = ("user", "kind", "label", "operator", "phone", "bank_name", "account_number", "account_name")
    list_filter = ("kind", "operator")
    search_fields = ("user__email", "account_number", "account_name", "phone")
