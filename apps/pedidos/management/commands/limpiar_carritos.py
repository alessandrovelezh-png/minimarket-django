import time
from django.core.management.base import BaseCommand
from django.contrib.sessions.models import Session
from django.contrib.sessions.backends.db import SessionStore
from django.conf import settings
from apps.catalogo.models import Producto

class Command(BaseCommand):
    help = 'Libera el stock de carritos inactivos sin cerrar la sesión del usuario'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Fuerza la limpieza de TODOS los carritos inmediatamente',
        )

    def handle(self, *args, **kwargs):
        es_modo_forzado = kwargs['force']
        # Leemos el tiempo que configuraste en settings.py (por defecto 900 si no lo encuentra)
        tiempo_limite = getattr(settings, 'CARRITO_TIEMPO_VIDA', 900) 
        tiempo_actual = time.time()

        productos_liberados = 0
        carritos_limpiados = 0

        # Iteramos sobre TODAS las sesiones activas en la base de datos
        for session_obj in Session.objects.all():
            # SessionStore nos permite manipular el diccionario interno de la sesión de forma segura
            session = SessionStore(session_key=session_obj.session_key)
            
            # Verificamos si esta sesión tiene un carrito y un cronómetro
            if 'carrito' in session and 'carrito_ultima_actividad' in session:
                ultima_actividad = session['carrito_ultima_actividad']
                tiempo_inactivo = tiempo_actual - ultima_actividad

                # Si el carrito ha estado inactivo más del tiempo límite, o usamos --force
                if tiempo_inactivo > tiempo_limite or es_modo_forzado:
                    carrito = session['carrito']
                    
                    for key, item in carrito.items():
                        try:
                            producto = Producto.objects.get(id=item['producto_id'])
                            cantidad_reservada = item['cantidad']
                            
                            # ==========================================
                            # PROTECCIÓN MATEMÁTICA (Defensive Programming)
                            # ==========================================
                            # Calculamos la resta de forma segura para evitar negativos
                            nuevo_reservado = max(0, producto.stock_reservado - cantidad_reservada)
                            
                            # Solo sumamos al contador y guardamos si realmente hubo un cambio
                            if producto.stock_reservado != nuevo_reservado:
                                producto.stock_reservado = nuevo_reservado
                                producto.save()
                                productos_liberados += 1
                            # ==========================================
                                
                        except Producto.DoesNotExist:
                            continue
                            
                    # EL TRUCO MAESTRO: Borramos solo los datos del carrito, no la sesión.
                    del session['carrito']
                    del session['carrito_ultima_actividad']
                    session.save() # Guardamos los cambios en SQLite
                    carritos_limpiados += 1
                    
        self.stdout.write(self.style.SUCCESS(f'✅ Éxito: Se liberaron productos de {carritos_limpiados} carritos inactivos sin desloguear a los usuarios.'))