# nucleo/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('pqrs/crear-desde-pdf/', views.crear_pqrs_desde_pdf, name='crear_pqrs_desde_pdf'),
    path('pqrs/nueva/', views.crear_pqrs, name='crear_pqrs'), # <-- AÑADE ESTA LÍNEA
     path('pqrs/<int:pqrs_id>/', views.detalle_pqrs, name='detalle_pqrs'),
    path('adjunto/<int:adjunto_id>/eliminar/', views.eliminar_adjunto, name='eliminar_adjunto'),

    path('pqrs/<int:pqrs_id>/editar/', views.editar_pqrs, name='editar_pqrs'),
    path('pqrs/exportar/', views.exportar_excel, name='exportar_excel'),
    path('pqrs/<int:pqrs_id>/pdf/', views.generar_pdf, name='generar_pdf'),
    path('pqrs/<int:pqrs_id>/enviar-respuesta/', views.enviar_respuesta_email, name='enviar_respuesta_email'),
    path('pqrs/<int:pqrs_id>/asignar/', views.asignar_abogado, name='asignar_abogado'),
    path('pqrs/<int:pqrs_id>/cerrar/', views.cerrar_pqrs, name='cerrar_pqrs'),
    path('pqrs/<int:pqrs_id>/reabrir/', views.reabrir_pqrs, name='reabrir_pqrs'),
    path('pqrs/<int:pqrs_id>/trasladar/', views.trasladar_pqrs, name='trasladar_pqrs'),
    path('pqrs/<int:pqrs_id>/deshacer-traslado/', views.deshacer_traslado_pqrs, name='deshacer_traslado_pqrs'),
    path('pqrs/<int:pqrs_id>/confirmar/', views.confirmar_pqrs, name='confirmar_pqrs'),
  
]

