# nucleo/admin.py
from django.contrib import admin
from .models import CalidadPeticionario, TipoTramite, Pqrs
from datetime import date # Importamos la herramienta de fecha

class PqrsAdmin(admin.ModelAdmin):
    list_display = (
        'radicado',
        'asunto',
        'responsable',
        'fecha_vencimiento',
        'estado',
        'estado_tiempo',
    )
    list_filter = ('estado', 'responsable', 'tipo_tramite')
    search_fields = ('radicado', 'asunto', 'peticionario_nombre')
    date_hierarchy = 'fecha_vencimiento'

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

    # --- ¡NUEVA LÓGICA DE AUTOMATIZACIÓN DE ESTADO! ---
    def change_view(self, request, object_id, form_url="", extra_context=None):
        # Obtenemos el objeto (la PQRS) que se está abriendo
        obj = self.get_object(request, object_id)

        # Si el estado actual es "Recibido"...
        if obj and obj.estado == 'Recibido':
            # ...lo cambiamos a "En Trámite".
            obj.estado = 'En Trámite'
            # Y si no tiene fecha de asignación, le ponemos la de hoy.
            if not obj.fecha_asignacion:
                obj.fecha_asignacion = date.today()
            obj.save() # Guardamos los cambios

        # Dejamos que Django continúe y muestre la página de edición normalmente
        return super().change_view(request, object_id, form_url, extra_context)


admin.site.register(CalidadPeticionario)
admin.site.register(TipoTramite)
admin.site.register(Pqrs, PqrsAdmin)