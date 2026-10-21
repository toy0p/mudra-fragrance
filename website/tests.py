from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from store.models import Cart, CartItem, Category, Order, Product


class StoreFlowTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="MENS", slug="mens")
        self.product = Product.objects.create(
            name="Test fragrance",
            slug="test-fragrance",
            category=self.category,
            description="Test product",
            price=Decimal("125.00"),
            stock=5,
        )
        self.ajax = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}

    def test_add_existing_product_does_not_duplicate_quantity(self):
        url = reverse("add_to_cart", args=[self.product.slug])
        first_response = self.client.post(url, **self.ajax)
        response = self.client.post(url, **self.ajax)

        self.assertEqual(first_response.json()["count"], 1)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["quantity"], 1)
        self.assertTrue(response.json()["open_cart"])
        self.assertContains(self.client.get(reverse("home")), 'class="bag-count" aria-live="polite">1')

    def test_adding_existing_product_redirects_to_cart_without_incrementing(self):
        url = reverse("add_to_cart", args=[self.product.slug])
        self.client.post(url, **self.ajax)

        response = self.client.post(url, {"add_to_bag": "1"}, **self.ajax)

        self.assertTrue(response.json()["open_cart"])
        self.assertTrue(response.json()["already_added"])
        self.assertEqual(CartItem.objects.get(product=self.product).quantity, 1)

    def test_cart_drawer_renders_items_and_checkout_action(self):
        self.client.post(reverse("add_to_cart", args=[self.product.slug]), **self.ajax)

        response = self.client.get(reverse("cart_drawer"))

        self.assertContains(response, self.product.name)
        self.assertContains(response, "CHECKOUT")
        self.assertContains(response, "data-cart-scope")

    def test_shop_shows_added_state_for_cart_products(self):
        self.client.post(reverse("add_to_cart", args=[self.product.slug]), **self.ajax)

        response = self.client.get(reverse("shop"))

        self.assertContains(response, 'data-already-added="true"')
        self.assertContains(response, ">ADDED</button>")

    def test_buy_now_adds_product_and_redirects_to_checkout(self):
        response = self.client.post(
            reverse("add_to_cart", args=[self.product.slug]),
            {"buy_now": "1"},
            **self.ajax,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["redirect"], reverse("checkout"))
        self.assertEqual(CartItem.objects.get(product=self.product).quantity, 1)

    def test_product_cards_include_add_to_bag_and_buy_now(self):
        response = self.client.get(reverse("shop"))
        self.assertContains(response, "ADD TO BAG")
        self.assertContains(response, 'name="buy_now" value="1"')

    def test_mens_category_shows_each_assigned_product_with_both_actions(self):
        self.product.is_active = False
        self.product.save(update_fields=["is_active"])
        Product.objects.create(
            name="MENS PRODUCT 01",
            slug="mens-product-01",
            category=self.category,
            description="Temporary demo product.",
            price=Decimal("0.00"),
            stock=10,
        )
        Product.objects.create(
            name="MENS PRODUCT 02",
            slug="mens-product-02",
            category=self.category,
            description="Temporary demo product.",
            price=Decimal("0.00"),
            stock=10,
        )

        response = self.client.get(reverse("shop"), {"category": self.category.slug})
        self.assertContains(response, "MENS PRODUCT 01")
        self.assertContains(response, "MENS PRODUCT 02")
        self.assertContains(response, "ADD TO BAG", count=2)
        self.assertContains(response, 'name="buy_now" value="1"', count=2)

    def test_decrease_to_zero_removes_cart_item(self):
        self.client.post(reverse("add_to_cart", args=[self.product.slug]), **self.ajax)
        item = CartItem.objects.get(product=self.product)
        url = reverse("update_cart_item", args=[item.pk])

        response = self.client.post(url, {"action": "decrease"}, **self.ajax)
        self.assertEqual(response.json()["count"], 0)
        self.assertEqual(response.json()["quantity"], 0)
        self.assertFalse(CartItem.objects.filter(pk=item.pk).exists())

    def test_remove_response_marks_item_removed(self):
        self.client.post(reverse("add_to_cart", args=[self.product.slug]), **self.ajax)
        item = CartItem.objects.get(product=self.product)

        response = self.client.post(
            reverse("remove_cart_item", args=[item.pk]),
            **self.ajax,
        )
        self.assertEqual(response.json()["quantity"], 0)
        self.assertTrue(response.json()["empty"])
        self.assertFalse(CartItem.objects.filter(pk=item.pk).exists())

    def test_set_quantity_supports_batched_quantity_changes(self):
        self.client.post(reverse("add_to_cart", args=[self.product.slug]), **self.ajax)
        item = CartItem.objects.get(product=self.product)

        response = self.client.post(
            reverse("update_cart_item", args=[item.pk]),
            {"action": "set", "quantity": "4"},
            **self.ajax,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["quantity"], 4)
        self.assertEqual(response.json()["count"], 4)

    def test_set_quantity_rejects_exceeding_stock(self):
        self.client.post(reverse("add_to_cart", args=[self.product.slug]), **self.ajax)
        item = CartItem.objects.get(product=self.product)

        response = self.client.post(
            reverse("update_cart_item", args=[item.pk]),
            {"action": "set", "quantity": "6"},
            **self.ajax,
        )
        self.assertEqual(response.status_code, 409)
        item.refresh_from_db()
        self.assertEqual(item.quantity, 1)

    def test_cart_mutation_cannot_access_another_session_cart(self):
        cart = Cart.objects.create(session_key="another-session")
        item = CartItem.objects.create(cart=cart, product=self.product)

        response = self.client.post(
            reverse("remove_cart_item", args=[item.pk]),
            **self.ajax,
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(CartItem.objects.filter(pk=item.pk).exists())

    def test_guest_checkout_creates_order_with_price_snapshot(self):
        self.client.post(reverse("add_to_cart", args=[self.product.slug]), **self.ajax)
        response = self.client.post(reverse("checkout"), {
            "customer_name": "Test Customer",
            "email": "customer@example.test",
            "phone": "0000000000",
            "delivery_address": "Test address",
        })

        order = Order.objects.get()
        self.assertRedirects(
            response,
            reverse("order_confirmation", args=[order.number]),
        )
        self.assertEqual(order.total, Decimal("125.00"))
        self.assertEqual(order.items.get().product_price, Decimal("125.00"))
        self.assertIsNone(order.user)
        self.assertFalse(CartItem.objects.exists())

    def test_order_detail_is_limited_to_owner(self):
        owner = User.objects.create_user(username="owner", password="SafePassword-123!")
        order = Order.objects.create(
            user=owner,
            customer_name="Owner",
            email="owner@example.test",
            phone="000",
            delivery_address="Address",
            total=Decimal("125.00"),
        )
        self.client.force_login(User.objects.create_user(
            username="other",
            password="SafePassword-123!",
        ))

        response = self.client.get(reverse("order_detail", args=[order.number]))
        self.assertEqual(response.status_code, 404)

    def test_signup_and_login_pages_render(self):
        response = self.client.get(reverse("signup"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "too similar")
        self.assertContains(response, "At least 8 characters")
        self.assertEqual(self.client.get(reverse("login")).status_code, 200)

    def test_password_requirements_hide_each_met_rule(self):
        url = reverse("password_requirements")
        response = self.client.post(url, {
            "username": "customer",
            "email": "customer@example.test",
            "password": "safe-password-723",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "length": True,
            "common": True,
            "numeric": True,
        })
        response = self.client.post(url, {
            "username": "customer",
            "email": "customer@example.test",
            "password": "12345678",
        })
        self.assertEqual(response.json(), {
            "length": True,
            "common": False,
            "numeric": False,
        })

    def test_signup_login_and_logout(self):
        response = self.client.post(reverse("signup"), {
            "username": "customer",
            "email": "customer@example.test",
            "password1": "SafeLongPassword-723!",
            "password2": "SafeLongPassword-723!",
        })
        self.assertRedirects(response, reverse("account"))
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("home"))

        response = self.client.post(reverse("login"), {
            "username": "customer",
            "password": "SafeLongPassword-723!",
        })
        self.assertRedirects(response, reverse("account"))

    def test_product_search_and_category_filter(self):
        response = self.client.get(reverse("shop"), {
            "q": "Test",
            "category": self.category.slug,
        })
        self.assertContains(response, self.product.name)
        self.assertEqual(response.context["products"].count(), 1)
        self.assertNotContains(response, "WOMENS PRODUCT")

    def test_products_page_shows_search_without_category_dropdown(self):
        response = self.client.get(reverse("shop"))
        self.assertContains(response, ">SEARCH</button>")
        self.assertNotContains(response, "All categories")
        self.assertNotContains(response, "SEARCH / FILTER")

    def test_empty_category_displays_an_empty_state_card(self):
        Category.objects.create(name="UNISEX", slug="unisex")
        response = self.client.get(reverse("shop"))
        mens_group = next(
            group for group in response.context["category_cards"]
            if group["category"].slug == "unisex"
        )

        self.assertEqual(mens_group["products"], [])
        self.assertContains(response, "UNISEX")
        self.assertContains(response, "No matching products")

    def test_stock_one_product_can_be_added(self):
        self.product.stock = 1
        self.product.save(update_fields=["stock"])

        response = self.client.post(
            reverse("add_to_cart", args=[self.product.slug]),
            **self.ajax,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)

    def test_checkout_page_and_empty_cart_guard(self):
        response = self.client.get(reverse("checkout"))
        self.assertRedirects(response, reverse("cart"))

        self.client.post(reverse("add_to_cart", args=[self.product.slug]), **self.ajax)
        self.assertEqual(self.client.get(reverse("checkout")).status_code, 200)

    def test_information_pages_render(self):
        for page in ("privacy", "terms", "shipping", "returns", "contact", "faq"):
            with self.subTest(page=page):
                self.assertEqual(
                    self.client.get(reverse("information", args=[page])).status_code,
                    200,
                )
