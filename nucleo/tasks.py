# nucleo/tasks.py
from background_task import background
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User

@background(schedule=5)
def enviar_correo_asignacion_pqrs(pqrs_radicado, responsable_id, pqrs_id):  # ← 3 PARÁMETROS
    """
    Tarea en segundo plano para enviar correo de asignación de PQRS
    """
    try:
        # Obtener el responsable
        responsable = User.objects.get(id=responsable_id)
        
        # Construir el enlace al caso
        enlace_caso = f"http://192.168.42.175:8000/pqrs/{pqrs_id}/"
        
        asunto = f"[NUEVA ASIGNACIÓN] Se te ha asignado la PQRS {pqrs_radicado}"
        mensaje = f"""Hola {responsable.first_name},

Se te ha asignado un nuevo caso en el Sistema de Gestión PQRS.

📋 **Detalles del caso:**
- **Radicado:** {pqrs_radicado}
- **Enlace directo:** {enlace_caso}

🔗 **Acción requerida:**
Por favor, accede al sistema a través del enlace anterior para revisar el caso e iniciar el trámite correspondiente.

Saludos,
Sistema de Gestión PQRS
"""
        
        send_mail(
            asunto,
            mensaje,
            settings.DEFAULT_FROM_EMAIL,
            [responsable.email],
            fail_silently=False,
        )
        
        print(f"✅ Correo de asignación enviado a {responsable.email}")
        print(f"🔗 Enlace incluido: {enlace_caso}")
        
    except User.DoesNotExist:
        print(f"❌ Error: Usuario con ID {responsable_id} no existe")
    except Exception as e:
        print(f"❌ Error enviando correo: {e}")