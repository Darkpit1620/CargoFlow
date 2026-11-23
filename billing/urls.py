from django.urls import path
from . import views

urlpatterns = [
    path("", views.invoice_list, name="billing-list"),
    path("export.csv", views.invoice_export, name="billing-export"),
    path("shipments/<int:pk>/new/", views.invoice_create, name="billing-create"),
    path("invoices/<int:pk>/", views.invoice_detail, name="billing-detail"),
    path("invoices/<int:pk>/payments/new/", views.payment_create, name="billing-payment-create"),
]
