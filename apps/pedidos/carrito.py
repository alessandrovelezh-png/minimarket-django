import time # NUEVO: Importamos el módulo de tiempo de Python
from apps.catalogo.models import Producto

class Carrito:
    def __init__(self, request):
        self.session = request.session
        carrito = self.session.get('carrito')
        if not carrito:
            carrito = self.session['carrito'] = {}
        self.carrito = carrito
        # NUEVO: Registramos la hora exacta en la que se instanció/leyó el carrito
        self.session['carrito_ultima_actividad'] = time.time()

    def agregar(self, producto):
        id = str(producto.id)
        # Solo permite agregar si hay stock disponible real
        if producto.stock_disponible > 0:
            if id not in self.carrito:
                self.carrito[id] = {
                    'producto_id': producto.id,
                    'nombre': producto.nombre,
                    'precio': str(producto.precio),
                    'cantidad': 1,
                }
            else:
                self.carrito[id]['cantidad'] += 1
            
            # Bloqueamos 1 unidad en la base de datos
            producto.stock_reservado += 1
            producto.save()
            self.guardar()

    def restar(self, producto):
        id = str(producto.id)
        if id in self.carrito:
            self.carrito[id]['cantidad'] -= 1
            
            # Liberamos 1 unidad en la base de datos
            producto.stock_reservado -= 1
            producto.save()
            
            # PROTECCIÓN: Nunca restar por debajo de 0
            producto.stock_reservado = max(0, producto.stock_reservado - 1)
            producto.save()

            if self.carrito[id]['cantidad'] <= 0:
                del self.carrito[id] # Se elimina directo de la sesión
            self.guardar()

    def eliminar(self, producto):
        id = str(producto.id)
        if id in self.carrito:
            cantidad_a_liberar = self.carrito[id]['cantidad']
            
            # PROTECCIÓN: Nunca restar por debajo de 0
            producto.stock_reservado = max(0, producto.stock_reservado - cantidad_a_liberar)
            producto.save()
            
            del self.carrito[id]
            self.guardar()

    def limpiar(self):
        # Si el usuario vacía el carrito, liberamos todo el stock reservado de la DB
        for key, item in self.carrito.items():
            try:
                prod = Producto.objects.get(id=item['producto_id'])
                # PROTECCIÓN
                prod.stock_reservado = max(0, prod.stock_reservado - item['cantidad'])
                prod.save()
            except Producto.DoesNotExist:
                pass
                
        self.session['carrito'] = {}
        self.guardar()

    def guardar(self):
        # NUEVO: Cada vez que hay una modificación, actualizamos el cronómetro
        self.session['carrito_ultima_actividad'] = time.time()
        self.session.modified = True

    def get_total_carrito(self):
        return sum(float(item['precio']) * item['cantidad'] for item in self.carrito.values())