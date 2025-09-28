# nucleo/models.py
from django.db import models
from django.contrib.auth.models import User
from datetime import date, timedelta
from django.core.mail import send_mail
from django.conf import settings

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
     ('Anulado', 'Anulado'), # <-- AÑADE ESTA LÍNEA

    ]

    radicado = models.CharField(max_length=50, unique=True)
    asunto = models.TextField()
    fecha_recepcion_inicial = models.DateField()
    fecha_asignacion = models.DateField(blank=True, null=True)
    fecha_vencimiento = models.DateField(blank=True, null=True)
    respuesta_tramite = models.TextField(blank=True, null=True)
    fecha_respuesta = models.DateField(blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='Recibido')
    fecha_cierre = models.DateField(null=True, blank=True, verbose_name="Fecha de Cierre Definitivo")
    ESTADOS_TRASLADO = (
        ('Activo', 'Activo en Vicerrectoría'),
        ('En Traslado', 'En Traslado a Otra Dependencia'),
    )
    estado_traslado = models.CharField(max_length=20, choices=ESTADOS_TRASLADO, default='Activo')
    dependencia_trasladada = models.CharField(max_length=255, blank=True, null=True, verbose_name="Dependencia a la que se traslada")
    # --- FIN DEL BLOQUE ---
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
        original_estado = None
        if self.pk:
            original_estado = Pqrs.objects.get(pk=self.pk).estado

        if not self.pk and self.tipo_tramite:
            dias_a_sumar = self.tipo_tramite.dias_plazo
            fecha_actual = self.fecha_recepcion_inicial
            dias_sumados = 0
            while dias_sumados < dias_a_sumar:
                fecha_actual += timedelta(days=1)
                if fecha_actual.weekday() < 5:
                    dias_sumados += 1
            self.fecha_vencimiento = fecha_actual

        if self.estado == 'Resuelto' and original_estado != 'Resuelto':
            self.fecha_respuesta = date.today()

        if self.responsable != self.__original_responsable and self.responsable is not None:
            asunto = f"[NUEVA ASIGNACIÓN] Se te ha asignado la PQRS con radicado {self.radicado}"
            mensaje = f"Hola {self.responsable.first_name},\n\nSe te ha asignado un nuevo caso en el Sistema de Gestión PQRS..."
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
        if not self.fecha_vencimiento:
            return "N/A"
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
    

# nucleo/models.py
class ArchivoAdjunto(models.Model):
    # Opciones para el tipo de archivo
    TIPO_PETICIONARIO = 'PETICIONARIO'
    TIPO_INTERNO = 'INTERNO'
    TIPO_CHOICES = [
        (TIPO_INTERNO, 'Documento de Soporte Interno'),
        (TIPO_PETICIONARIO, 'Anexo del Peticionario'),
    ]

    pqrs = models.ForeignKey(Pqrs, on_delete=models.CASCADE, related_name='adjuntos')
    archivo = models.FileField(upload_to='adjuntos_pqrs/')
    fecha_carga = models.DateTimeField(auto_now_add=True)
    descripcion = models.CharField(max_length=255, blank=True, null=True, help_text="Ej: Cédula, Derecho de petición, etc.")

    # --- NUEVO CAMPO ---
    tipo_archivo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default=TIPO_INTERNO,
    )

    def __str__(self):
        return self.archivo.name.split('/')[-1]

    @property
    def nombre_corto(self):
        return self.archivo.name.split('/')[-1]
    # nucleo/models.py

class Seguimiento(models.Model):
    pqrs = models.ForeignKey(Pqrs, on_delete=models.CASCADE, related_name='seguimientos')
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    nota = models.TextField(verbose_name="Nota de Seguimiento")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_creacion'] # Muestra los más recientes primero

    def __str__(self):
        return f"Seguimiento en {self.pqrs.radicado} por {self.autor.username}"