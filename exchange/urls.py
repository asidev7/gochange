"""URLs espace connecté & webhooks — GoChange."""
from django.urls import path

from . import views

app_name = "exchange"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("deposer/", views.deposer, name="deposer"),
    path("deposer/retour/<str:reference>/", views.depot_retour, name="depot_retour"),
    path("echanger/", views.echanger, name="echanger"),
    path("retirer/", views.retirer, name="retirer"),
    path("transferer/", views.transferer, name="transferer"),
    path("transactions/", views.transactions, name="transactions"),
    path("transactions/export.csv", views.transactions_csv, name="transactions_csv"),
    path("beneficiaires/", views.beneficiaires, name="beneficiaires"),
    path("beneficiaires/<int:pk>/supprimer/", views.beneficiaire_supprimer, name="beneficiaire_supprimer"),

    # API internes (JSON)
    path("api/banques/", views.api_banques, name="api_banques"),
    path("api/resoudre-compte/", views.api_resoudre_compte, name="api_resoudre_compte"),

    # Webhooks fournisseurs
    path("webhooks/paydunya/", views.webhook_paydunya, name="webhook_paydunya"),
    path("webhooks/paystack/", views.webhook_paystack, name="webhook_paystack"),
]
