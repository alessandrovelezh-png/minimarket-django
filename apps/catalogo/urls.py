from django.urls import path
from . import views, api_views # Importa el nuevo archivo

app_name = 'catalogo'

urlpatterns = [
    path('', views.catalogo_list, name='lista_productos'),
    path('categoria/<int:categoria_id>/', views.catalogo_list, name='lista_por_categoria'),
    path('producto/<int:producto_id>/', views.producto_detail, name='detalle_producto'),
    
    # NUEVA RUTA PARA LA API REST
    path('api/productos/', api_views.api_lista_productos, name='api_lista_productos'),
    path('api/productos/<int:producto_id>/', api_views.api_detalle_producto, name='api_detalle_producto'),
]