# nucleo/models.py
from django.db import models
from django.contrib.auth.models import User
from datetime import date, timedelta
from django.core.mail import send_mail
from django.conf import settings
# AÑADE ESTAS LÍNEAS - Import para tareas en segundo plano
try:
    from .tasks import enviar_correo_asignacion_pqrs
except ImportError:
    # Fallback para desarrollo si las tasks no están disponibles
    enviar_correo_asignacion_pqrs = None
    
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
    confirmado = models.BooleanField(default=True, help_text="Indica si la PQRS ha sido revisada y confirmada por un coordinador.")
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
        # --- 1. OBTENEMOS EL ESTADO ORIGINAL ANTES DE CUALQUIER CAMBIO ---
        is_new = self.pk is None
        original_pqrs = None
        if not is_new:
            # Obtenemos una sola vez el objeto original para hacer todas las comparaciones
            original_pqrs = Pqrs.objects.get(pk=self.pk)

        # --- 2. LÓGICA QUE SE EJECUTA ANTES DE GUARDAR ---

        # Recalcula la fecha de vencimiento si es un caso nuevo O si cambia el tipo de trámite
        if (is_new or self.tipo_tramite != original_pqrs.tipo_tramite) and self.tipo_tramite:
            dias_a_sumar = self.tipo_tramite.dias_plazo
            fecha_actual = self.fecha_recepcion_inicial
            dias_sumados = 0
            while dias_sumados < dias_a_sumar:
                fecha_actual += timedelta(days=1)
                if fecha_actual.weekday() < 5:
                    dias_sumados += 1
            self.fecha_vencimiento = fecha_actual

        # Asigna la fecha de respuesta si el estado cambia a "Resuelto"
        if not is_new and self.estado == 'Resuelto' and original_pqrs.estado != 'Resuelto':
            self.fecha_respuesta = date.today()

        # Obtenemos el "actor" (el usuario que está realizando la acción) que pasamos desde la vista
        actor = getattr(self, '_actor', None)

        # --- 3. GUARDAMOS EN LA BASE DE DATOS ---
        super().save(*args, **kwargs)

        # --- 4. LÓGICA POST-GUARDADO (CREACIÓN DEL HISTORIAL) ---

        if not is_new:
            from nucleo.models import Seguimiento

            # a. Historial de cambio de estado
            if self.estado != original_pqrs.estado:
                nota = f"El estado del caso cambió de '{original_pqrs.estado}' a '{self.estado}'."
                Seguimiento.objects.create(pqrs=self, nota=nota, autor=actor)

            # b. Historial de cambio de responsable (y envío de correo)
            if self.responsable != original_pqrs.responsable and self.responsable is not None:
                nota = f"Caso asignado al abogado: {self.responsable.get_full_name()}."
                Seguimiento.objects.create(pqrs=self, nota=nota, autor=actor)
                
                if enviar_correo_asignacion_pqrs:
                    # Tu lógica para agendar el correo...
                    try:
                        enviar_correo_asignacion_pqrs(self.radicado, self.responsable.id, self.id, schedule=5)
                        print(f"📧 Tarea de correo programada para PQRS {self.radicado}")
                    except Exception as e:
                        print(f"❌ Error programando tarea de correo: {e}")

            # --- ¡AQUÍ ESTÁ LA NUEVA LÓGICA! ---
            # c. Historial de cambio de otros campos clave
            if self.asunto != original_pqrs.asunto:
                nota = "Se modificó el asunto del caso."
                Seguimiento.objects.create(pqrs=self, nota=nota, autor=actor)
            
            if self.fecha_vencimiento != original_pqrs.fecha_vencimiento:
                nota = f"La fecha de vencimiento cambió de '{original_pqrs.fecha_vencimiento}' a '{self.fecha_vencimiento}'."
                Seguimiento.objects.create(pqrs=self, nota=nota, autor=actor)

            if self.tipo_tramite != original_pqrs.tipo_tramite:
                nota = f"El tipo de trámite cambió de '{original_pqrs.tipo_tramite}' a '{self.tipo_tramite}'."
                Seguimiento.objects.create(pqrs=self, nota=nota, autor=actor)
            # --- FIN DE LA NUEVA LÓGICA ---
            if self.confirmado and not original_pqrs.confirmado:
                            nota = "La PQRS fue confirmada y sus datos validados por el coordinador."
                            Seguimiento.objects.create(pqrs=self, nota=nota, autor=actor)

        # Finalmente, actualizamos el responsable original para la próxima vez
        self.__original_responsable = self.responsable

    def _enviar_correo_sincrono(self):
        """
        Método de fallback para enviar correo sincrónicamente
        si falla la tarea en segundo plano
        """
        try:
            # Construir el enlace al caso
            enlace_caso = f"http://192.168.42.175:8000/pqrs/{self.id}/"
            
            asunto = f"[NUEVA ASIGNACIÓN] Se te ha asignado la PQRS con radicado {self.radicado}"
            mensaje = f"""Hola {self.responsable.first_name},

    Se te ha asignado un nuevo caso en el Sistema de Gestión PQRS.

    Detalles del caso:
    - Radicado: {self.radicado}

    Puedes acceder al caso a través del siguiente enlace:
    {enlace_caso}

    Por favor, inicia el trámite correspondiente en el sistema.

    Saludos,
    Sistema de Gestión PQRS
    """
            send_mail(asunto, mensaje, settings.EMAIL_HOST_USER, [self.responsable.email])
            print(f"✅ Correo enviado sincrónicamente a {self.responsable.email}")
        except Exception as e:
            print(f"❌ Error enviando correo sincrónicamente: {e}")
    
    def get_estado_tiempo(self):
            if self.estado == 'Resuelto':
                return "Finalizado"
            if not self.fecha_vencimiento:
                return "N/A"
            
            # Asegúrate de que 'date' está importado al principio del archivo: from datetime import date
            hoy = date.today()
            
            dias_restantes = (self.fecha_vencimiento - hoy).days
            if dias_restantes < 0:
                return "Vencido"
            elif dias_restantes <= 3:
                return "Por Vencer"
            else:
                return "A Tiempo"
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
        # Comprueba si existe un autor. Si no, usa la palabra "Sistema".
        autor_texto = self.autor.username if self.autor else "Sistema"
        return f"Seguimiento en {self.pqrs.radicado} por {autor_texto}"