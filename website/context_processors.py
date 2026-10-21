from store.models import Cart


def bag_count(request):
    session_key = request.session.session_key
    count = 0
    if session_key:
        cart = Cart.objects.filter(session_key=session_key).first()
        if cart:
            count = sum(cart.items.values_list("quantity", flat=True))
    return {"bag_count": count}
