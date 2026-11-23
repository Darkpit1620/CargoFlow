from django.urls import path
from . import views

urlpatterns = [
    path("", views.case_list, name="support-desk-list"),
    path("overdue/", views.overdue_deliveries, name="support-desk-overdue"),
    path("export.csv", views.export_cases, name="support-desk-export"),
    path("shipments/<int:pk>/new/", views.case_create, name="support-desk-create"),
    path("cases/<int:pk>/", views.case_detail, name="support-desk-detail"),
    path("cases/<int:pk>/update/", views.case_update, name="support-desk-update"),
]
