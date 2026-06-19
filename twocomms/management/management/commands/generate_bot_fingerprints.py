"""Генерує візуальні відбитки товарів для матчингу IG-бота (Gemini-vision).

Запуск (з venv, на сервері або локально):
    python manage.py generate_bot_fingerprints            # усі опубліковані без відбитка
    python manage.py generate_bot_fingerprints --force    # перегенерувати всі
    python manage.py generate_bot_fingerprints --product 123
    python manage.py generate_bot_fingerprints --limit 20

Безпечно ганяти кроном раз на добу — нові/змінені товари отримають відбиток.
"""
from django.core.management.base import BaseCommand

from management.services import bot_vision


class Command(BaseCommand):
    help = "Генерує bot_vision-відбитки варіантів товарів для матчингу IG-бота."

    def add_arguments(self, parser):
        parser.add_argument("--product", type=int, default=None, help="ID конкретного товару")
        parser.add_argument("--limit", type=int, default=0, help="Обмежити к-сть товарів")
        parser.add_argument("--force", action="store_true", help="Перегенерувати наявні відбитки")

    def handle(self, *args, **opts):
        from storefront.models import Product, ProductStatus

        qs = Product.objects.all()
        if opts.get("product"):
            qs = qs.filter(id=opts["product"])
        else:
            qs = qs.filter(status=ProductStatus.PUBLISHED)
        qs = qs.order_by("-featured", "-id")
        limit = opts.get("limit") or 0
        if limit:
            qs = qs[:limit]

        total_products = 0
        total_variants = 0
        force = bool(opts.get("force"))
        for product in qs:
            n = bot_vision.fingerprint_product(product, force=force)
            total_products += 1
            total_variants += n
            if n:
                self.stdout.write(f"  #{product.id} {product.title}: {n} варіантів")

        self.stdout.write(
            self.style.SUCCESS(
                f"Готово: {total_products} товарів проглянуто, {total_variants} варіантів оброблено."
            )
        )
