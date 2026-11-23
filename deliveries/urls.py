from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .api import DriverViewSet, ShipmentViewSet, TrackingEventViewSet, health_check, public_tracking

router = DefaultRouter()
router.register("shipments", ShipmentViewSet, basename="api-shipments")
router.register("drivers", DriverViewSet, basename="api-drivers")
router.register("events", TrackingEventViewSet, basename="api-events")

urlpatterns = [
    path("health/", health_check, name="api-health"),
    path("track/<str:tracking_number>/", public_tracking, name="api-track"),
    path("", include(router.urls)),
]
