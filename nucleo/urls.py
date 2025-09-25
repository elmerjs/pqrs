# nucleo/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('pqrs/nueva/', views.crear_pqrs, name='crear_pqrs'), # <-- AÑADE ESTA LÍNEA
    path('pqrs/<int:pqrs_id>/editar/', views.editar_pqrs, name='editar_pqrs'),

]