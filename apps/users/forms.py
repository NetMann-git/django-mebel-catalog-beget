# apps/users/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Profile


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True, max_length=30)
    last_name = forms.CharField(required=True, max_length=30)

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2']


class ProfileEditForm(forms.Form):
    """Existing optional profile fields, with limits from their models."""
    first_name = forms.CharField(label='Имя', required=False, max_length=User._meta.get_field('first_name').max_length)
    last_name = forms.CharField(label='Фамилия', required=False, max_length=User._meta.get_field('last_name').max_length)
    email = forms.EmailField(label='Электронная почта', required=False, max_length=User._meta.get_field('email').max_length)
    phone = forms.CharField(label='Телефон', required=False, max_length=Profile._meta.get_field('phone').max_length)
