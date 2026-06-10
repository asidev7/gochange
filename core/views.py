"""Vues des pages publiques, contact et SEO — GoChange."""
from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.template.response import TemplateResponse
from django.views.decorators.http import require_GET

from exchange.models import ExchangeRate

from .forms import ContactForm


# Données réutilisées par plusieurs pages (taux affiché publiquement)
def _public_rate():
    return ExchangeRate.current()


def landing(request):
    return render(request, "public/landing.html", {
        "rate": _public_rate(),
        "meta_title": "GoChange — Échangez vos Naira en FCFA, simplement",
        "meta_description": (
            "GoChange convertit vos Naira en FCFA (et inversement) au vrai taux du jour, "
            "directement sur votre Mobile Money ou votre compte bancaire. Bénin–Nigeria."
        ),
    })


def taux(request):
    rate = _public_rate()
    history = ExchangeRate.objects.order_by("-created_at")[:12]
    return render(request, "public/taux.html", {
        "rate": rate,
        "history": history,
        "meta_title": "Taux du jour NGN ⇄ XOF — GoChange",
        "meta_description": "Consultez le taux du jour Naira ⇄ FCFA appliqué par GoChange, mis à jour quotidiennement.",
    })


def faq(request):
    return render(request, "public/faq.html", {
        "meta_title": "Questions fréquentes — GoChange",
        "meta_description": "Délais, frais, sécurité, KYC, limites : les réponses aux questions les plus posées sur GoChange.",
    })


def a_propos(request):
    return render(request, "public/a_propos.html", {
        "meta_title": "À propos — GoChange par ASITECH SOLUTION",
        "meta_description": "GoChange est édité par ASITECH SOLUTION, basée à Parakou (Bénin). Notre mission : un change Naira–FCFA simple et honnête.",
    })


def contact(request):
    form = ContactForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        body = (
            f"Message de {form.cleaned_data['name']} <{form.cleaned_data['email']}>\n\n"
            f"{form.cleaned_data['message']}"
        )
        try:
            send_mail(
                subject=f"[Contact GoChange] {form.cleaned_data['subject']}",
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.CONTACT_EMAIL],
                fail_silently=True,
            )
        finally:
            messages.success(
                request,
                "Merci ! Votre message est bien parti. Nous répondons en général sous quelques heures.",
            )
            return redirect("core:contact")
    return render(request, "public/contact.html", {
        "form": form,
        "meta_title": "Contact — GoChange",
        "meta_description": "Une question ? Écrivez-nous ou contactez-nous sur WhatsApp, 7j/7.",
    })


def cgu(request):
    return render(request, "public/cgu.html", {
        "meta_title": "Conditions générales d'utilisation — GoChange",
        "meta_description": "Conditions générales d'utilisation de la plateforme GoChange.",
    })


def confidentialite(request):
    return render(request, "public/confidentialite.html", {
        "meta_title": "Politique de confidentialité — GoChange",
        "meta_description": "Comment GoChange collecte, utilise et protège vos données personnelles.",
    })


@require_GET
def robots_txt(request):
    return TemplateResponse(request, "robots.txt", content_type="text/plain")


@require_GET
def service_worker(request):
    """Service worker servi à la racine (scope /) pour la PWA."""
    from django.http import HttpResponse

    js = """
const CACHE = 'gochange-v1';
const ASSETS = ['/', '/dashboard/'];
self.addEventListener('install', (e) => {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS).catch(() => {})));
});
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) =>
    Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))));
  self.clients.claim();
});
self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;                 // jamais de cache pour POST
  if (new URL(req.url).pathname.startsWith('/static/')) {
    e.respondWith(caches.match(req).then((r) => r || fetch(req).then((res) => {
      const copy = res.clone();
      caches.open(CACHE).then((c) => c.put(req, copy));
      return res;
    }).catch(() => r)));
  }
});
"""
    resp = HttpResponse(js, content_type="application/javascript")
    resp["Service-Worker-Allowed"] = "/"
    return resp
