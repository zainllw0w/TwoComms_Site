"""Генерує візуальні відбитки товарів для матчингу IG-бота (Gemini-vision).

Запуск (з venv, на сервері або локально):
    python manage.py generate_bot_fingerprints              # усі, що ПОТРЕБУЮТЬ
    python manage.py generate_bot_fingerprints --limit 12   # лише 12 товарів, що потребують
    python manage.py generate_bot_fingerprints --sleep 2    # пауза 2с між товарами (щадити квоту)
    python manage.py generate_bot_fingerprints --force      # перегенерувати все
    python manage.py generate_bot_fingerprints --product 123

Команда РЕЗЮМОВАНА: товари з готовими відбитками пропускаються БЕЗ виклику vision
(дешево), тож кронами малими батчами база поступово заповнюється в межах квоти,
включно з новими товарами. --limit рахує лише товари, ЩО ПОТРЕБУЮТЬ обробки.
"""
import time

from django.core.management.base import BaseCommand

from management.services import bot_vision


class Command(BaseCommand):
    help = "Генерує bot_vision-відбитки варіантів товарів для матчингу IG-бота."

    def add_arguments(self, parser):
        parser.add_argument("--product", type=int, default=None, help="ID конкретного товару")
        parser.add_argument("--limit", type=int, default=0, help="Макс. товарів, ЩО ПОТРЕБУЮТЬ обробки")
        parser.add_argument("--force", action="store_true", help="Перегенерувати наявні відбитки")
        parser.add_argument("--sleep", type=float, default=0.0, help="Пауза між товарами, с (щадити квоту)")

    def handle(self, *args, **opts):
        from storefront.models import Product, ProductStatus

        qs = Product.objects.all()
        if opts.get("product"):
            qs = qs.filter(id=opts["product"])
        else:
            qs = qs.filter(status=ProductStatus.PUBLISHED)
        qs = qs.order_by("-featured", "-id").prefetch_related("color_variants")

        limit = opts.get("limit") or 0
        force = bool(opts.get("force"))
        sleep_s = float(opts.get("sleep") or 0)

        worked = 0
        skipped = 0
        total_variants = 0
        for product in qs:
            variants = list(product.color_variants.all())
            needs = force or any(not (v.metadata or {}).get("bot_vision") for v in variants)
            if not needs:
                skipped += 1
                continue
            if limit and worked >= limit:
                break
            n = bot_vision.fingerprint_product(product, force=force)
            worked += 1  # рахуємо навіть n==0 (vision міг не відповісти) — щоб не зациклитись
            total_variants += n
            if n:
                self.stdout.write(f"  #{product.id} {product.title}: +{n}")
            if sleep_s:
                time.sleep(sleep_s)

        self.stdout.write(
            self.style.SUCCESS(
                f"Оброблено товарів: {worked}, відбитків створено: {total_variants}, "
                f"пропущено готових: {skipped}"
            )
        )
