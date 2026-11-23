from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='warehouse-dashboard'),
    path('hubs/new/', views.new_hub, name='warehouse-new-hub'),
    path('bins/new/', views.new_bin, name='warehouse-new-bin'),
    path('scan/', views.scan_parcel, name='warehouse-scan'),
    path('positions.csv', views.export_positions, name='warehouse-export'),
]
