"""Création automatique du portefeuille et du profil KYC à l'inscription."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from wallet.models import Wallet

from .models import CustomUser, KYCProfile


@receiver(post_save, sender=CustomUser)
def create_related_objects(sender, instance, created, **kwargs):
    if created:
        Wallet.objects.get_or_create(user=instance)
        KYCProfile.objects.get_or_create(user=instance)
