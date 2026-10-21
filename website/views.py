from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import (
    CommonPasswordValidator,
    MinimumLengthValidator,
    NumericPasswordValidator,
    get_default_password_validators,
)
from django.db import transaction
from django.core.exceptions import ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from store.models import Cart, CartItem, Category, Order, OrderItem, Product
from .forms import CheckoutForm, SignUpForm


def _get_cart(request, create=False):
    if not request.session.session_key:
        if not create:
            return None
        request.session.create()
    if create:
        return Cart.objects.get_or_create(
            session_key=request.session.session_key
        )[0]
    return Cart.objects.filter(session_key=request.session.session_key).first()


def _cart_total(cart):
    if not cart:
        return Decimal("0.00")
    return sum(
        (item.product.price * item.quantity for item in cart.items.select_related("product")),
        Decimal("0.00"),
    )


def _cart_data(cart, changed_item=None, removed=False):
    data = {
        "count": sum(cart.items.values_list("quantity", flat=True)),
        "total": f"{_cart_total(cart):.2f}",
        "empty": not cart.items.exists(),
    }
    if changed_item is not None:
        data.update({
            "item_id": changed_item.pk,
            "quantity": 0 if removed else changed_item.quantity,
            "line_total": (
                f"{changed_item.product.price * changed_item.quantity:.2f}"
                if not removed else "0.00"
            ),
        })
    return data


def _is_ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def home(request):
    featured_products = Product.objects.filter(
        is_active=True
    ).select_related("category")[:8]
    return render(request, "website/home.html", {
        "featured_products": featured_products,
    })


def shop(request):
    products = Product.objects.filter(
        is_active=True
    ).select_related("category")
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    if query:
        products = products.filter(name__icontains=query)
    if category:
        products = products.filter(category__slug=category)

    cart = _get_cart(request)
    cart_product_ids = set(
        cart.items.values_list("product_id", flat=True)
    ) if cart else set()
    categories = list(Category.objects.all())
    order = {"MENS": 1, "WOMENS": 2, "UNISEX": 3, "CAR DIFFUSER": 4}
    categories.sort(key=lambda item: order.get(item.name.upper(), 99))
    category_cards = []
    for category_obj in categories:
        category_products = list(products.filter(category=category_obj))
        category_cards.append({
            "category": category_obj,
            "products": category_products,
        })
    return render(request, "website/shop.html", {
        "products": products,
        "categories": categories,
        "category_cards": category_cards,
        "query": query,
        "selected_category": category,
        "cart_product_ids": cart_product_ids,
    })


@require_POST
def add_to_cart(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    cart = _get_cart(request, create=True)
    item = CartItem.objects.filter(cart=cart, product=product).first()
    buy_now = request.POST.get("buy_now") == "1"
    if item:
        if _is_ajax(request):
            data = _cart_data(cart, item)
            data["already_added"] = True
            if buy_now:
                data["redirect"] = redirect("checkout").url
            else:
                data["open_cart"] = True
            return JsonResponse(data)
        return redirect("checkout" if buy_now else "cart")

    item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    if product.stock < 1 or (not created and item.quantity >= product.stock):
        if created:
            item.delete()
        payload = {"error": "This product is not available in the requested quantity."}
        if _is_ajax(request):
            return JsonResponse(payload, status=409)
        messages.error(request, payload["error"])
        return redirect("shop")
    if not created:
        item.quantity += 1
        item.save(update_fields=["quantity"])
    if _is_ajax(request):
        data = _cart_data(cart, item)
        if buy_now:
            data["redirect"] = redirect("checkout").url
        else:
            data["open_cart"] = True
        return JsonResponse(data)
    if buy_now:
        return redirect("checkout")
    return redirect("cart")


@require_POST
def update_cart_item(request, item_id):
    cart = _get_cart(request)
    if not cart:
        return JsonResponse({"error": "Your bag is empty."}, status=404)
    item = get_object_or_404(CartItem, pk=item_id, cart=cart)
    action = request.POST.get("action")
    removed = False
    if action == "increase":
        if item.quantity >= item.product.stock:
            return JsonResponse({"error": "No more stock is available."}, status=409)
        item.quantity += 1
        item.save(update_fields=["quantity"])
    elif action == "set":
        try:
            quantity = int(request.POST.get("quantity", ""))
        except ValueError:
            return JsonResponse({"error": "Invalid quantity."}, status=400)
        if quantity < 0:
            return JsonResponse({"error": "Invalid quantity."}, status=400)
        if quantity > item.product.stock:
            return JsonResponse({"error": "No more stock is available."}, status=409)
        if quantity == 0:
            item.delete()
            removed = True
        elif quantity != item.quantity:
            item.quantity = quantity
            item.save(update_fields=["quantity"])
    elif action == "decrease":
        item.quantity -= 1
        if item.quantity == 0:
            item.delete()
            removed = True
    else:
        return JsonResponse({"error": "Invalid cart action."}, status=400)
    if _is_ajax(request):
        return JsonResponse(_cart_data(cart, item, removed=removed))
    return redirect("cart")


@require_POST
def remove_cart_item(request, item_id):
    cart = _get_cart(request)
    if not cart:
        return JsonResponse({"error": "Your bag is empty."}, status=404)
    item = get_object_or_404(CartItem, pk=item_id, cart=cart)
    item.delete()
    if _is_ajax(request):
        return JsonResponse(_cart_data(cart, item, removed=True))
    return redirect("cart")


def cart(request):
    cart_obj = _get_cart(request, create=True)
    items = cart_obj.items.select_related("product", "product__category")
    return render(request, "website/cart.html", {
        "cart": cart_obj,
        "items": items,
        "total": _cart_total(cart_obj),
    })


def cart_drawer(request):
    cart_obj = _get_cart(request)
    items = cart_obj.items.select_related("product", "product__category") if cart_obj else []
    return render(request, "website/cart_drawer_content.html", {
        "items": items,
        "total": _cart_total(cart_obj),
    })


def checkout(request):
    cart_obj = _get_cart(request)
    items = list(cart_obj.items.select_related("product") if cart_obj else [])
    if not items:
        messages.error(request, "Add a product to your bag before checkout.")
        return redirect("cart")

    initial = {}
    if request.user.is_authenticated:
        initial = {
            "customer_name": request.user.get_full_name() or request.user.username,
            "email": request.user.email,
        }
    form = CheckoutForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        unavailable = [
            item.product.name for item in items
            if not item.product.is_active or item.quantity > item.product.stock
        ]
        if unavailable:
            form.add_error(None, "Some items no longer have enough stock. Update your bag and try again.")
        else:
            with transaction.atomic():
                order = Order.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    total=_cart_total(cart_obj),
                    **form.cleaned_data,
                )
                OrderItem.objects.bulk_create([
                    OrderItem(
                        order=order,
                        product=item.product,
                        quantity=item.quantity,
                        product_price=item.product.price,
                    )
                    for item in items
                ])
                cart_obj.items.all().delete()
            request.session["recent_order_id"] = order.pk
            return redirect("order_confirmation", order_number=order.number)

    return render(request, "website/checkout.html", {
        "form": form,
        "items": items,
        "total": _cart_total(cart_obj),
    })


def order_confirmation(request, order_number):
    order = get_object_or_404(Order, number=order_number)
    allowed = (
        request.user.is_authenticated and order.user_id == request.user.pk
    ) or (
        not request.user.is_authenticated
        and request.session.get("recent_order_id") == order.pk
    )
    if not allowed:
        raise Http404
    return render(request, "website/order_confirmation.html", {"order": order})


def sign_up(request):
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        auth_login(request, user)
        return redirect("account")
    return render(request, "website/signup.html", {"form": form})


@require_POST
def password_requirements(request):
    user = get_user_model()(
        username=request.POST.get("username", ""),
        email=request.POST.get("email", ""),
    )
    password = request.POST.get("password", "")
    results = {"length": False, "common": False, "numeric": False}
    validator_keys = (
        (MinimumLengthValidator, "length"),
        (CommonPasswordValidator, "common"),
        (NumericPasswordValidator, "numeric"),
    )
    for validator in get_default_password_validators():
        for validator_type, key in validator_keys:
            if isinstance(validator, validator_type):
                try:
                    validator.validate(password, user)
                except ValidationError:
                    results[key] = False
                else:
                    results[key] = True
    return JsonResponse(results)


def sign_in(request):
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        auth_login(request, form.get_user())
        return redirect("account")
    return render(request, "website/login.html", {"form": form})


@require_POST
def sign_out(request):
    from django.contrib.auth import logout

    logout(request)
    return redirect("home")


@login_required
def account(request):
    return render(request, "website/account.html", {
        "orders": request.user.orders.all(),
    })


@login_required
def order_detail(request, order_number):
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product"),
        number=order_number,
        user=request.user,
    )
    return render(request, "website/order_detail.html", {"order": order})


def information_page(request, page):
    titles = {
        "privacy": "Privacy Policy",
        "terms": "Terms & Conditions",
        "shipping": "Shipping Policy",
        "returns": "Returns / Refund Policy",
        "contact": "Contact",
        "faq": "FAQ",
    }
    if page not in titles:
        raise Http404
    return render(request, "website/information.html", {
        "title": titles[page],
        "page": page,
    })
