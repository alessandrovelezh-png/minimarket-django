from django import forms
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