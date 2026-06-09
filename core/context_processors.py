"""Variables globales disponibles dans tous les templates."""
from django.conf import settings


def site_globals(request):
    whatsapp = settings.WHATSAPP_NUMBER or ""
    return {
        "SITE_URL": settings.SITE_URL,
        "SITE_NAME": "GoChange",
        "CONTACT_EMAIL": settings.CONTACT_EMAIL,
        "WHATSAPP_NUMBER": whatsapp,
        "WHATSAPP_LINK": "https://wa.me/" + whatsapp.replace("+", "").replace(" ", ""),
        "PAYMENTS_SIMULATION": settings.PAYMENTS_SIMULATION,
    }
