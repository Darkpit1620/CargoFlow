from django.urls import path
from . import views

urlpatterns = [
    path("", views.task_list, name="workboard-list"),
    path("new/", views.task_create, name="workboard-create"),
    path("export.csv", views.task_export, name="workboard-export"),
    path("<int:pk>/", views.task_detail, name="workboard-detail"),
    path("<int:pk>/edit/", views.task_edit, name="workboard-edit"),
    path("<int:pk>/status/", views.task_status, name="workboard-status"),
    path("<int:pk>/notes/", views.task_note, name="workboard-note"),
]
