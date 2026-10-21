from django.contrib import admin
from .models import Category, Order, OrderItem, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "stock", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("name", "description", "fragrance_notes")
    prepopulated_fields = {"slug": ("name",)}


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product_price",)
    fields = ("product", "quantity", "product_price")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("number", "customer_name", "total", "payment_status", "status", "created_at")
    list_filter = ("payment_status", "status", "created_at")
    search_fields = ("number", "customer_name", "email")
    readonly_fields = ("number", "user", "customer_name", "email", "phone", "delivery_address", "total", "created_at")
    inlines = (OrderItemInline,)
