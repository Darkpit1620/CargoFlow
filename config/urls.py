from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from deliveries import views as delivery_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", delivery_views.home, name="home"),
    path("dashboard/", delivery_views.dashboard, name="dashboard"),
    path("shipments/", delivery_views.shipment_list, name="shipment-list"),
    path("shipments/new/", delivery_views.shipment_create, name="shipment-create"),
    path("shipments/<int:pk>/", delivery_views.shipment_detail, name="shipment-detail"),
    path("shipments/<int:pk>/edit/", delivery_views.shipment_edit, name="shipment-edit"),
    path("shipments/<int:pk>/status/", delivery_views.shipment_change_status, name="shipment-status"),
    path("drivers/", delivery_views.driver_list, name="driver-list"),
    path("drivers/new/", delivery_views.driver_create, name="driver-create"),
    path("drivers/<int:pk>/edit/", delivery_views.driver_edit, name="driver-edit"),
    path("track/", delivery_views.track_shipment, name="track-shipment"),
    path("api/", include("deliveries.urls")),
    path("operations/", include("operations.urls")),
    path("shipping/", include("shipping_tools.urls")),
    path("support/", include("support_desk.urls")),
    path("fleet/", include("fleet.urls")),
    path("billing/", include("billing.urls")),
    path("insights/", include("insights.urls")),
    path("workboard/", include("workboard.urls")),
    path("warehouse/", include("warehouse.urls")),
    path("system/", include("system_center.urls")),
]
