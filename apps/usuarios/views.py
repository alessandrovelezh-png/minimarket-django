from django.shortcuts import render, redirect
from django.contrib.auth import login, logout # <-- Asegúrate de agregar 'logout' aquí
from django.contrib.auth.decorators import login_required
from .forms import RegistroClienteForm
from apps.pedidos.models import Pedido
from apps.pedidos.carrito import Carrito # <-- IMPORTANTE: Importamos tu clase Carrito

# Create your views here.

def registro(request):
    if request.method == 'POST':
        form = RegistroClienteForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user) # Auto-login después de registrarse
            return redirect('catalogo:lista_productos')
    else:
        form = RegistroClienteForm()
    return render(request, 'usuarios/registro.html', {'form': form})

# Protección: Solo usuarios logueados pueden ver esta vista
@login_required
def perfil_historial(request):
    # Traemos los pedidos de este usuario gracias a la relación related_name='pedidos'
    pedidos = request.user.pedidos.all().order_by('-fecha_hora_pedido')
    return render(request, 'usuarios/perfil.html', {'pedidos': pedidos})

# NUEVA VISTA:
def custom_logout(request):
    # 1. Instanciamos el carrito ANTES de que Django destruya la sesión
    carrito = Carrito(request)
    
    # 2. Si el carrito existe y tiene productos, liberamos el stock
    # Usamos la función limpiar() que ya programaste, la cual resta el stock_reservado
    if carrito.carrito:
        carrito.limpiar()

    # 3. Ahora sí, cerramos la sesión de Django de forma segura
    logout(request)
    
    # 4. Redirigimos al catálogo de productos
    return redirect('catalogo:lista_productos')