"""URLs des pages publiques — GoChange."""
from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("taux/", views.taux, name="taux"),
    path("faq/", views.faq, name="faq"),
    path("a-propos/", views.a_propos, name="a_propos"),
    path("contact/", views.contact, name="contact"),
    path("cgu/", views.cgu, name="cgu"),
    path("confidentialite/", views.confidentialite, name="confidentialite"),
    path("robots.txt", views.robots_txt, name="robots"),
    path("sw.js", views.service_worker, name="service_worker"),
]
