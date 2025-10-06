# nucleo/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Pqrs, Seguimiento
from .google_sheets_service import update_pqrs_sheet

@receiver(post_save, sender=Pqrs)
def pqrs_saved_handler(sender, instance, created, **kwargs):
    """
    Se dispara al guardar una PQRS.
    - Si es nueva, crea la nota de seguimiento inicial.
    - Siempre agenda la actualización de Google Sheets.
    """
    if created:
        # Esta lógica solo se ejecuta al crear la PQRS
        autor_accion = getattr(instance, '_creador', None)
        fecha_hora_creacion = timezone.localtime(instance.created_at).strftime('%d de %b de %Y a las %I:%M %p')
        nota_automatica = f"Caso cargado al sistema el {fecha_hora_creacion}."
        
        Seguimiento.objects.create(
            pqrs=instance,
            nota=nota_automatica,
            autor=autor_accion
        )

    # --- ¡ESTA ES LA CORRECCIÓN! ---
    # Estas dos líneas están FUERA del 'if' y se ejecutan siempre.
    update_pqrs_sheet(instance.id)
    
    print(f"Tarea para actualizar Google Sheets (PQRS ID: {instance.id}) ha sido agendada.")