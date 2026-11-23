from django.urls import path
from . import views

urlpatterns = [
    path("dispatch/", views.dispatch_board, name="operations-dispatch"),
    path("dispatch/<int:pk>/assign/", views.assign_driver, name="operations-assign"),
    path("shipments/<int:pk>/confirm/", views.confirm_delivery, name="operations-confirm"),
    path("shipments/<int:pk>/attempt/", views.record_attempt, name="operations-attempt"),
    path("reports/", views.reports, name="operations-reports"),
    path("reports/export/", views.export_report, name="operations-export"),
]
