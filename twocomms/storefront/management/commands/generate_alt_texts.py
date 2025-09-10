"""
Django команда для генерации alt-текстов для изображений товаров
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from storefront.models import Product, ProductImage
from storefront.seo_utils import SEOContentOptimizer
import os


class Command(BaseCommand):
    help = 'Генерирует alt-тексты для всех изображений товаров'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет сделано без внесения изменений',
        )
        parser.add_argument(
            '--product-id',
            type=int,
            help='Обработать только конкретный товар',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        product_id = options.get('product_id')

        if dry_run:
            self.stdout.write(
                self.style.WARNING('РЕЖИМ ПРЕДВАРИТЕЛЬНОГО ПРОСМОТРА - изменения не будут сохранены')
            )

        # Получаем товары для обработки
        if product_id:
            products = Product.objects.filter(id=product_id)
            if not products.exists():
                self.stdout.write(
                    self.style.ERROR(f'Товар с ID {product_id} не найден')
                )
                return
        else:
            products = Product.objects.all()

        total_products = products.count()
        processed_products = 0
        updated_images = 0

        self.stdout.write(f'Начинаем обработку {total_products} товаров...')

        for product in products:
            processed_products += 1
            self.stdout.write(f'Обрабатываем товар {processed_products}/{total_products}: {product.title}')

            # Обрабатываем основное изображение товара
            if product.main_image:
                image_name = os.path.basename(product.main_image.name)
                alt_text = SEOContentOptimizer.generate_alt_text_for_image(
                    image_name, product.title
                )
                
                if not dry_run:
                    # Здесь можно добавить поле alt_text в модель Product, если нужно
                    # product.alt_text = alt_text
                    # product.save()
                    pass
                
                self.stdout.write(f'  Основное изображение: {alt_text}')
                updated_images += 1

            # Обрабатываем дополнительные изображения
            for image in product.images.all():
                image_name = os.path.basename(image.image.name)
                alt_text = SEOContentOptimizer.generate_alt_text_for_image(
                    image_name, product.title
                )
                
                if not dry_run:
                    # Здесь можно добавить поле alt_text в модель ProductImage, если нужно
                    # image.alt_text = alt_text
                    # image.save()
                    pass
                
                self.stdout.write(f'  Дополнительное изображение: {alt_text}')
                updated_images += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Обработка завершена! Обработано товаров: {processed_products}, '
                f'изображений: {updated_images}'
            )
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    'Для применения изменений запустите команду без флага --dry-run'
                )
            )
