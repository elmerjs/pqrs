# nucleo/forms.py
from django import forms
from .models import Pqrs, User
from datetime import date

class PqrsForm(forms.ModelForm):
    class Meta:
        model = Pqrs
        fields = [
            'radicado',
            'asunto',
            'fecha_recepcion_inicial',
            'peticionario_nombre',
            'peticionario_email',
            'calidad_peticionario',
            'tipo_tramite',
            'responsable',
        ]
        labels = {
            'fecha_recepcion_inicial': 'Fecha de Recepción',
            'peticionario_nombre': 'Nombre del Peticionario',
            'peticionario_email': 'Email del Peticionario',
            'calidad_peticionario': 'Calidad del Peticionario',
            'tipo_tramite': 'Tipo de Trámite',
        }


# --- AÑADE ESTE NUEVO FORMULARIO PARA FILTROS ---
class PqrsFilterForm(forms.Form):
    # Generamos una lista de años dinámicamente
    YEAR_CHOICES = [(str(y), str(y)) for y in range(date.today().year, 2020, -1)]

    q = forms.CharField(
        label='Buscar por Radicado o Asunto',
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Escriba aquí...'})
    )

    # --- ¡NUEVO CAMPO! ---
    vigencia = forms.ChoiceField(
        choices=[('', 'Año Actual')] + YEAR_CHOICES, # La opción por defecto será el año actual
        required=False,
        label='Vigencia'
    )

    responsable = forms.ModelChoiceField(
        queryset=User.objects.filter(groups__name__in=['Abogados', 'Coordinadores']),
        required=False,
        label='Responsable'
    )

    estado = forms.ChoiceField(
        choices=[('', 'Todos los Estados')] + Pqrs.ESTADO_CHOICES,
        required=False,
        label='Estado'
    )