# nucleo/management/commands/enviar_alertas.py

from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User
from django.urls import reverse
from nucleo.models import Pqrs

class Command(BaseCommand):
    help = 'Busca PQRS próximas a vencer (<= 3 días) y envía alertas por correo.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Iniciando la búsqueda de PQRS por vencer...'))

        # --- MEJORA 1: Definimos la URL base de tu aplicación ---
        BASE_URL = "http://192.168.42.175:8000"

        # La búsqueda de PQRS se mantiene igual
        hoy = date.today()
        fecha_limite = hoy + timedelta(days=3)
        pqrs_por_vencer = Pqrs.objects.filter(
            fecha_vencimiento__gte=hoy,
            fecha_vencimiento__lte=fecha_limite,
            estado__in=['Recibido', 'En Trámite']
        )

        if not pqrs_por_vencer.exists():
            self.stdout.write(self.style.SUCCESS('No se encontraron PQRS próximas a vencer.'))
            return

        # Obtenemos los correos de los coordinadores (esto no cambia)
        try:
            coordinadores = User.objects.filter(groups__name='Coordinadores')
            emails_coordinadores = [c.email for c in coordinadores if c.email]
        except Exception:
            self.stdout.write(self.style.WARNING('No se pudo encontrar el grupo "Coordinadores".'))
            emails_coordinadores = []

        if not emails_coordinadores:
            self.stdout.write(self.style.WARNING('No hay coordinadores con email configurado para enviar alertas.'))

        # --- MEJORA 2: Lógica separada para casos asignados y no asignados ---
        contador_enviados = 0
        for pqrs in pqrs_por_vencer:
            
            url_caso = f"{BASE_URL}{reverse('detalle_pqrs', args=[pqrs.id])}"
            dias_restantes = (pqrs.fecha_vencimiento - hoy).days
            
            # CASO A: La PQRS TIENE un responsable asignado
            if pqrs.responsable and pqrs.responsable.email:
                asunto = f"[ALERTA POR VENCER] PQRS {pqrs.radicado} vence en {dias_restantes} día(s)"
                mensaje = f"""
Hola {pqrs.responsable.first_name or pqrs.responsable.username},

Este es un recordatorio automático. El siguiente caso está próximo a su fecha de vencimiento:

- Radicado: {pqrs.radicado}
- Fecha de Vencimiento: {pqrs.fecha_vencimiento.strftime('%d de %B de %Y')}
- Estado Actual: {pqrs.estado}

Para gestionarlo, por favor haz clic en el siguiente enlace:
{url_caso}

- Sistema de Gestión PQRS
"""
                # El destinatario es el abogado, con copia a los coordinadores
                destinatarios = list(set([pqrs.responsable.email] + emails_coordinadores))
                
            # CASO B: La PQRS NO TIENE responsable asignado
            else:
                asunto = f"[ALERTA URGENTE] PQRS {pqrs.radicado} sin asignar y próxima a vencer"
                mensaje = f"""
Hola Coordinadores,

Este es un recordatorio automático. El siguiente caso está próximo a vencer y AÚN NO TIENE UN RESPONSABLE ASIGNADO:

- Radicado: {pqrs.radicado}
- Fecha de Vencimiento: {pqrs.fecha_vencimiento.strftime('%d de %B de %Y')} ({dias_restantes} día(s) restantes)
- Peticionario: {pqrs.peticionario_nombre}

Es urgente asignar un responsable para gestionar este caso a la brevedad.

Para ver y asignar el caso, por favor haz clic en el siguiente enlace:
{url_caso}

- Sistema de Gestión PQRS
"""
                # Los destinatarios son ÚNICAMENTE los coordinadores
                destinatarios = emails_coordinadores

            # Lógica de envío (ahora es común para ambos casos)
            if not destinatarios:
                self.stdout.write(self.style.WARNING(f'PQRS {pqrs.radicado}: No hay destinatarios para enviar la alerta.'))
                continue

            try:
                send_mail(asunto, mensaje, settings.EMAIL_HOST_USER, destinatarios, fail_silently=False)
                self.stdout.write(self.style.SUCCESS(f'Alerta para PQRS {pqrs.radicado} enviada a: {", ".join(destinatarios)}'))
                contador_enviados += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Error enviando correo para PQRS {pqrs.radicado}: {e}'))

        self.stdout.write(self.style.SUCCESS(f'Proceso finalizado. Se enviaron {contador_enviados} alertas.'))