"""
Configuration Django — GoChange (gochange.store)
Plateforme d'échange NGN ⇄ XOF — corridor Bénin–Nigeria.

Lit la configuration depuis un fichier .env (voir .env.example).
Par défaut SQLite ; bascule sur PostgreSQL si DATABASE_URL est défini.
"""
from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env(key, default=None):
    return os.environ.get(key, default)


def env_bool(key, default=False):
    val = os.environ.get(key)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


# --------------------------------------------------------------------------- #
# Base
# --------------------------------------------------------------------------- #
SECRET_KEY = env("SECRET_KEY", "django-insecure-dev-key-change-me-in-production-0048ae")
DEBUG = env_bool("DEBUG", True)

ALLOWED_HOSTS = [h.strip() for h in env(
    "ALLOWED_HOSTS", "localhost,127.0.0.1,.gochange.store"
).split(",") if h.strip()]

CSRF_TRUSTED_ORIGINS = [o.strip() for o in env(
    "CSRF_TRUSTED_ORIGINS", "https://gochange.store,https://www.gochange.store"
).split(",") if o.strip()]

SITE_URL = env("SITE_URL", "https://gochange.store")
SITE_ID = 1

# --------------------------------------------------------------------------- #
# Applications
# --------------------------------------------------------------------------- #
INSTALLED_APPS = [
    "jazzmin",  # admin stylé — doit précéder django.contrib.admin
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.sitemaps",
    "django.contrib.humanize",

    # Apps GoChange
    "accounts",
    "wallet",
    "exchange",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site_globals",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --------------------------------------------------------------------------- #
# Base de données — SQLite par défaut, PostgreSQL si DATABASE_URL
# --------------------------------------------------------------------------- #
DATABASE_URL = env("DATABASE_URL")
if DATABASE_URL:
    # Format : postgres://user:password@host:port/dbname
    from urllib.parse import urlparse

    parsed = urlparse(DATABASE_URL)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": parsed.path.lstrip("/"),
            "USER": parsed.username or "",
            "PASSWORD": parsed.password or "",
            "HOST": parsed.hostname or "",
            "PORT": str(parsed.port or ""),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# --------------------------------------------------------------------------- #
# Authentification
# --------------------------------------------------------------------------- #
AUTH_USER_MODEL = "accounts.CustomUser"
AUTHENTICATION_BACKENDS = ["accounts.backends.EmailBackend"]

LOGIN_URL = "accounts:connexion"
LOGIN_REDIRECT_URL = "exchange:dashboard"
LOGOUT_REDIRECT_URL = "core:landing"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------------------------------------------------------------- #
# Internationalisation
# --------------------------------------------------------------------------- #
LANGUAGE_CODE = "fr"
TIME_ZONE = "Africa/Porto-Novo"
USE_I18N = True
USE_TZ = True

LANGUAGES = [("fr", "Français"), ("en", "English")]

# --------------------------------------------------------------------------- #
# Fichiers statiques & médias
# --------------------------------------------------------------------------- #
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------- #
# E-mail — console en dev, SMTP en prod
# --------------------------------------------------------------------------- #
if env("EMAIL_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = env("EMAIL_HOST")
    EMAIL_PORT = int(env("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "GoChange <no-reply@gochange.store>")
CONTACT_EMAIL = env("CONTACT_EMAIL", "contact@gochange.store")
WHATSAPP_NUMBER = env("WHATSAPP_NUMBER", "+22990000000")

# --------------------------------------------------------------------------- #
# Sécurité (prod)
# --------------------------------------------------------------------------- #
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_CONTENT_TYPE_NOSNIFF = True

# --------------------------------------------------------------------------- #
# Fournisseurs de paiement
# Si les clés secrètes sont absentes -> mode simulation (sandbox local).
# --------------------------------------------------------------------------- #
PAYDUNYA_MASTER_KEY = env("PAYDUNYA_MASTER_KEY", "")
PAYDUNYA_PRIVATE_KEY = env("PAYDUNYA_PRIVATE_KEY", "")
PAYDUNYA_PUBLIC_KEY = env("PAYDUNYA_PUBLIC_KEY", "")
PAYDUNYA_TOKEN = env("PAYDUNYA_TOKEN", "")
PAYDUNYA_MODE = env("PAYDUNYA_MODE", "test")  # test | live

PAYSTACK_SECRET_KEY = env("PAYSTACK_SECRET_KEY", "")
PAYSTACK_PUBLIC_KEY = env("PAYSTACK_PUBLIC_KEY", "")

# FedaPay (recharge XOF — Bénin)
FEDAPAY_SECRET_KEY = env("FEDAPAY_SECRET_KEY", "")
FEDAPAY_PUBLIC_KEY = env("FEDAPAY_PUBLIC_KEY", "")
FEDAPAY_MODE = env("FEDAPAY_MODE", "live")  # live | sandbox

# Mode simulation : aucun appel réseau réel, crédit via webhook simulé.
PAYMENTS_SIMULATION = not (PAYDUNYA_MASTER_KEY and PAYSTACK_SECRET_KEY)

# --------------------------------------------------------------------------- #
# Logs des appels API / webhooks
# --------------------------------------------------------------------------- #
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "gochange.payments": {"handlers": ["console"], "level": "INFO"},
    },
}

MESSAGE_TAGS = {
    10: "debug", 20: "info", 25: "success", 30: "warning", 40: "error",
}

# --------------------------------------------------------------------------- #
# Jazzmin (admin)
# --------------------------------------------------------------------------- #
JAZZMIN_SETTINGS = {
    "site_title": "GoChange Admin",
    "site_header": "GoChange",
    "site_brand": "GoChange",
    "welcome_sign": "Administration GoChange",
    "copyright": "ASITECH SOLUTION — Parakou",
    "search_model": ["accounts.CustomUser", "exchange.Withdrawal"],
    "show_ui_builder": False,
    "changeform_format": "single",
    "icons": {
        "accounts.CustomUser": "fas fa-user",
        "accounts.KYCProfile": "fas fa-id-card",
        "accounts.KYCDocument": "fas fa-file-upload",
        "accounts.DailyLimit": "fas fa-sliders-h",
        "wallet.Wallet": "fas fa-wallet",
        "wallet.Beneficiary": "fas fa-address-book",
        "exchange.ExchangeRate": "fas fa-chart-line",
        "exchange.Deposit": "fas fa-arrow-down",
        "exchange.ExchangeTransaction": "fas fa-exchange-alt",
        "exchange.Withdrawal": "fas fa-arrow-up",
        "exchange.WebhookLog": "fas fa-bell",
    },
}
JAZZMIN_UI_TWEAKS = {
    "theme": "default",
    "navbar": "navbar-white navbar-light",
    "accent": "accent-primary",
    "sidebar": "sidebar-dark-primary",
}
