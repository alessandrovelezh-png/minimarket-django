from rest_framework import serializers
from .models import Pedido, Pago

class CheckoutSerializer(serializers.Serializer):
    # En lugar de un ModelForm, usamos un Serializer para recibir los datos en JSON
    franja_recojo = serializers.ChoiceField(choices=Pedido.OPCIONES_FRANJA)
    metodo_pago = serializers.ChoiceField(choices=Pago.OPCIONES_METODO)