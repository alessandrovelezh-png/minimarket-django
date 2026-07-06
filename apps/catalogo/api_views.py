from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Producto
from .serializers import ProductoSerializer

@api_view(['GET'])
def api_lista_productos(request):
    """Devuelve la lista de todos los productos disponibles en JSON"""
    productos = Producto.objects.filter(disponible=True)
    serializer = ProductoSerializer(productos, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['GET'])
def api_detalle_producto(request, producto_id):
    """Devuelve los detalles de un solo producto"""
    producto = get_object_or_404(Producto, id=producto_id, disponible=True)
    serializer = ProductoSerializer(producto)
    return Response(serializer.data, status=status.HTTP_200_OK)