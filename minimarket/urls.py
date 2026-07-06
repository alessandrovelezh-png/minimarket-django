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
from apps.pedidos import api_views as pedidos_api # Importamos tu archivo de vistas API
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('pedidos/', include('apps.pedidos.urls')), 
    path('', include('apps.catalogo.urls')),
    path('usuarios/', include('apps.usuarios.urls')), 
    
    # === RUTAS API GLOBALES ===
    # Lo mapeamos directamente en la raíz para que no sufra por el prefijo 'pedidos/'
    path('api/carrito/', pedidos_api.api_carrito, name='api_carrito_global'),
    path('api/checkout/', pedidos_api.api_checkout, name='api_checkout_global'),
]

# Esto es vital para que las imágenes de los productos se vean en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)