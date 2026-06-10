"""Administration comptes & KYC — GoChange."""
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin

from . import emails
from .models import CustomUser, DailyLimit, KYCDocument, KYCProfile, SiteSettings


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ("email", "nom", "account_code", "country", "kyc_badge", "email_verified", "is_staff", "created_at")
    list_filter = ("country", "email_verified", "is_staff", "is_active")
    search_fields = ("email", "first_name", "last_name", "phone", "account_code")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "last_login", "account_code")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Identité", {"fields": ("first_name", "last_name", "phone", "country", "account_code")}),
        ("Vérification", {"fields": ("email_verified", "phone_verified")}),
        ("Préférences", {"fields": ("language", "notify_email")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "created_at")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2", "is_staff", "is_superuser")}),
    )

    @admin.display(description="Nom")
    def nom(self, obj):
        return obj.display_name

    @admin.display(description="KYC")
    def kyc_badge(self, obj):
        return f"Niveau {obj.kyc_level}"


class KYCDocumentInline(admin.TabularInline):
    model = KYCDocument
    extra = 0
    readonly_fields = ("doc_type", "target_level", "file", "uploaded_at")
    can_delete = False


@admin.register(KYCProfile)
class KYCProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "level", "status", "pending_level", "updated_at")
    list_filter = ("level", "status")
    search_fields = ("user__email", "full_name")
    readonly_fields = ("updated_at",)
    inlines = [KYCDocumentInline]
    actions = ["approuver", "rejeter"]

    @admin.action(description="Approuver le passage de niveau demandé")
    def approuver(self, request, queryset):
        n = 0
        for kyc in queryset.filter(status=KYCProfile.STATUS_PENDING):
            kyc.level = kyc.pending_level or kyc.level
            kyc.status = KYCProfile.STATUS_APPROVED
            kyc.pending_level = None
            kyc.rejection_reason = ""
            kyc.save()
            emails.send_kyc_decision_email(kyc.user, kyc.level, approved=True)
            n += 1
        self.message_user(request, f"{n} demande(s) approuvée(s) et notifiée(s).", messages.SUCCESS)

    @admin.action(description="Rejeter la demande de niveau")
    def rejeter(self, request, queryset):
        n = 0
        for kyc in queryset.filter(status=KYCProfile.STATUS_PENDING):
            target = kyc.pending_level or (kyc.level + 1)
            kyc.status = KYCProfile.STATUS_REJECTED
            kyc.pending_level = None
            kyc.save()
            emails.send_kyc_decision_email(kyc.user, target, approved=False, reason=kyc.rejection_reason)
            n += 1
        self.message_user(request, f"{n} demande(s) rejetée(s) et notifiée(s).", messages.WARNING)


@admin.register(KYCDocument)
class KYCDocumentAdmin(admin.ModelAdmin):
    list_display = ("profile", "doc_type", "target_level", "uploaded_at")
    list_filter = ("doc_type", "target_level")
    search_fields = ("profile__user__email",)


@admin.register(DailyLimit)
class DailyLimitAdmin(admin.ModelAdmin):
    list_display = ("level", "label", "deposit_xof_per_day", "withdraw_xof_per_day")
    list_editable = ("deposit_xof_per_day", "withdraw_xof_per_day")


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ("brand_name", "primary_color", "support_phone", "updated_at")

    def has_add_permission(self, request):
        # Singleton : on édite l'unique enregistrement
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
