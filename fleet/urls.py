from django.urls import path
from . import views

urlpatterns = [
    path("", views.vehicle_list, name="fleet-list"),
    path("new/", views.vehicle_create, name="fleet-create"),
    path("due/", views.service_due, name="fleet-due"),
    path("export.csv", views.vehicle_export, name="fleet-export"),
    path("vehicles/<int:pk>/", views.vehicle_detail, name="fleet-detail"),
    path("vehicles/<int:pk>/edit/", views.vehicle_edit, name="fleet-edit"),
    path("vehicles/<int:pk>/service/new/", views.service_create, name="fleet-service-create"),
]
