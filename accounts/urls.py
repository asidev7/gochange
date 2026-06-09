"""URLs comptes, authentification, profil et KYC — GoChange."""
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("inscription/", views.inscription, name="inscription"),
    path("connexion/", views.connexion, name="connexion"),
    path("deconnexion/", views.deconnexion, name="deconnexion"),
    path("verifier-email/<str:token>/", views.verifier_email, name="verifier_email"),
    path("renvoyer-verification/", views.renvoyer_verification, name="renvoyer_verification"),
    path("mot-de-passe-oublie/", views.mot_de_passe_oublie, name="mot_de_passe_oublie"),
    path("reinitialiser/<str:token>/", views.reinitialiser_mot_de_passe, name="reinitialiser"),

    path("profil/", views.profil, name="profil"),
    path("profil/mot-de-passe/", views.changer_mot_de_passe, name="changer_mot_de_passe"),
    path("profil/kyc/", views.kyc_upgrade, name="kyc_upgrade"),
    path("parametres/", views.parametres, name="parametres"),
    path("parametres/supprimer/", views.supprimer_compte, name="supprimer_compte"),
]
