from django.db import models

# Create your models here.

class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre

class Producto(models.Model):
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE, related_name='productos')
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField()
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    
    stock = models.IntegerField(default=0)
    # NUEVO: Campo para bloquear el stock mientras está en un carrito
    stock_reservado = models.IntegerField(default=0) 
    
    imagen = models.ImageField(upload_to='productos/', blank=True, null=True)
    disponible = models.BooleanField(default=True)

    # NUEVO: Propiedad dinámica que calcula cuánto se puede vender realmente
    @property
    def stock_disponible(self):
        return self.stock - self.stock_reservado

    # ==========================================
    # NUEVO: PROGRAMACIÓN DEFENSIVA
    # ==========================================
    def save(self, *args, **kwargs):
        # Si por algún error matemático el stock reservado intenta ser negativo, lo forzamos a 0
        if self.stock_reservado < 0:
            self.stock_reservado = 0
            
        # Opcional pero recomendado: hacemos lo mismo para el stock físico
        if self.stock < 0:
            self.stock = 0
            
        # Llamamos al método save original para que guarde en la base de datos
        super().save(*args, **kwargs)
    

    def __str__(self):
        return self.nombre
