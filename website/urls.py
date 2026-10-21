from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("shop/", views.shop, name="shop"),
    path("cart/add/<slug:slug>/", views.add_to_cart, name="add_to_cart"),
    path("cart/update/<int:item_id>/", views.update_cart_item, name="update_cart_item"),
    path("cart/remove/<int:item_id>/", views.remove_cart_item, name="remove_cart_item"),
    path("cart/drawer/", views.cart_drawer, name="cart_drawer"),
    path("cart/", views.cart, name="cart"),
    path("checkout/", views.checkout, name="checkout"),
    path("orders/confirmation/<str:order_number>/", views.order_confirmation, name="order_confirmation"),
    path("orders/<str:order_number>/", views.order_detail, name="order_detail"),
    path("account/", views.account, name="account"),
    path("account/signup/", views.sign_up, name="signup"),
    path("account/password-requirements/", views.password_requirements, name="password_requirements"),
    path("account/login/", views.sign_in, name="login"),
    path("account/logout/", views.sign_out, name="logout"),
    path("information/<slug:page>/", views.information_page, name="information"),
]
