"""Envoi d'e-mails transactionnels — GoChange."""
import secrets

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse

from .models import EmailVerificationToken


def _make_token(user, purpose):
    token = secrets.token_urlsafe(32)
    EmailVerificationToken.objects.create(user=user, token=token, purpose=purpose)
    return token


def _send(subject, template, context, to):
    body = render_to_string(template, context)
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[to],
        html_message=body,
        fail_silently=False,
    )


def send_verification_email(request, user):
    token = _make_token(user, EmailVerificationToken.PURPOSE_VERIFY)
    link = request.build_absolute_uri(reverse("accounts:verifier_email", args=[token]))
    _send(
        "Confirmez votre adresse e-mail — GoChange",
        "emails/verification.html",
        {"user": user, "link": link},
        user.email,
    )


def send_password_reset_email(request, user):
    token = _make_token(user, EmailVerificationToken.PURPOSE_RESET)
    link = request.build_absolute_uri(reverse("accounts:reinitialiser", args=[token]))
    _send(
        "Réinitialisation de votre mot de passe — GoChange",
        "emails/reset.html",
        {"user": user, "link": link},
        user.email,
    )


def send_kyc_decision_email(user, level, approved, reason=""):
    subject = (
        f"Votre niveau {level} est approuvé — GoChange"
        if approved
        else f"Votre demande de niveau {level} — GoChange"
    )
    _send(
        subject,
        "emails/kyc_decision.html",
        {"user": user, "level": level, "approved": approved, "reason": reason},
        user.email,
    )
