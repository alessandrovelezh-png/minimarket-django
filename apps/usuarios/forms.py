from django import forms
from django.contrib.auth.models import User
from apps.pedidos.models import Cliente

class RegistroClienteForm(forms.ModelForm):
    # Campos nativos de User
    username = forms.CharField(max_length=150, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    
    # Campo extra de nuestro modelo Cliente
    telefono = forms.CharField(max_length=20, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def save(self, commit=True):
        # 1. Creamos el usuario base
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password']) # Hashing de seguridad
        if commit:
            user.save()
            # 2. Creamos el perfil de Cliente vinculado automáticamente
            Cliente.objects.create(
                user=user,
                telefono=self.cleaned_data.get('telefono')
            )
        return user