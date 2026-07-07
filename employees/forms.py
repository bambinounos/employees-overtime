from django import forms

from .models import SolicitudAusencia, TipoAusencia


class SolicitudAusenciaForm(forms.ModelForm):
    """Formulario de solicitud de ausencia para el empleado autenticado.

    El employee no es campo del form: lo fija la vista desde request.user
    para que nadie pueda solicitar a nombre de otro."""

    class Meta:
        model = SolicitudAusencia
        fields = ['tipo', 'fecha_inicio', 'fecha_fin', 'motivo']
        widgets = {
            'fecha_inicio': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'fecha_fin': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'motivo': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, employee=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.employee = employee
        self.fields['tipo'].queryset = TipoAusencia.objects.filter(activo=True)
        self.fields['tipo'].widget.attrs['class'] = 'form-control'

    def clean(self):
        cleaned = super().clean()
        # clean() del modelo valida solapamientos; necesita employee asignado
        if self.employee is not None:
            self.instance.employee = self.employee
        return cleaned
