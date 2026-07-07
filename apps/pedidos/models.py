from django.db import models
from django.contrib.auth.models import User
from apps.catalogo.models import Producto

class Cliente(models.Model):
    # Vinculamos con el sistema nativo de Django para reutilizar la seguridad de contraseñas
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil_cliente')
    telefono = models.CharField(max_length=20, blank=True, null=True)
    
    # CAMBIO: Usar el username que siempre estará poblado y es único
    def __str__(self):
        return self.user.username

class Pedido(models.Model):
    # Tus estados originales se mantienen intactos
    OPCIONES_ESTADO = [
        ('PENDIENTE', 'Pendiente'),
        ('PREPARANDO', 'En Preparación'),
        ('LISTO', 'Listo para Recojo/Envío'),
        ('ENTREGADO', 'Entregado'),
        ('CANCELADO', 'Cancelado (No Show)'), # <-- NUEVO ESTADO
    ]
    
    OPCIONES_FRANJA = [
        ('HOY_MAÑANA', 'Hoy (8:00 AM - 12:00 PM)'),
        ('HOY_TARDE', 'Hoy (12:00 PM - 4:00 PM)'),
        ('HOY_NOCHE', 'Hoy (4:00 PM - 8:00 PM)'),
        ('MAN_MAÑANA', 'Mañana (8:00 AM - 12:00 PM)'),
        ('MAN_TARDE', 'Mañana (12:00 PM - 4:00 PM)'),
        ('MAN_NOCHE', 'Mañana (4:00 PM - 8:00 PM)'),
    ]

    # NUEVO: Modalidades de entrega
    TIPO_ENTREGA = [
        ('RECOJO', 'Recojo en Tienda (Gratis)'),
        ('DELIVERY', 'Delivery a Domicilio (+ S/ 10.00)'),
    ]

    cliente = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pedidos')
    fecha_hora_pedido = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=OPCIONES_ESTADO, default='PENDIENTE')
    
    # NUEVOS CAMPOS DE LOGÍSTICA
    tipo_entrega = models.CharField(max_length=20, choices=TIPO_ENTREGA, default='RECOJO')
    costo_delivery = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    direccion_delivery = models.CharField(max_length=255, blank=True, null=True) 
    
    # MODIFICADO: franja_recojo ahora permite estar en blanco (blank=True, null=True)
    # porque si el cliente elige Delivery, no necesita franja de recojo.
    franja_recojo = models.CharField(max_length=20, choices=OPCIONES_FRANJA, blank=True, null=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Pedido #{self.id} - {self.cliente.username}"

class DetallePedido(models.Model):
    # Esta clase se mantiene exactamente igual a tu original
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.SET_NULL, null=True)
    cantidad = models.PositiveIntegerField()
    precio_unitario_historico = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.cantidad}x {self.producto.nombre if self.producto else 'Producto Eliminado'} (Pedido #{self.pedido.id})"

class Pago(models.Model):
    # NUEVO: Estructura de grupos de Django (optgroups) y nuevas opciones
    OPCIONES_METODO = [
        ('Pago en Línea Segura', (
            ('STRIPE_CARD', 'Tarjeta de Crédito / Débito (Stripe)'),
            ('STRIPE_WALLET', 'Google Pay / Apple Pay / Link (Stripe)'),
        )),
        ('Billeteras Digitales (Simulación)', (
            ('LOCAL_YAPE', 'Yape (Simulación QR/OTP)'), # <-- SEPARADOS
            ('LOCAL_PLIN', 'Plin (Simulación QR/OTP)'),
        )),
        ('Pago Contra Entrega (Físico)', (
            ('CONTRA_EFECTIVO', 'Pago en Efectivo'),
            ('CONTRA_TARJETA', 'Pago con Tarjeta (POS)'),
            ('CONTRA_BILLETERA', 'Pago con Yape/Plin (QR)'),
        )),
    ]

    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='pagos')
    metodo_pago = models.CharField(max_length=50, choices=OPCIONES_METODO)
    monto_pago = models.DecimalField(max_digits=10, decimal_places=2)
    estado_pago = models.CharField(max_length=20, default='PENDIENTE')
    referencia_transaccion = models.CharField(max_length=100, blank=True, null=True)

    # NUEVO: Función de ayuda para que el Panel de Admin de Django 
    # pueda leer correctamente los nombres dentro de los grupos.
    def get_metodo_pago_display_name(self):
        for grupo, opciones in self.OPCIONES_METODO:
            for clave, valor in opciones:
                if self.metodo_pago == clave:
                    return valor
        return self.metodo_pago

    def __str__(self):
        return f"Pago de S/ {self.monto_pago} para Pedido #{self.pedido.id} ({self.get_metodo_pago_display_name()})"