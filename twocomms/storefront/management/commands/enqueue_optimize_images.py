from pathlib import Path

from django.core.management.base import BaseCommand
from django.apps import apps

from storefront.models import Product, ProductImage, Category, CatalogOptionValue, SizeGrid, PrintProposal
from productcolors.models import ProductColorImage

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
        parser.add_argument(
            '--local',
            action='store_true',
            help='Выполнять оптимизацию синхронно (без Celery). Используйте с маленьким limit на слабом хостинге.'
        )
        parser.add_argument(
            '--fallback-local',
            action='store_true',
            help='Если отправка в Celery не удалась — выполнить синхронно.'
        )
        parser.add_argument(
            '--sleep',
            type=float,
            default=0.0,
            help='Пауза в секундах между заданиями при локальном выполнении.'
        )

    def handle(self, *args, **options):
        from storefront.tasks import optimize_image_field_task  # импортируем внутри, чтобы избежать проблем с PYTHONPATH

        steps = {s.strip() for s in (options.get('steps') or '').split(',') if s.strip()}
        limit = options.get('limit')
        offset = options.get('offset') or 0
        enqueued = 0
        local = options.get('local', False)
        fallback_local = options.get('fallback_local', False)
        sleep = float(options.get('sleep') or 0)

        def _maybe_stop():
            return limit is not None and enqueued >= limit

        def _dispatch(model_label, obj_id, field):
            nonlocal enqueued
            if local:
                optimize_image_field_task.run(model_label, obj_id, field)
            else:
                try:
                    optimize_image_field_task.delay(model_label, obj_id, field)
                except Exception as exc:
                    if fallback_local:
                        optimize_image_field_task.run(model_label, obj_id, field)
                    else:
                        raise
            enqueued += 1
            if sleep > 0 and local:
                import time
                time.sleep(sleep)

        # Product main_image
        if 'product_main' in steps:
            qs = Product.objects.exclude(main_image='').only('id', 'main_image')[offset:limit + offset if limit else None]
            for p in qs:
                _dispatch(p._meta.label, p.id, 'main_image')
                if _maybe_stop():
                    self._print_done(enqueued)
                    return

        # Product extra images
        if 'product_extra' in steps and not _maybe_stop():
            qs = ProductImage.objects.exclude(image='').only('id', 'image')[offset:limit + offset if limit else None]
            for img in qs:
                _dispatch(img._meta.label, img.id, 'image')
                if _maybe_stop():
                    self._print_done(enqueued)
                    return

        # Color images
        if 'color' in steps and not _maybe_stop():
            qs = ProductColorImage.objects.exclude(image='').only('id', 'image')[offset:limit + offset if limit else None]
            for img in qs:
                _dispatch(img._meta.label, img.id, 'image')
                if _maybe_stop():
                    self._print_done(enqueued)
                    return

        # Categories icon/cover
        if 'category' in steps and not _maybe_stop():
            qs = Category.objects.only('id', 'icon', 'cover')[offset:limit + offset if limit else None]
            for cat in qs:
                if cat.icon:
                    _dispatch(cat._meta.label, cat.id, 'icon')
                if _maybe_stop():
                    self._print_done(enqueued)
                    return
                if cat.cover:
                    _dispatch(cat._meta.label, cat.id, 'cover')
                if _maybe_stop():
                    self._print_done(enqueued)
                    return

        # Catalog options
        if 'option' in steps and not _maybe_stop():
            qs = CatalogOptionValue.objects.exclude(image='').only('id', 'image')[offset:limit + offset if limit else None]
            for opt in qs:
                _dispatch(opt._meta.label, opt.id, 'image')
                if _maybe_stop():
                    self._print_done(enqueued)
                    return

        # Size grids
        if 'size' in steps and not _maybe_stop():
            qs = SizeGrid.objects.exclude(image='').only('id', 'image')[offset:limit + offset if limit else None]
            for grid in qs:
                _dispatch(grid._meta.label, grid.id, 'image')
                if _maybe_stop():
                    self._print_done(enqueued)
                    return

        # Print proposals
        if 'proposal' in steps and not _maybe_stop():
            qs = PrintProposal.objects.exclude(image='').only('id', 'image')[offset:limit + offset if limit else None]
            for prop in qs:
                _dispatch(prop._meta.label, prop.id, 'image')
                if _maybe_stop():
                    self._print_done(enqueued)
                    return

        self._print_done(enqueued)

    def _print_done(self, enqueued):
        self.stdout.write(self.style.SUCCESS(f'Enqueued {enqueued} optimize_image tasks.'))
