# nucleo/forms.py
from django import forms
from .models import Pqrs, User, ArchivoAdjunto
from datetime import date
#from .models import Pqrs, ArchivoAdjunto # <-- Modifica esta línea

class PqrsForm(forms.ModelForm):
    class Meta:
        model = Pqrs
        fields = [
            'radicado', 'asunto', 'fecha_recepcion_inicial', 'peticionario_nombre',
            'peticionario_email', 'calidad_peticionario', 'tipo_tramite',
            'responsable', 'estado', 'respuesta_tramite',
        ]
        labels = {
            'fecha_recepcion_inicial': 'Fecha de Recepción',
            'peticionario_nombre': 'Nombre del Peticionario',
            'peticionario_email': 'Email del Peticionario',
            'calidad_peticionario': 'Calidad del Peticionario',
            'tipo_tramite': 'Tipo de Trámite',
            'respuesta_tramite': 'Respuesta al Trámite',
        }
        widgets = {
            'asunto': forms.Textarea(attrs={'rows': 3}),
            'respuesta_tramite': forms.Textarea(attrs={'rows': 5}),
        }

class AbogadoPqrsForm(forms.ModelForm):
    class Meta:
        model = Pqrs
        fields = ['estado', 'respuesta_tramite']
        labels = {
            'estado': 'Cambiar Estado del Trámite',
            'respuesta_tramite': 'Respuesta al Trámite (Borrador)',
        }
        widgets = {
            'respuesta_tramite': forms.Textarea(attrs={'rows': 5}),
        }

class PqrsFilterForm(forms.Form):
    # 1. Todos los campos se definen primero
    YEAR_CHOICES = [(str(y), str(y)) for y in range(date.today().year, 2020, -1)]

    q = forms.CharField(
        label='Buscar por Radicado o Asunto', required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Escriba aquí...'})
    )
    
    vigencia = forms.ChoiceField(
        choices=[('', 'Año Actual')] + YEAR_CHOICES, required=False,
        label='Vigencia'
    )

    responsable = forms.ModelChoiceField(
        queryset=User.objects.filter(groups__name__in=['Abogados', 'Coordinadores']),
        required=False, label='Responsable'
    )
    
    estado = forms.ChoiceField(
        choices=[('', 'Todos los Estados')] + Pqrs.ESTADO_CHOICES,
        required=False, label='Estado'
    )

    # 2. La función __init__ va después de los campos y DEBE estar indentada
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Si el usuario es un abogado, deshabilitamos y pre-seleccionamos el filtro de responsable
        if user and user.groups.filter(name='Abogados').exists() and not user.groups.filter(name='Coordinadores').exists():
            self.fields['responsable'].disabled = True
            self.fields['responsable'].queryset = User.objects.filter(pk=user.pk)
            self.fields['responsable'].initial = user

# nucleo/forms.py

# ... (tus otros formularios PqrsForm, etc., se quedan igual) ...

# --- AÑADE ESTE NUEVO FORMULARIO AL FINAL ---
# nucleo/forms.py
class ArchivoAdjuntoForm(forms.ModelForm):
    class Meta:
        model = ArchivoAdjunto
        # --- AÑADE 'tipo_archivo' A LA LISTA ---
        fields = ['archivo', 'descripcion', 'tipo_archivo']
        widgets = {
            'descripcion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Descripción breve del archivo'}),
            'archivo': forms.FileInput(attrs={'class': 'form-control'}),
            # --- AÑADE EL WIDGET PARA EL NUEVO CAMPO ---
            'tipo_archivo': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'descripcion': 'Descripción',
            'archivo': 'Seleccionar archivo',
            # --- AÑADE LA ETIQUETA PARA EL NUEVO CAMPO ---
            'tipo_archivo': 'Tipo de Archivo',
        }

# --- AÑADE ESTE NUEVO FORMULARIO ---
class PdfUploadForm(forms.Form):
    pdf_file = forms.FileField(
        label="Seleccionar PDF de la queja",
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf'})
    )