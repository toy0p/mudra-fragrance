from decimal import Decimal

from django.db import migrations


def add_mens_demo_products(apps, schema_editor):
    Category = apps.get_model("store", "Category")
    Product = apps.get_model("store", "Product")
    category = Category.objects.filter(slug="mens").first()
    if not category:
        return

    for number in (1, 2):
        slug = f"mens-product-{number:02d}"
        Product.objects.get_or_create(
            slug=slug,
            defaults={
                "name": f"MENS PRODUCT {number:02d}",
                "category": category,
                "description": "Temporary demo product.",
                "price": Decimal("0.00"),
                "stock": 10,
                "is_active": True,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0004_order_orderitem"),
    ]

    operations = [
        migrations.RunPython(add_mens_demo_products, migrations.RunPython.noop),
    ]
