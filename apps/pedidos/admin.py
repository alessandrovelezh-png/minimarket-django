from django.contrib import admin
from .models import Pedido, DetallePedido, Pago, Cliente

# Register your models here.

# Mostrar el detalle dentro del pedido
class DetallePedidoInline(admin.TabularInline):
    model = DetallePedido
    extra = 0
    readonly_fields = ['producto', 'cantidad', 'precio_unitario_historico']

@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'fecha_hora_pedido', 'estado', 'franja_recojo', 'total')
    list_filter = ('estado', 'franja_recojo', 'fecha_hora_pedido')
    search_fields = ('cliente__username',)
    list_editable = ('estado',) # ¡Esto permite cambiar el estado rápido desde la lista! (HU15)
    inlines = [DetallePedidoInline]

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    # Mostramos columnas claras para que no salgan campos vacíos
    list_display = ('obtener_username', 'obtener_email', 'telefono')
    search_fields = ('user__username', 'user__email', 'telefono')

    def obtener_username(self, obj):
        return obj.user.username
    obtener_username.short_description = 'Usuario'

    def obtener_email(self, obj):
        return obj.user.email
    obtener_email.short_description = 'Correo Electrónico'
    
@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    # Usamos una función personalizada ('mostrar_metodo_pago') en lugar del campo directo
    list_display = ('pedido', 'mostrar_metodo_pago', 'monto_pago', 'estado_pago', 'referencia_transaccion')
    list_filter = ('metodo_pago', 'estado_pago')

    # Esta función obliga a Django a traducir la clave interna ('STRIPE') a su versión legible
    def mostrar_metodo_pago(self, obj):
        return obj.get_metodo_pago_display()
    mostrar_metodo_pago.short_description = 'Método de Pago'