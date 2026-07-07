from datetime import timedelta

from django import forms
from django.utils import timezone

from .models import Evaluacion, PerfilObjetivo


class EvaluacionForm(forms.ModelForm):
    """Alta de evaluación desde el panel (sin pasar por el Django admin).

    El token lo genera Evaluacion.save(); aquí solo se ajusta la validez en
    horas y se decide si se envía el link por correo."""

    horas_validez = forms.IntegerField(
        initial=48, min_value=1, max_value=720, label="Validez del link (horas)",
        widget=forms.NumberInput(attrs={'class': 'form-input'}))
    enviar_email = forms.BooleanField(
        initial=True, required=False, label="Enviar el link por correo al candidato")

    class Meta:
        model = Evaluacion
        fields = ['nombres', 'cedula', 'correo', 'telefono',
                  'cargo_postulado', 'perfil_objetivo']
        widgets = {
            'nombres': forms.TextInput(attrs={'class': 'form-input'}),
            'cedula': forms.TextInput(attrs={'class': 'form-input'}),
            'correo': forms.EmailInput(attrs={'class': 'form-input'}),
            'telefono': forms.TextInput(attrs={'class': 'form-input'}),
            'cargo_postulado': forms.TextInput(attrs={'class': 'form-input'}),
            'perfil_objetivo': forms.Select(attrs={'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['perfil_objetivo'].queryset = PerfilObjetivo.objects.all()
        self.fields['perfil_objetivo'].required = False

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('enviar_email') and not cleaned.get('correo'):
            self.add_error('correo', "Para enviar el link por correo, el candidato necesita un correo.")
        return cleaned

    def save(self, commit=True):
        evaluacion = super().save(commit=False)
        horas = self.cleaned_data.get('horas_validez') or 48
        evaluacion.fecha_expiracion = timezone.now() + timedelta(hours=horas)
        if commit:
            evaluacion.save()
        return evaluacion
