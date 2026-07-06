from django.shortcuts import render, get_object_or_404
from .models import Producto, Categoria
from apps.pedidos.carrito import Carrito # <-- IMPORTANTE: Importa el Carrito
# Create your views here.

def catalogo_list(request, categoria_id=None):
    categoria = None
    categorias = Categoria.objects.all()
    productos = Producto.objects.filter(disponible=True)

    if categoria_id:
        categoria = get_object_or_404(Categoria, id=categoria_id)
        productos = productos.filter(categoria=categoria)

    return render(request, 'catalogo/lista.html', {
        'categoria': categoria,
        'categorias': categorias,
        'productos': productos
    })

def producto_detail(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id, disponible=True)
    
    # Instanciamos el carrito de la sesión actual
    carrito = Carrito(request)
    
    # Buscamos si este producto ya está en el carrito para obtener su cantidad
    cantidad_en_carrito = 0
    item = carrito.carrito.get(str(producto.id))
    if item:
        cantidad_en_carrito = item['cantidad']
        
    return render(request, 'catalogo/detalle.html', {
        'producto': producto,
        'cantidad_en_carrito': cantidad_en_carrito # <-- Enviamos la cantidad a la plantilla
    })