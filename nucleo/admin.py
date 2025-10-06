# nucleo/admin.py
from django.contrib import admin
from .models import CalidadPeticionario, TipoTramite, Pqrs
from datetime import date

class PqrsAdmin(admin.ModelAdmin):
    list_display = (
        'radicado',
        'asunto',
        'responsable',
        'fecha_vencimiento',
        'estado',
        'estado_tiempo_display',  # CAMBIA ESTA LÍNEA
    )
    list_filter = ('estado', 'responsable', 'tipo_tramite')
    search_fields = ('radicado', 'asunto', 'peticionario_nombre')
    date_hierarchy = 'fecha_vencimiento'

    # AÑADE ESTE MÉTODO
    def estado_tiempo_display(self, obj):
        return obj.get_estado_tiempo() # <-- CORRECCIÓN AQUÍ
    estado_tiempo_display.short_description = 'Estado Tiempo'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser or request.user.groups.filter(name="Coordinadores").exists():
            return qs
        if request.user.groups.filter(name="Abogados").exists():
            return qs.filter(responsable=request.user)
        return qs.none()

    def get_readonly_fields(self, request, obj=None):
        if request.user.groups.filter(name="Abogados").exists():
            return [
                'radicado', 'fecha_recepcion_inicial', 'fecha_asignacion',
                'fecha_vencimiento', 'peticionario_nombre', 'peticionario_email',
                'calidad_peticionario', 'tipo_tramite', 'responsable'
            ]
        return []

    def change_view(self, request, object_id, form_url="", extra_context=None):
        obj = self.get_object(request, object_id)
        if obj and obj.estado == 'Recibido':
            obj.estado = 'En Trámite'
            if not obj.fecha_asignacion:
                obj.fecha_asignacion = date.today()
            obj.save()
        return super().change_view(request, object_id, form_url, extra_context)

admin.site.register(CalidadPeticionario)
admin.site.register(TipoTramite)
admin.site.register(Pqrs, PqrsAdmin)