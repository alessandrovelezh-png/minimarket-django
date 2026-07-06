from rest_framework import serializers
from .models import Categoria, Producto

class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = ['id', 'nombre']

class ProductoSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.CharField(source='categoria.nombre', read_only=True)

    class Meta:
        model = Producto
        # Incluimos los campos relevantes, incluyendo el stock disponible real
        fields = ['id', 'nombre', 'descripcion', 'precio', 'stock_disponible', 'categoria_nombre', 'disponible']