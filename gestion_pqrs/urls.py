# gestion_pqrs/urls.py
from django.contrib import admin
from django.urls import path, include # <-- Asegúrate de que 'include' esté aquí

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('nucleo.urls')), # <-- Añade esta línea
]