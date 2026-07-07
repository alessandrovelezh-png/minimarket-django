import stripe
import requests
import uuid
from datetime import datetime # <-- NUEVO
from weasyprint import HTML # <-- NUEVO
from django.utils import timezone # <-- NUEVO
from django.http import HttpResponse # <-- NUEVO
from django.template.loader import render_to_string # <-- NUEVO
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
    # 1. API DE DÓLARES: Extraemos solo la tasa de cambio pura
    # ========================================================
    tipo_cambio = 0
    try:
        respuesta = requests.get('https://open.er-api.com/v6/latest/PEN', timeout=5)
        if respuesta.status_code == 200:
            datos_json = respuesta.json() 
            tipo_cambio = datos_json['rates']['USD'] 
    except Exception as e:
        print(f"Error al consumir el API externa: {e}")

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            metodo_seleccionado = form.cleaned_data['metodo_pago']
            franja_recojo = form.cleaned_data.get('franja_recojo')
            tipo_entrega = form.cleaned_data['tipo_entrega']
            direccion_delivery = form.cleaned_data.get('direccion_delivery')

            # ========================================================
            # 2. VALIDACIÓN DEL HORARIO DE DELIVERY (8:00 AM a 8:00 PM)
            # ========================================================
            if tipo_entrega == 'DELIVERY':
                # Obtenemos la hora local configurada en Django (Lima)
                hora_actual = timezone.localtime().time()
                hora_apertura = datetime.strptime("08:00", "%H:%M").time()
                hora_cierre = datetime.strptime("20:00", "%H:%M").time()
                
                # Si está fuera del horario, recargamos la página con un error
                if not (hora_apertura <= hora_actual <= hora_cierre):
                    return render(request, 'pedidos/checkout.html', {
                        'form': form, 
                        'total_general': total_general, 
                        'tipo_cambio': tipo_cambio,
                        'error_mensaje': 'El servicio de Delivery a domicilio solo está disponible de 8:00 AM a 8:00 PM.'
                    })

            # LÓGICA DE COSTOS: + S/ 10.00 si es Delivery
            costo_envio = 10.00 if tipo_entrega == 'DELIVERY' else 0.00
            total_con_envio = float(total_general) + costo_envio

            # ========================================================
            # BIFURCACIÓN DE PAGOS
            # ========================================================
            
            # --- A. FLUJO STRIPE (Tarjetas y Billeteras Globales) ---
            if metodo_seleccionado in ['STRIPE_CARD', 'STRIPE_WALLET']:
                request.session['datos_pedido_pendiente'] = {
                    'tipo_entrega': tipo_entrega,
                    'direccion_delivery': direccion_delivery,
                    'franja_recojo': franja_recojo,
                    'metodo_pago': metodo_seleccionado, 
                    'costo_delivery': float(costo_envio)
                }

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
                        'form': form, 'total_general': total_general, 'tipo_cambio': tipo_cambio,
                        'error_mensaje': f"Error en pasarela Stripe: {str(e)}"
                    })

            # --- B. FLUJO YAPE / PLIN ONLINE (Redirección a Simulación OTP) ---
            elif metodo_seleccionado in ['LOCAL_YAPE', 'LOCAL_PLIN']:
                try:
                    with transaction.atomic():
                        pedido = form.save(commit=False)
                        pedido.cliente = request.user
                        pedido.estado = 'PENDIENTE'
                        pedido.costo_delivery = costo_envio
                        pedido.total = 0 
                        pedido.save()

                        total_calculado = 0
                        for key, item in carrito.carrito.items():
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

                        # IMPORTANTE: Queda PENDIENTE_PAGO hasta que ingrese el código
                        Pago.objects.create(
                            pedido=pedido, metodo_pago=metodo_seleccionado,
                            monto_pago=pedido.total, estado_pago='PENDIENTE_PAGO' 
                        )
                        carrito.limpiar()
                        
                        # Lo enviamos a la pantalla de validación del código (Paso 3)
                        return redirect('pedidos:simular_billetera', pedido_id=pedido.id)
                        
                except Exception as e:
                    return render(request, 'pedidos/checkout.html', {
                        'form': form, 'total_general': total_general, 'tipo_cambio': tipo_cambio,
                        'error_mensaje': str(e)
                    })

            # --- C. FLUJO CONTRA ENTREGA (Físico) ---
            else:
                try:
                    with transaction.atomic():
                        pedido = form.save(commit=False)
                        pedido.cliente = request.user
                        pedido.estado = 'PENDIENTE'
                        pedido.costo_delivery = costo_envio
                        pedido.total = 0 
                        pedido.save()

                        total_calculado = 0
                        for key, item in carrito.carrito.items():
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

                        # En Contra Entrega, siempre queda PENDIENTE_PAGO
                        Pago.objects.create(
                            pedido=pedido, metodo_pago=metodo_seleccionado,
                            monto_pago=pedido.total, estado_pago='PENDIENTE_PAGO',
                            referencia_transaccion=f"TRX-{uuid.uuid4().hex[:10].upper()}"
                        )

                        carrito.limpiar()
                        return redirect('pedidos:pedido_exitoso')
                        
                except Exception as e:
                    return render(request, 'pedidos/checkout.html', {
                        'form': form, 'total_general': total_general, 'tipo_cambio': tipo_cambio,
                        'error_mensaje': str(e)
                    })
    else:
        form = CheckoutForm()

    return render(request, 'pedidos/checkout.html', {
        'form': form, 
        'total_general': total_general,
        'tipo_cambio': tipo_cambio 
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

# --- 1. SIMULACIÓN YAPE / PLIN ---
@login_required
def simular_billetera(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id, cliente=request.user)
    pago = pedido.pagos.first()
    
    if request.method == 'POST':
        codigo = request.POST.get('codigo_otp')
        if codigo and len(codigo) == 6:
            # Simulación de éxito
            pago.estado_pago = 'APROBADO_SIMULADO'
            pago.referencia_transaccion = f"OTP-{uuid.uuid4().hex[:6].upper()}"
            pago.save()
            return redirect('pedidos:pedido_exitoso')
        else:
            return render(request, 'pedidos/billetera.html', {'pedido': pedido, 'pago': pago, 'error': 'Código inválido'})
            
    return render(request, 'pedidos/billetera.html', {'pedido': pedido, 'pago': pago})

# --- 2. PANELES OPERATIVOS ---
@login_required
def panel_cajero(request):
    # Pedidos de RECOJO que no están entregados ni cancelados
    pedidos = Pedido.objects.filter(tipo_entrega='RECOJO').exclude(estado__in=['ENTREGADO', 'CANCELADO']).order_by('-fecha_hora_pedido')
    return render(request, 'pedidos/panel_cajero.html', {'pedidos': pedidos})

@login_required
def panel_repartidor(request):
    # Pedidos de DELIVERY
    pedidos = Pedido.objects.filter(tipo_entrega='DELIVERY').exclude(estado__in=['ENTREGADO', 'CANCELADO']).order_by('-fecha_hora_pedido')
    return render(request, 'pedidos/panel_repartidor.html', {'pedidos': pedidos})

# --- 3. ACCIONES OPERATIVAS (PAGAR / CANCELAR) ---
@login_required
def accion_pedido(request, pedido_id, accion):
    pedido = get_object_or_404(Pedido, id=pedido_id)
    pago = pedido.pagos.first()
    
    with transaction.atomic():
        if accion == 'CANCELAR':
            # REVERSIÓN DE INVENTARIO
            for detalle in pedido.detalles.all():
                producto = detalle.producto
                producto.stock += detalle.cantidad  # Devuelve los productos a las góndolas
                producto.save()
            
            pedido.estado = 'CANCELADO'
            if pago:
                pago.estado_pago = 'CANCELADO'
                pago.save()
            pedido.save()
            
        elif accion == 'PAGAR_ENTREGAR':
            pedido.estado = 'ENTREGADO'
            if pago:
                pago.estado_pago = 'APROBADO'
                pago.save()
            pedido.save()
            
    return redirect(request.META.get('HTTP_REFERER', 'catalogo:lista_productos'))

'''
@login_required
def descargar_ticket(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id, cliente=request.user)
    pago = pedido.pagos.first()
    
    # Validamos que solo los pedidos realmente pagados generen comprobante
    if not pago or 'APROBADO' not in pago.estado_pago:
        return HttpResponse("El comprobante aún no está disponible porque el pedido no ha sido pagado.", status=403)
    
    # Renderiza la plantilla HTML a un string
    html_string = render_to_string('pedidos/ticket_pdf.html', {'pedido': pedido, 'pago': pago})
    
    # Convierte a PDF
    pdf_file = HTML(string=html_string).write_pdf()
    
    # Configura la respuesta de descarga
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Ticket-Venta-{pedido.id}.pdf"'
    return response
'''
@login_required
def descargar_ticket(request, pedido_id):
    # Función base (Descomenta la lógica de WeasyPrint cuando esté habilitada localmente)
    return HttpResponse("Visualización de comprobante. Función reservada para WeasyPrint.")