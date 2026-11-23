from django.urls import path
from . import views

urlpatterns = [
    path('labels/<int:pk>/', views.shipping_label, name='shipping-label'),
    path('labels/<int:pk>/qr.svg', views.shipping_qr, name='shipping-qr'),
    path('import/', views.bulk_import, name='shipping-bulk-import'),
    path('import/template.csv', views.import_template, name='shipping-import-template'),
    path('manifest/', views.driver_manifest, name='shipping-manifest'),
    path('manifest/export.csv', views.export_manifest, name='shipping-manifest-export'),
]
