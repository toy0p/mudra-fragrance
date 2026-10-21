from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class SignUpForm(UserCreationForm):
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ("username", "email")


class CheckoutForm(forms.Form):
    customer_name = forms.CharField(max_length=200)
    email = forms.EmailField()
    phone = forms.CharField(max_length=50)
    delivery_address = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}))
