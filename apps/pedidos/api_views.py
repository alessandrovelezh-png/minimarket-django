import uuid
import stripe # NUEVO
from django.conf import settings # NUEVO
from django.urls import reverse # NUEVO
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from apps.catalogo.models import Producto
from .models import Pedido, DetallePedido, Pago
from .carrito import Carrito
from .serializers import CheckoutSerializer

# NUEVO: Configuramos la clave secreta de Stripe para la API
stripe.api_key = settings.STRIPE_SECRET_KEY

# ==========================================
# 1. API DEL CARRITO DE COMPRAS
# ==========================================
@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([AllowAny]) # Permitimos ver el carrito sin login temporalmente
def api_carrito(request):
    carrito = Carrito(request)

    # Ver el carrito (GET)
    if request.method == 'GET':
        return Response({
            'items': carrito.carrito,
            'total_general': carrito.get_total_carrito()
        })

    # Agregar/Sumar producto (POST)
    elif request.method == 'POST':
        producto_id = request.data.get('producto_id')
        if not producto_id:
            return Response({'error': 'Falta el ID del producto'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            producto = Producto.objects.get(id=producto_id)
            carrito.agregar(producto)
            return Response({'mensaje': f'{producto.nombre} agregado al carrito', 'total': carrito.get_total_carrito()})
        except Producto.DoesNotExist:
            return Response({'error': 'Producto no encontrado'}, status=status.HTTP_404_NOT_FOUND)

    # Eliminar producto (DELETE)
    elif request.method == 'DELETE':
        producto_id = request.data.get('producto_id')
        try:
            producto = Producto.objects.get(id=producto_id)
            carrito.eliminar(producto)
            return Response({'mensaje': 'Producto eliminado'})
        except Producto.DoesNotExist:
            return Response({'error': 'Producto no encontrado'}, status=status.HTTP_404_NOT_FOUND)


# ==========================================
# 2. API DEL CHECKOUT (PAGO)
# ==========================================
@api_view(['POST'])
@permission_classes([IsAuthenticated]) # SOLO usuarios logueados pueden procesar el pago
def api_checkout(request):
    carrito = Carrito(request)
    
    if not carrito.carrito:
        return Response({'error': 'El carrito está vacío'}, status=status.HTTP_400_BAD_REQUEST)

    # Validamos los datos JSON enviados por el cliente
    serializer = CheckoutSerializer(data=request.data)
    if serializer.is_valid():
        metodo_seleccionado = serializer.validated_data['metodo_pago']
        franja_recojo = serializer.validated_data['franja_recojo']

        # ========================================================
        # BIFURCACIÓN DE PAGOS: STRIPE VS SIMULACIÓN EN LA API
        # ========================================================
        # CAMBIO 1: Comparamos usando las nuevas claves agrupadas
        if metodo_seleccionado in ['STRIPE_CARD', 'STRIPE_WALLET']:
            
            # CAMBIO 2: Guardamos 'metodo_pago' en la sesión temporalmente
            request.session['datos_pedido_pendiente'] = {
                'franja_recojo': franja_recojo,
                'metodo_pago': metodo_seleccionado, 
            }

            # Construimos la lista de productos (line_items) para Stripe
            line_items = []
            for key, item in carrito.carrito.items():
                line_items.append({
                    'price_data': {
                        'currency': 'pen', # Moneda en Soles
                        'unit_amount': int(float(item['precio']) * 100), # Centavos
                        'product_data': {
                            'name': item['nombre'],
                        },
                    },
                    'quantity': item['cantidad'],
                })

            try:
                # Construimos las URLs de retorno
                success_url = request.build_absolute_uri(reverse('pedidos:stripe_success'))
                cancel_url = request.build_absolute_uri(reverse('pedidos:stripe_cancel'))

                # Creamos la sesión en los servidores de Stripe
                checkout_session = stripe.checkout.Session.create(
                    # CAMBIO 3: Añadimos 'link' para habilitar las billeteras digitales
                    payment_method_types=['card', 'link'],
                    line_items=line_items,
                    mode='payment',
                    success_url=success_url,
                    cancel_url=cancel_url,
                )

                # La API responde con la URL para que el frontend haga la redirección
                return Response({
                    'mensaje': 'Sesión de pago iniciada. Redirige al cliente a la URL proporcionada.',
                    'stripe_url': checkout_session.url
                }, status=status.HTTP_200_OK)

            except Exception as e:
                return Response({'error': f"Error conectando con Stripe: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        else:
            # --- FLUJO DE PAGO SIMULADO LOCAL (Yape, Plin, Efectivo, Transferencia) ---
            try:
                with transaction.atomic():
                    pedido = Pedido.objects.create(
                        cliente=request.user,
                        estado='PENDIENTE',
                        franja_recojo=franja_recojo,
                        total=0
                    )

                    total_calculado = 0
                    for key, item in carrito.carrito.items():
                        producto = Producto.objects.get(id=item['producto_id'])
                        cantidad_comprada = item['cantidad']

                        # Descuento del stock (Overbooking defensivo)
                        producto.stock = max(0, producto.stock - cantidad_comprada)
                        producto.stock_reservado = max(0, producto.stock_reservado - cantidad_comprada)
                        producto.save()

                        precio_unitario = float(item['precio'])
                        DetallePedido.objects.create(
                            pedido=pedido, producto=producto,
                            cantidad=cantidad_comprada, precio_unitario_historico=precio_unitario
                        )
                        total_calculado += (precio_unitario * cantidad_comprada)

                    pedido.total = total_calculado
                    pedido.save()

                    Pago.objects.create(
                        pedido=pedido, 
                        metodo_pago=metodo_seleccionado, # Automáticamente guardará LOCAL_YAPE, LOCAL_EFECTIVO, etc.
                        monto_pago=total_calculado, 
                        estado_pago='APROBADO_SIMULADO',
                        referencia_transaccion=f"API-TRX-{uuid.uuid4().hex[:8].upper()}"
                    )

                    # Limpiamos el carrito
                    carrito.limpiar()

                    return Response({
                        'mensaje': 'Pedido simulado procesado con éxito',
                        'pedido_id': pedido.id,
                        'total_pagado': total_calculado
                    }, status=status.HTTP_201_CREATED)
                    
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)