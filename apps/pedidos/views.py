import stripe
import requests
import uuid
from django.conf import settings
from django.urls import reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from apps.catalogo.models import Producto
from .models import Pedido, DetallePedido, Pago
from .carrito import Carrito
from .forms import CheckoutForm

# Configuramos la clave secreta de Stripe extrayéndola de settings.py
stripe.api_key = settings.STRIPE_SECRET_KEY

def ver_carrito(request):
    carrito = Carrito(request)
    total_general = carrito.get_total_carrito()
    
    # HU08: Preparamos los datos matemáticos (Subtotal) antes de enviarlos al HTML
    items_carrito = []
    for key, item in carrito.carrito.items():
        item['subtotal'] = float(item['precio']) * item['cantidad']
        items_carrito.append(item)

    return render(request, 'pedidos/carrito.html', {
        'items_carrito': items_carrito, 
        'total_general': total_general
    })

def restar_carrito(request, producto_id):
    carrito = Carrito(request)
    producto = get_object_or_404(Producto, id=producto_id)
    carrito.restar(producto)
    url_origen = request.META.get('HTTP_REFERER', 'pedidos:ver_carrito')
    return redirect(url_origen)

def agregar_carrito(request, producto_id):
    carrito = Carrito(request)
    producto = get_object_or_404(Producto, id=producto_id)
    carrito.agregar(producto)
    url_origen = request.META.get('HTTP_REFERER', 'catalogo:lista_productos')
    return redirect(url_origen)

def eliminar_carrito(request, producto_id):
    carrito = Carrito(request)
    producto = get_object_or_404(Producto, id=producto_id)
    carrito.eliminar(producto)
    url_origen = request.META.get('HTTP_REFERER', 'pedidos:ver_carrito')
    return redirect(url_origen)

@login_required 
def checkout(request):
    carrito = Carrito(request)
    if not carrito.carrito:
        return redirect('catalogo:lista_productos')

    total_general = carrito.get_total_carrito()
    
    # ========================================================
    # CONSUMO DE API EXTERNA REST FULL (Requisito del profesor)
    # ========================================================
    tipo_cambio = None
    total_dolares = None
    try:
        respuesta = requests.get('https://open.er-api.com/v6/latest/PEN', timeout=5)
        if respuesta.status_code == 200:
            datos_json = respuesta.json() 
            tipo_cambio = datos_json['rates']['USD'] 
            total_dolares = round(float(total_general) * tipo_cambio, 2)
    except Exception as e:
        print(f"Error al consumir el API externa: {e}")
    # ========================================================

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            metodo_seleccionado = form.cleaned_data['metodo_pago']
            franja_recojo = form.cleaned_data.get('franja_recojo')
            tipo_entrega = form.cleaned_data['tipo_entrega']
            direccion_delivery = form.cleaned_data.get('direccion_delivery')

            # LÓGICA DE COSTOS: + S/ 10.00 si es Delivery
            costo_envio = 10.00 if tipo_entrega == 'DELIVERY' else 0.00
            total_con_envio = float(total_general) + costo_envio

            # ========================================================
            # BIFURCACIÓN DE PAGOS: STRIPE VS SIMULACIÓN LOCAL
            # ========================================================
            if metodo_seleccionado in ['STRIPE_CARD', 'STRIPE_WALLET']:
                
                # --- FLUJO STRIPE ---
                # Guardamos los datos logísticos en la sesión temporalmente
                request.session['datos_pedido_pendiente'] = {
                    'tipo_entrega': tipo_entrega,
                    'direccion_delivery': direccion_delivery,
                    'franja_recojo': franja_recojo,
                    'metodo_pago': metodo_seleccionado, 
                    'costo_delivery': float(costo_envio)
                }

                # Construimos la lista de productos
                line_items = []
                for key, item in carrito.carrito.items():
                    line_items.append({
                        'price_data': {
                            'currency': 'pen', 
                            'unit_amount': int(float(item['precio']) * 100), 
                            'product_data': {
                                'name': item['nombre'],
                            },
                        },
                        'quantity': item['cantidad'],
                    })
                
                # AÑADIMOS EL COSTO DE DELIVERY A STRIPE SI APLICA
                if costo_envio > 0:
                    line_items.append({
                        'price_data': {
                            'currency': 'pen',
                            'unit_amount': int(costo_envio * 100),
                            'product_data': {
                                'name': 'Servicio de Delivery a Domicilio',
                            },
                        },
                        'quantity': 1,
                    })

                try:
                    # Creamos la sesión de pago con Stripe habilitando tarjetas y Link (billeteras)
                    checkout_session = stripe.checkout.Session.create(
                        payment_method_types=['card', 'link'], 
                        line_items=line_items,
                        mode='payment',
                        success_url=request.build_absolute_uri(reverse('pedidos:stripe_success')),
                        cancel_url=request.build_absolute_uri(reverse('pedidos:stripe_cancel')),
                    )
                    return redirect(checkout_session.url, code=303)
                except Exception as e:
                    return render(request, 'pedidos/checkout.html', {
                        'form': form, 
                        'total_general': total_general, 
                        'total_dolares': total_dolares,
                        'error_mensaje': f"Error en pasarela Stripe: {str(e)}"
                    })

            else:
                # --- FLUJO SIMULADO (Online Local o Contra Entrega) ---
                try:
                    with transaction.atomic():
                        user_actual = request.user 
                        
                        # 1. Crear la cabecera del Pedido
                        pedido = form.save(commit=False)
                        pedido.cliente = user_actual
                        pedido.estado = 'PENDIENTE'
                        pedido.costo_delivery = costo_envio
                        pedido.total = 0 
                        pedido.save()

                        total_calculado = 0

                        # 2. Procesar ítems del carrito y actualizar stocks (Protección Defensiva)
                        for key, item in carrito.carrito.items():
                            producto = Producto.objects.select_for_update().get(id=item['producto_id'])
                            cantidad_comprada = item['cantidad']

                            producto.stock = max(0, producto.stock - cantidad_comprada)
                            producto.stock_reservado = max(0, producto.stock_reservado - cantidad_comprada)
                            producto.save()

                            precio_unitario = float(item['precio'])
                            DetallePedido.objects.create(
                                pedido=pedido,
                                producto=producto,
                                cantidad=cantidad_comprada,
                                precio_unitario_historico=precio_unitario
                            )
                            total_calculado += (precio_unitario * cantidad_comprada)

                        # Actualizar el total real calculado sumando el delivery
                        pedido.total = total_calculado + costo_envio
                        pedido.save()

                        # 3. Determinar el estado del pago simulado
                        # Si es Contra Entrega está PENDIENTE_PAGO, si es Yape Online está APROBADO_SIMULADO
                        estado_final_pago = 'PENDIENTE_PAGO' if 'CONTRA' in metodo_seleccionado else 'APROBADO_SIMULADO'

                        # 4. Registrar el Pago
                        referencia_generada = f"TRX-{uuid.uuid4().hex[:10].upper()}" 
                        Pago.objects.create(
                            pedido=pedido,
                            metodo_pago=metodo_seleccionado,
                            monto_pago=pedido.total,
                            estado_pago=estado_final_pago,
                            referencia_transaccion=referencia_generada
                        )

                        # 5. Vaciar el carrito y limpiar los cronómetros de inactividad
                        request.session['carrito'] = {}
                        if 'carrito_ultima_actividad' in request.session:
                            del request.session['carrito_ultima_actividad']
                        request.session.modified = True

                        return redirect('pedidos:pedido_exitoso')
                        
                except Exception as e:
                    return render(request, 'pedidos/checkout.html', {
                        'form': form,
                        'total_general': total_general,
                        'total_dolares': total_dolares,
                        'error_mensaje': str(e)
                    })
    else:
        form = CheckoutForm()

    return render(request, 'pedidos/checkout.html', {
        'form': form, 
        'total_general': total_general,
        'total_dolares': total_dolares 
    })


# ========================================================
# NUEVAS VISTAS: MANEJO DEL RETORNO DE STRIPE
# ========================================================

@login_required
def stripe_success(request):
    """Se ejecuta si el cliente paga con éxito en Stripe"""
    carrito = Carrito(request)
    datos_pedido = request.session.get('datos_pedido_pendiente')

    if not carrito.carrito or not datos_pedido:
        return redirect('catalogo:lista_productos')

    try:
        with transaction.atomic():
            # 1. Crear el Pedido con todos los datos logísticos de la sesión
            pedido = Pedido.objects.create(
                cliente=request.user,
                estado='PENDIENTE',
                tipo_entrega=datos_pedido['tipo_entrega'],
                direccion_delivery=datos_pedido.get('direccion_delivery'),
                franja_recojo=datos_pedido.get('franja_recojo'),
                costo_delivery=datos_pedido['costo_delivery'],
                total=0
            )

            total_calculado = 0
            
            # 2. Procesar ítems y descontar existencias (Defensivo)
            for key, item in carrito.carrito.items():
                producto = Producto.objects.select_for_update().get(id=item['producto_id'])
                cantidad_comprada = item['cantidad']

                producto.stock = max(0, producto.stock - cantidad_comprada)
                producto.stock_reservado = max(0, producto.stock_reservado - cantidad_comprada)
                producto.save()

                precio_unitario = float(item['precio'])
                DetallePedido.objects.create(
                    pedido=pedido, 
                    producto=producto,
                    cantidad=cantidad_comprada, 
                    precio_unitario_historico=precio_unitario
                )
                total_calculado += (precio_unitario * cantidad_comprada)

            # Sumamos el costo de delivery al total guardado
            pedido.total = total_calculado + float(datos_pedido['costo_delivery'])
            pedido.save()

            # 3. Registrar el pago como REAL y APROBADO
            Pago.objects.create(
                pedido=pedido,
                metodo_pago=datos_pedido['metodo_pago'],
                monto_pago=pedido.total,
                estado_pago='APROBADO',
                referencia_transaccion=f"STRIPE-{uuid.uuid4().hex[:15].upper()}"
            )

            # 4. Limpiar los datos temporales y vaciar el carrito
            request.session['carrito'] = {}
            del request.session['datos_pedido_pendiente']
            if 'carrito_ultima_actividad' in request.session:
                del request.session['carrito_ultima_actividad']
            request.session.modified = True

            return redirect('pedidos:pedido_exitoso')
            
    except Exception as e:
        return render(request, 'pedidos/checkout.html', {
            'form': CheckoutForm(),
            'error_mensaje': f"Ocurrió un error guardando el pedido tras pagar con Stripe: {str(e)}"
        })

@login_required
def stripe_cancel(request):
    """Se ejecuta si el cliente cancela o cierra la ventana de Stripe"""
    carrito = Carrito(request)
    total_general = carrito.get_total_carrito()
    
    if 'datos_pedido_pendiente' in request.session:
        del request.session['datos_pedido_pendiente']
        request.session.modified = True

    return render(request, 'pedidos/checkout.html', {
        'form': CheckoutForm(),
        'total_general': total_general,
        'error_mensaje': "Se canceló el pago con tarjeta. Puedes intentar nuevamente o usar otro método."
    })


def pedido_exitoso(request):
    return render(request, 'pedidos/exito.html')