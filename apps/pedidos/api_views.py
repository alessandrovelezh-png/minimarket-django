import uuid
import stripe
import requests
from datetime import datetime
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from apps.catalogo.models import Producto
from .models import Pedido, DetallePedido, Pago
from .carrito import Carrito

# Configuramos la clave secreta de Stripe para la API
stripe.api_key = settings.STRIPE_SECRET_KEY

# ==========================================
# 1. API DEL CARRITO DE COMPRAS
# ==========================================
@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([AllowAny]) 
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
@permission_classes([IsAuthenticated]) 
def api_checkout(request):
    carrito = Carrito(request)
    
    if not carrito.carrito:
        return Response({'error': 'El carrito está vacío'}, status=status.HTTP_400_BAD_REQUEST)

    # Extraemos los datos dinámicos del JSON enviado por el cliente
    data = request.data
    metodo_seleccionado = data.get('metodo_pago')
    franja_recojo = data.get('franja_recojo', 'HOY_MAÑANA')
    tipo_entrega = data.get('tipo_entrega', 'RECOJO')
    direccion_delivery = data.get('direccion_delivery', '')

    if not metodo_seleccionado:
        return Response({'error': 'Debe seleccionar un método de pago'}, status=status.HTTP_400_BAD_REQUEST)

    # 1. VALIDACIÓN DEL HORARIO DE DELIVERY (8:00 AM a 8:00 PM)
    if tipo_entrega == 'DELIVERY':
        hora_actual = timezone.localtime().time()
        hora_apertura = datetime.strptime("08:00", "%H:%M").time()
        hora_cierre = datetime.strptime("20:00", "%H:%M").time()
        
        if not (hora_apertura <= hora_actual <= hora_cierre):
            return Response({'error': 'El servicio de Delivery solo está disponible de 8:00 AM a 8:00 PM.'}, status=status.HTTP_400_BAD_REQUEST)

    # LÓGICA DE COSTOS
    costo_envio = 10.00 if tipo_entrega == 'DELIVERY' else 0.00
    total_general = float(carrito.get_total_carrito())

    # ========================================================
    # BIFURCACIÓN DE PAGOS: STRIPE VS SIMULACIÓN LOCAL API
    # ========================================================
    if metodo_seleccionado in ['STRIPE_CARD', 'STRIPE_WALLET']:
        
        # Guardamos los datos logísticos en la sesión temporalmente para el retorno de Stripe
        request.session['datos_pedido_pendiente'] = {
            'tipo_entrega': tipo_entrega,
            'direccion_delivery': direccion_delivery,
            'franja_recojo': franja_recojo,
            'metodo_pago': metodo_seleccionado, 
            'costo_delivery': float(costo_envio)
        }

        # Construimos la lista de productos (line_items) para Stripe
        line_items = []
        for key, item in carrito.carrito.items():
            line_items.append({
                'price_data': {
                    'currency': 'pen', 
                    'unit_amount': int(float(item['precio']) * 100), 
                    'product_data': {'name': item['nombre']},
                },
                'quantity': item['cantidad'],
            })
            
        # Añadimos el costo de delivery a Stripe si aplica
        if costo_envio > 0:
            line_items.append({
                'price_data': {
                    'currency': 'pen',
                    'unit_amount': int(costo_envio * 100),
                    'product_data': {'name': 'Servicio de Delivery a Domicilio'},
                },
                'quantity': 1,
            })

        try:
            success_url = request.build_absolute_uri(reverse('pedidos:stripe_success'))
            cancel_url = request.build_absolute_uri(reverse('pedidos:stripe_cancel'))

            # Creamos la sesión en los servidores de Stripe
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card', 'link'],
                line_items=line_items,
                mode='payment',
                success_url=success_url,
                cancel_url=cancel_url,
            )

            return Response({
                'mensaje': 'Sesión de pago iniciada. Redirige al cliente a la URL proporcionada.',
                'stripe_url': checkout_session.url
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': f"Error conectando con Stripe: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    else:
        # --- FLUJO SIMULADO LOCAL (Yape, Plin, Contra Entrega, Efectivo) ---
        try:
            with transaction.atomic():
                pedido = Pedido.objects.create(
                    cliente=request.user,
                    estado='PENDIENTE',
                    tipo_entrega=tipo_entrega,
                    direccion_delivery=direccion_delivery,
                    franja_recojo=franja_recojo,
                    costo_delivery=costo_envio,
                    total=0
                )

                total_calculado = 0
                for key, item in carrito.carrito.items():
                    # Bloqueamos la fila y descontamos aplicando Programación Defensiva (Max 0)
                    producto = Producto.objects.select_for_update().get(id=item['producto_id'])
                    cantidad_comprada = item['cantidad']

                    producto.stock = max(0, producto.stock - cantidad_comprada)
                    producto.stock_reservado = max(0, producto.stock_reservado - cantidad_comprada)
                    producto.save()

                    precio_unitario = float(item['precio'])
                    DetallePedido.objects.create(
                        pedido=pedido, producto=producto,
                        cantidad=cantidad_comprada, precio_unitario_historico=precio_unitario
                    )
                    total_calculado += (precio_unitario * cantidad_comprada)

                pedido.total = total_calculado + costo_envio
                pedido.save()

                # Determinar el estado del pago simulado
                if metodo_seleccionado in ['LOCAL_YAPE', 'LOCAL_PLIN'] or 'CONTRA' in metodo_seleccionado:
                    estado_final_pago = 'PENDIENTE_PAGO'
                else:
                    estado_final_pago = 'APROBADO_SIMULADO'

                Pago.objects.create(
                    pedido=pedido, 
                    metodo_pago=metodo_seleccionado,
                    monto_pago=pedido.total, 
                    estado_pago=estado_final_pago,
                    referencia_transaccion=f"API-TRX-{uuid.uuid4().hex[:8].upper()}"
                )

                carrito.limpiar()

                # Si es Yape/Plin, la API devuelve la URL para que el frontend procese el código OTP
                if metodo_seleccionado in ['LOCAL_YAPE', 'LOCAL_PLIN']:
                    url_otp = request.build_absolute_uri(reverse('pedidos:simular_billetera', kwargs={'pedido_id': pedido.id}))
                    return Response({
                        'mensaje': 'Pedido creado. Requiere validación OTP para Yape/Plin.',
                        'pedido_id': pedido.id,
                        'url_validacion': url_otp,
                        'total_pagar': pedido.total
                    }, status=status.HTTP_201_CREATED)

                # Si es Contra Entrega o Efectivo Local
                return Response({
                    'mensaje': 'Pedido procesado localmente con éxito',
                    'pedido_id': pedido.id,
                    'total_pagado': pedido.total
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)