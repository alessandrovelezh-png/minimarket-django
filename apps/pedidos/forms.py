from django import forms
from django.utils import timezone
import datetime
from .models import Pedido, Pago

class CheckoutForm(forms.ModelForm):
    tipo_entrega = forms.ChoiceField(
        choices=Pedido.TIPO_ENTREGA, 
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    metodo_pago = forms.ChoiceField(
        choices=Pago.OPCIONES_METODO, 
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    class Meta:
        model = Pedido
        fields = ['tipo_entrega', 'direccion_delivery', 'franja_recojo', 'metodo_pago']
        widgets = {
            'direccion_delivery': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Av. Javier Prado 1234, Lima'}),
            'franja_recojo': forms.Select(attrs={'class': 'form-select'}),
        }
        
    # NUEVO: Lógica dinámica de horarios
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        hora_actual = timezone.localtime().time()
        hora_tarde = datetime.time(12, 0)
        hora_noche = datetime.time(16, 0)
        hora_cierre = datetime.time(20, 0)
        
        opciones = []
        if hora_actual < hora_tarde:
            opciones = [
                ('HOY_MAÑANA', 'Hoy - Mañana (8:00 AM - 12:00 PM)'),
                ('HOY_TARDE', 'Hoy - Tarde (12:00 PM - 4:00 PM)'),
                ('HOY_NOCHE', 'Hoy - Noche (4:00 PM - 8:00 PM)')
            ]
        elif hora_tarde <= hora_actual < hora_noche:
            opciones = [
                ('HOY_TARDE', 'Hoy - Tarde (12:00 PM - 4:00 PM)'),
                ('HOY_NOCHE', 'Hoy - Noche (4:00 PM - 8:00 PM)'),
                ('MAN_MAÑANA', 'Mañana - Mañana (8:00 AM - 12:00 PM)')
            ]
        elif hora_noche <= hora_actual < hora_cierre:
            opciones = [
                ('HOY_NOCHE', 'Hoy - Noche (4:00 PM - 8:00 PM)'),
                ('MAN_MAÑANA', 'Mañana - Mañana (8:00 AM - 12:00 PM)'),
                ('MAN_TARDE', 'Mañana - Tarde (12:00 PM - 4:00 PM)')
            ]
        else:
            opciones = [
                ('MAN_MAÑANA', 'Mañana - Mañana (8:00 AM - 12:00 PM)'),
                ('MAN_TARDE', 'Mañana - Tarde (12:00 PM - 4:00 PM)'),
                ('MAN_NOCHE', 'Mañana - Noche (4:00 PM - 8:00 PM)')
            ]
            
        self.fields['franja_recojo'].choices = opciones