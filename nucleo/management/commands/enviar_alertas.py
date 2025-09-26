from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User
from nucleo.models import Pqrs
from datetime import date, timedelta

class Command(BaseCommand):
    help = 'Busca PQRS próximas a vencer (<= 3 días) y envía alertas por correo.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Iniciando la búsqueda de PQRS por vencer...'))

        # 1. Definimos el rango de fechas para "Por Vencer"
        hoy = date.today()
        fecha_limite = hoy + timedelta(days=3)

        # 2. Buscamos las PQRS que están en el rango y no están resueltas/anuladas
        pqrs_por_vencer = Pqrs.objects.filter(
            fecha_vencimiento__gte=hoy,
            fecha_vencimiento__lte=fecha_limite,
            estado__in=['Recibido', 'En Trámite']
        )

        if not pqrs_por_vencer.exists():
            self.stdout.write(self.style.SUCCESS('No se encontraron PQRS próximas a vencer.'))
            return

        # 3. Obtenemos los correos de todos los coordinadores una sola vez
        try:
            coordinadores = User.objects.filter(groups__name='Coordinadores')
            emails_coordinadores = [c.email for c in coordinadores if c.email]
        except Exception:
            self.stdout.write(self.style.WARNING('No se pudo encontrar el grupo "Coordinadores". No se enviarán copias.'))
            emails_coordinadores = []

        # 4. Recorremos cada PQRS encontrada y enviamos la alerta
        contador_enviados = 0
        for pqrs in pqrs_por_vencer:
            if not pqrs.responsable or not pqrs.responsable.email:
                self.stdout.write(self.style.WARNING(f'PQRS {pqrs.radicado}: No tiene responsable con email. Se omite.'))
                continue

            # Preparamos la lista de destinatarios (el abogado + copia a coordinadores)
            destinatarios = list(set([pqrs.responsable.email] + emails_coordinadores))

            # Redactamos el correo
            asunto = f"[ALERTA POR VENCER] La PQRS {pqrs.radicado} vence en {(pqrs.fecha_vencimiento - hoy).days} día(s)"
            mensaje = f"""
Hola,

Este es un recordatorio automático del Sistema de Gestión PQRS.
El siguiente caso está próximo a su fecha de vencimiento:

- Radicado: {pqrs.radicado}
- Asunto: {pqrs.asunto}
- Responsable: {pqrs.responsable.get_full_name()}
- Fecha de Vencimiento: {pqrs.fecha_vencimiento.strftime('%d de %B de %Y')}

Por favor, asegúrese de gestionarlo a la brevedad.

- Sistema de Gestión PQRS - Vicerrectoría Académica
"""
            # Enviamos el correo
            try:
                send_mail(
                    asunto,
                    mensaje,
                    settings.EMAIL_HOST_USER,  # El remitente (configurado en settings.py)
                    destinatarios,
                    fail_silently=False,
                )
                self.stdout.write(self.style.SUCCESS(f'Alerta para PQRS {pqrs.radicado} enviada a: {", ".join(destinatarios)}'))
                contador_enviados += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Error enviando correo para PQRS {pqrs.radicado}: {e}'))

        self.stdout.write(self.style.SUCCESS(f'Proceso finalizado. Se enviaron {contador_enviados} alertas.'))