from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="system-dashboard"),
    path("activity/", views.activity, name="system-activity"),
]
