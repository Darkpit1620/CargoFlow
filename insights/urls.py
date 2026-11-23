from django.urls import path
from . import views

urlpatterns = [
    path('', views.insights_dashboard, name='insights-dashboard'),
    path('attention/', views.insights_exceptions, name='insights-attention'),
    path('shipments.csv', views.insights_export, name='insights-export'),
]
