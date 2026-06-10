"""Variables globales disponibles dans tous les templates."""
from django.conf import settings


def site_globals(request):
    whatsapp = settings.WHATSAPP_NUMBER or ""

    # Réglages de marque (logo/nom) modifiables par l'admin — tolérant si table absente
    brand_name, brand_logo_url, primary_color = "GoChange", "", "#0066FF"
    try:
        from accounts.models import SiteSettings

        s = SiteSettings.current()
        brand_name = s.brand_name or brand_name
        primary_color = s.primary_color or primary_color
        if s.logo:
            brand_logo_url = s.logo.url
    except Exception:
        pass

    return {
        "SITE_URL": settings.SITE_URL,
        "SITE_NAME": brand_name,
        "BRAND_LOGO_URL": brand_logo_url,
        "BRAND_PRIMARY": primary_color,
        "CONTACT_EMAIL": settings.CONTACT_EMAIL,
        "WHATSAPP_NUMBER": whatsapp,
        "WHATSAPP_LINK": "https://wa.me/" + whatsapp.replace("+", "").replace(" ", ""),
        "PAYMENTS_SIMULATION": settings.PAYMENTS_SIMULATION,
    }
