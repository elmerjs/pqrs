# nucleo/models.py
from django.db import models
from django.contrib.auth.models import User
from datetime import date, timedelta
from django.core.mail import send_mail # <-- Importante: añadimos el enviador de correo
from django.conf import settings # <-- Para usar el email remitente de la configuración

# ... (Los modelos CalidadPeticionario y TipoTramite se quedan igual) ...
class CalidadPeticionario(models.Model):
    tipo = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.tipo

class TipoTramite(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    dias_plazo = models.IntegerField(help_text="Plazo en días hábiles para la respuesta")

    def __str__(self):
        return self.nombre
class Pqrs(models.Model):
    ESTADO_CHOICES = [
        ('Recibido', 'Recibido'),
        ('En Trámite', 'En Trámite'),
        ('Resuelto', 'Resuelto'),
    ]

    radicado = models.CharField(max_length=50, unique=True)
    asunto = models.TextField()
    fecha_recepcion_inicial = models.DateField()
    fecha_asignacion = models.DateField(blank=True, null=True)
    fecha_vencimiento = models.DateField(blank=True, null=True)
    respuesta_tramite = models.TextField(blank=True, null=True)
    fecha_respuesta = models.DateField(blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='Recibido')
    
    peticionario_nombre = models.CharField(max_length=255)
    peticionario_email = models.EmailField(blank=True, null=True)
    
    calidad_peticionario = models.ForeignKey(CalidadPeticionario, on_delete=models.SET_NULL, null=True)
    tipo_tramite = models.ForeignKey(TipoTramite, on_delete=models.SET_NULL, null=True)
    responsable = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    __original_responsable = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__original_responsable = self.responsable

    def save(self, *args, **kwargs):
        if not self.pk and self.tipo_tramite:
            dias_a_sumar = self.tipo_tramite.dias_plazo
            fecha_actual = self.fecha_recepcion_inicial
            dias_sumados = 0
            while dias_sumados < dias_a_sumar:
                fecha_actual += timedelta(days=1)
                if fecha_actual.weekday() < 5:
                    dias_sumados += 1
            self.fecha_vencimiento = fecha_actual

        if self.responsable != self.__original_responsable and self.responsable is not None:
            asunto = f"[NUEVA ASIGNACIÓN] Se te ha asignado la PQRS con radicado {self.radicado}"
            mensaje = f"""Hola {self.responsable.first_name},

Se te ha asignado un nuevo caso en el Sistema de Gestión PQRS.

Radicado: {self.radicado}
Asunto: {self.asunto}
Peticionario: {self.peticionario_nombre}
Fecha de Vencimiento: {self.fecha_vencimiento}

Puedes gestionarlo desde el panel de administración.

- Sistema de Gestión PQRS - Vicerrectoría Académica
"""
            try:
                send_mail(asunto, mensaje, settings.EMAIL_HOST_USER, [self.responsable.email])
            except Exception as e:
                print(f"Error enviando correo de asignación: {e}")

        super().save(*args, **kwargs)
        self.__original_responsable = self.responsable

    @property
    def estado_tiempo(self):
        if self.estado == 'Resuelto':
            return "Finalizado"
        
        # Asegurémonos que fecha_vencimiento no sea None
        if not self.fecha_vencimiento:
            return "N/A" # O algún otro valor por defecto

        hoy = date.today()
        dias_restantes = (self.fecha_vencimiento - hoy).days
        
        if dias_restantes < 0:
            return "Vencido"
        elif dias_restantes <= 3:
            return "Por Vencer"
        else:
            return "A Tiempo"

    def __str__(self):
        return f"{self.radicado} - {self.asunto[:50]}"