"""
URL configuration for minimarket project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Importamos directamente las vistas de la API
from apps.catalogo import api_views as catalogo_api
from apps.pedidos import api_views as pedidos_api

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Rutas Web Tradicionales (HTML)
    path('', include('apps.catalogo.urls')),
    path('pedidos/', include('apps.pedidos.urls')),
    path('usuarios/', include('apps.usuarios.urls')),
    
    # Rutas API REST Framework (JSON)
    path('api/productos/', catalogo_api.lista_productos_api, name='api_productos'),
    path('api/productos/<int:producto_id>/', catalogo_api.api_detalle_producto, name='api_detalle_producto'),
    path('api/carrito/', pedidos_api.api_carrito, name='api_carrito'),
    path('api/checkout/', pedidos_api.api_checkout, name='api_checkout'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)