from pathlib import Path

from django.core.management.base import BaseCommand
from django.apps import apps

from storefront.models import Product, ProductImage, Category, CatalogOptionValue, SizeGrid, PrintProposal
from productcolors.models import ProductColorImage
from storefront.tasks import optimize_image_field_task


class Command(BaseCommand):
    """
    Лёгкая команда, ставящая задачи Celery на оптимизацию изображений.
    Не выполняет конвертацию локально (минимум CPU на хостинге).
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Максимальное количество задач на один запуск'
        )
        parser.add_argument(
            '--offset',
            type=int,
            default=0,
            help='Смещение для выборки (для батчевого запуска)'
        )
        parser.add_argument(
            '--steps',
            type=str,
            default='product_main,product_extra,color,category,option,size,proposal',
            help='Через запятую: product_main,product_extra,color,category,option,size,proposal'
        )

    def handle(self, *args, **options):
        steps = {s.strip() for s in (options.get('steps') or '').split(',') if s.strip()}
        limit = options.get('limit')
        offset = options.get('offset') or 0
        enqueued = 0

        def _maybe_stop():
            return limit is not None and enqueued >= limit

        # Product main_image
        if 'product_main' in steps:
            qs = Product.objects.exclude(main_image='').only('id', 'main_image')[offset:limit + offset if limit else None]
            for p in qs:
                optimize_image_field_task.delay(p._meta.label, p.id, 'main_image')
                enqueued += 1
                if _maybe_stop():
                    self._print_done(enqueued)
                    return

        # Product extra images
        if 'product_extra' in steps and not _maybe_stop():
            qs = ProductImage.objects.exclude(image='').only('id', 'image')[offset:limit + offset if limit else None]
            for img in qs:
                optimize_image_field_task.delay(img._meta.label, img.id, 'image')
                enqueued += 1
                if _maybe_stop():
                    self._print_done(enqueued)
                    return

        # Color images
        if 'color' in steps and not _maybe_stop():
            qs = ProductColorImage.objects.exclude(image='').only('id', 'image')[offset:limit + offset if limit else None]
            for img in qs:
                optimize_image_field_task.delay(img._meta.label, img.id, 'image')
                enqueued += 1
                if _maybe_stop():
                    self._print_done(enqueued)
                    return

        # Categories icon/cover
        if 'category' in steps and not _maybe_stop():
            qs = Category.objects.only('id', 'icon', 'cover')[offset:limit + offset if limit else None]
            for cat in qs:
                if cat.icon:
                    optimize_image_field_task.delay(cat._meta.label, cat.id, 'icon')
                    enqueued += 1
                if _maybe_stop():
                    self._print_done(enqueued)
                    return
                if cat.cover:
                    optimize_image_field_task.delay(cat._meta.label, cat.id, 'cover')
                    enqueued += 1
                if _maybe_stop():
                    self._print_done(enqueued)
                    return

        # Catalog options
        if 'option' in steps and not _maybe_stop():
            qs = CatalogOptionValue.objects.exclude(image='').only('id', 'image')[offset:limit + offset if limit else None]
            for opt in qs:
                optimize_image_field_task.delay(opt._meta.label, opt.id, 'image')
                enqueued += 1
                if _maybe_stop():
                    self._print_done(enqueued)
                    return

        # Size grids
        if 'size' in steps and not _maybe_stop():
            qs = SizeGrid.objects.exclude(image='').only('id', 'image')[offset:limit + offset if limit else None]
            for grid in qs:
                optimize_image_field_task.delay(grid._meta.label, grid.id, 'image')
                enqueued += 1
                if _maybe_stop():
                    self._print_done(enqueued)
                    return

        # Print proposals
        if 'proposal' in steps and not _maybe_stop():
            qs = PrintProposal.objects.exclude(image='').only('id', 'image')[offset:limit + offset if limit else None]
            for prop in qs:
                optimize_image_field_task.delay(prop._meta.label, prop.id, 'image')
                enqueued += 1
                if _maybe_stop():
                    self._print_done(enqueued)
                    return

        self._print_done(enqueued)

    def _print_done(self, enqueued):
        self.stdout.write(self.style.SUCCESS(f'Enqueued {enqueued} optimize_image tasks.'))
