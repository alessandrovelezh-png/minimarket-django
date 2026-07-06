from django.urls import path
from django.contrib.auth.views import LoginView
from . import views

app_name = 'usuarios'

urlpatterns = [
    path('registro/', views.registro, name='registro'),
    # Usamos la vista integrada de Django para login
    path('login/', LoginView.as_view(template_name='usuarios/login.html'), name='login'),
    # CAMBIO: Quitamos LogoutView.as_view() y ponemos views.custom_logout
    path('logout/', views.custom_logout, name='logout'),
    path('perfil/', views.perfil_historial, name='perfil'),
]