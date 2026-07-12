from django.urls import path
from . import views, api_views # Importa el nuevo archivo

app_name = 'catalogo'

urlpatterns = [
    path('', views.catalogo_list, name='lista_productos'),
    path('categoria/<int:categoria_id>/', views.catalogo_list, name='lista_por_categoria'),
    path('producto/<int:producto_id>/', views.producto_detail, name='detalle_producto'),
]