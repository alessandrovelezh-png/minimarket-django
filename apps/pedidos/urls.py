from django.urls import path
from . import views, api_views

app_name = 'pedidos'

urlpatterns = [
    path('carrito/', views.ver_carrito, name='ver_carrito'),
    path('agregar/<int:producto_id>/', views.agregar_carrito, name='agregar_carrito'),
    path('eliminar/<int:producto_id>/', views.eliminar_carrito, name='eliminar_carrito'),
    path('restar/<int:producto_id>/', views.restar_carrito, name='restar_carrito'),
    path('checkout/', views.checkout, name='checkout'),
    path('exito/', views.pedido_exitoso, name='pedido_exitoso'),
    # Nuevas rutas de Stripe
    path('stripe/success/', views.stripe_success, name='stripe_success'),
    path('stripe/cancel/', views.stripe_cancel, name='stripe_cancel'),
    # NUEVO
    path('billetera/<int:pedido_id>/', views.simular_billetera, name='simular_billetera'),
    path('cajero/', views.panel_cajero, name='panel_cajero'),
    path('repartidor/', views.panel_repartidor, name='panel_repartidor'),
    path('accion/<int:pedido_id>/<str:accion>/', views.accion_pedido, name='accion_pedido'),
    path('ticket/<int:pedido_id>/', views.descargar_ticket, name='descargar_ticket'), # generacion de ticket
]