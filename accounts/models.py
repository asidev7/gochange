"""Modèles comptes & KYC — GoChange."""
from decimal import Decimal

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class CustomUserManager(BaseUserManager):
    """Gestionnaire d'utilisateurs basé sur l'e-mail (pas de username)."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("L'adresse e-mail est obligatoire.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("email_verified", True)
        if extra.get("is_staff") is not True:
            raise ValueError("Un superuser doit avoir is_staff=True.")
        if extra.get("is_superuser") is not True:
            raise ValueError("Un superuser doit avoir is_superuser=True.")
        return self._create_user(email, password, **extra)


class CustomUser(AbstractUser):
    """Utilisateur GoChange — connexion par e-mail."""

    username = None
    email = models.EmailField(_("adresse e-mail"), unique=True)
    phone = models.CharField(_("téléphone"), max_length=20, blank=True)
    country = models.CharField(_("pays"), max_length=2, default="BJ")  # BJ / NG

    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)

    # Code PIN de transaction (haché, jamais en clair)
    pin_hash = models.CharField(max_length=128, blank=True)

    # Préférences
    language = models.CharField(max_length=2, choices=[("fr", "Français"), ("en", "English")], default="fr")
    notify_email = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"

    def __str__(self):
        return self.email

    # --- Code PIN de transaction --------------------------------------- #
    def set_pin(self, raw_pin):
        from django.contrib.auth.hashers import make_password
        self.pin_hash = make_password(str(raw_pin))

    def check_pin(self, raw_pin):
        from django.contrib.auth.hashers import check_password
        if not self.pin_hash:
            return False
        return check_password(str(raw_pin), self.pin_hash)

    @property
    def has_pin(self):
        return bool(self.pin_hash)

    @property
    def display_name(self):
        full = self.get_full_name()
        return full or self.email.split("@")[0]

    @property
    def kyc_level(self):
        return self.kyc.level if hasattr(self, "kyc") else 1


class KYCProfile(models.Model):
    """Niveau KYC de l'utilisateur (1, 2 ou 3) et statut de la demande en cours."""

    STATUS_NONE = "none"
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_NONE, "Non soumis"),
        (STATUS_PENDING, "En attente"),
        (STATUS_APPROVED, "Approuvé"),
        (STATUS_REJECTED, "Rejeté"),
    ]

    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="kyc")
    level = models.PositiveSmallIntegerField(default=1)  # 1, 2, 3
    # Statut de la demande de passage au niveau supérieur
    pending_level = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_NONE)
    rejection_reason = models.TextField(blank=True)

    full_name = models.CharField("nom complet (pièce)", max_length=120, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.CharField(max_length=255, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "profil KYC"
        verbose_name_plural = "profils KYC"

    def __str__(self):
        return f"{self.user.email} — niveau {self.level}"

    @property
    def level_label(self):
        return {
            1: "Niveau 1 — Standard",
            2: "Niveau 2 — Vérifié",
            3: "Niveau 3 — Professionnel",
        }.get(self.level, "Niveau 1")

    @property
    def can_upgrade(self):
        return self.level < 3 and self.status != self.STATUS_PENDING


class KYCDocument(models.Model):
    """Document justificatif téléversé pour un passage de niveau."""

    TYPE_ID = "id"
    TYPE_SELFIE = "selfie"
    TYPE_ADDRESS = "address"
    TYPE_BUSINESS = "business"
    TYPE_CHOICES = [
        (TYPE_ID, "Pièce d'identité (CNI / passeport / CIP)"),
        (TYPE_SELFIE, "Selfie avec la pièce"),
        (TYPE_ADDRESS, "Justificatif d'adresse"),
        (TYPE_BUSINESS, "Registre de commerce (RCCM)"),
    ]

    profile = models.ForeignKey(KYCProfile, on_delete=models.CASCADE, related_name="documents")
    doc_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    target_level = models.PositiveSmallIntegerField(default=2)
    file = models.FileField(upload_to="kyc/%Y/%m/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "document KYC"
        verbose_name_plural = "documents KYC"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.profile.user.email} — {self.get_doc_type_display()}"


class DailyLimit(models.Model):
    """Limites journalières par niveau KYC (modifiables par l'admin)."""

    level = models.PositiveSmallIntegerField(unique=True)
    label = models.CharField(max_length=60)
    deposit_xof_per_day = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("50000"))
    withdraw_xof_per_day = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("50000"))

    class Meta:
        verbose_name = "limite journalière"
        verbose_name_plural = "limites journalières"
        ordering = ["level"]

    def __str__(self):
        return f"Niveau {self.level} — {self.label}"


class EmailVerificationToken(models.Model):
    """Jeton de vérification d'e-mail / réinitialisation de mot de passe."""

    PURPOSE_VERIFY = "verify"
    PURPOSE_RESET = "reset"

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="tokens")
    token = models.CharField(max_length=64, unique=True, db_index=True)
    purpose = models.CharField(max_length=10, default=PURPOSE_VERIFY)
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)

    def is_valid(self, max_age_hours=24):
        if self.used:
            return False
        return self.created_at >= timezone.now() - timezone.timedelta(hours=max_age_hours)

    def __str__(self):
        return f"{self.user.email} — {self.purpose}"
