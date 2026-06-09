"""Initialise les données de base : taux, limites KYC, compte admin."""
import os
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.models import DailyLimit
from exchange.models import ExchangeRate

User = get_user_model()


class Command(BaseCommand):
    help = "Crée le taux par défaut, les limites KYC L1/L2/L3 et un compte admin."

    def handle(self, *args, **options):
        # 1. Limites journalières par niveau
        limits = [
            (1, "Standard", "50000", "50000"),
            (2, "Vérifié", "500000", "500000"),
            (3, "Professionnel", "2000000", "2000000"),
        ]
        for level, label, dep, wit in limits:
            obj, created = DailyLimit.objects.update_or_create(
                level=level,
                defaults={
                    "label": label,
                    "deposit_xof_per_day": Decimal(dep),
                    "withdraw_xof_per_day": Decimal(wit),
                },
            )
            self.stdout.write(("  + " if created else "  · ") + f"Limite niveau {level} ({label})")

        # 2. Taux actif par défaut (1 NGN ≈ 0,385 XOF, frais 1,5 %)
        if not ExchangeRate.objects.filter(is_active=True).exists():
            ExchangeRate.objects.create(
                xof_per_ngn=Decimal("0.385000"),
                fee_percent=Decimal("1.50"),
                is_active=True,
            )
            self.stdout.write("  + Taux par défaut créé (1 NGN = 0,385 XOF, frais 1,5 %)")
        else:
            self.stdout.write("  · Taux actif déjà présent")

        # 3. Compte administrateur
        admin_email = os.environ.get("ADMIN_EMAIL", "admin@gochange.store")
        admin_password = os.environ.get("ADMIN_PASSWORD", "ChangeMoi123!")
        if not User.objects.filter(email=admin_email).exists():
            User.objects.create_superuser(
                email=admin_email, password=admin_password,
                first_name="Admin", last_name="GoChange",
            )
            self.stdout.write(self.style.SUCCESS(
                f"  + Compte admin créé : {admin_email} / {admin_password}"
            ))
            self.stdout.write(self.style.WARNING(
                "    ⚠ Changez ce mot de passe après la première connexion."
            ))
        else:
            self.stdout.write(f"  · Compte admin déjà présent : {admin_email}")

        self.stdout.write(self.style.SUCCESS("\nSeed terminé."))
