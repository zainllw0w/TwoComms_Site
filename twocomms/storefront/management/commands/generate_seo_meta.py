"""
Django команда для генерации и обновления SEO мета-тегов
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from storefront.models import Product, Category
from storefront.seo_utils import SEOKeywordGenerator, SEOMetaGenerator
import json


class Command(BaseCommand):
    help = 'Генерирует SEO мета-теги для товаров и категорий'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет сделано без внесения изменений',
        )
        parser.add_argument(
            '--type',
            choices=['products', 'categories', 'all'],
            default='all',
            help='Тип объектов для обработки',
        )
        parser.add_argument(
            '--product-id',
            type=int,
            help='Обработать только конкретный товар',
        )
        parser.add_argument(
            '--category-id',
            type=int,
            help='Обработать только конкретную категорию',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        object_type = options['type']
        product_id = options.get('product_id')
        category_id = options.get('category_id')

        if dry_run:
            self.stdout.write(
                self.style.WARNING('РЕЖИМ ПРЕДВАРИТЕЛЬНОГО ПРОСМОТРА - изменения не будут сохранены')
            )

        if object_type in ['products', 'all']:
            self.process_products(dry_run, product_id)

        if object_type in ['categories', 'all']:
            self.process_categories(dry_run, category_id)

    def process_products(self, dry_run, product_id=None):
        """Обрабатывает товары"""
        self.stdout.write(self.style.SUCCESS('=== ОБРАБОТКА ТОВАРОВ ==='))

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

        self.stdout.write(f'Начинаем обработку {total_products} товаров...')

        for product in products:
            processed_products += 1
            self.stdout.write(f'Обрабатываем товар {processed_products}/{total_products}: {product.title}')

            # Генерируем мета-теги
            meta_data = SEOMetaGenerator.generate_product_meta(product)
            keywords = SEOKeywordGenerator.generate_product_keywords(product)

            self.stdout.write(f'  Title: {meta_data["title"]}')
            self.stdout.write(f'  Description: {meta_data["description"]}')
            self.stdout.write(f'  Keywords: {", ".join(keywords[:5])}...')

            if not dry_run:
                # Здесь можно добавить поля в модель Product для хранения мета-тегов
                # product.meta_title = meta_data['title']
                # product.meta_description = meta_data['description']
                # product.meta_keywords = meta_data['keywords']
                # product.save()
                pass

            # Предложения по улучшению
            suggestions = SEOContentOptimizer.suggest_content_improvements(product)
            if suggestions:
                self.stdout.write(f'  Предложения по улучшению:')
                for suggestion in suggestions:
                    self.stdout.write(f'    - {suggestion}')

        self.stdout.write(
            self.style.SUCCESS(f'Обработка товаров завершена! Обработано: {processed_products}')
        )

    def process_categories(self, dry_run, category_id=None):
        """Обрабатывает категории"""
        self.stdout.write(self.style.SUCCESS('=== ОБРАБОТКА КАТЕГОРИЙ ==='))

        if category_id:
            categories = Category.objects.filter(id=category_id)
            if not categories.exists():
                self.stdout.write(
                    self.style.ERROR(f'Категория с ID {category_id} не найдена')
                )
                return
        else:
            categories = Category.objects.all()

        total_categories = categories.count()
        processed_categories = 0

        self.stdout.write(f'Начинаем обработку {total_categories} категорий...')

        for category in categories:
            processed_categories += 1
            self.stdout.write(f'Обрабатываем категорию {processed_categories}/{total_categories}: {category.name}')

            # Генерируем мета-теги
            meta_data = SEOMetaGenerator.generate_category_meta(category)
            keywords = SEOKeywordGenerator.generate_category_keywords(category)

            self.stdout.write(f'  Title: {meta_data["title"]}')
            self.stdout.write(f'  Description: {meta_data["description"]}')
            self.stdout.write(f'  Keywords: {", ".join(keywords[:5])}...')

            if not dry_run:
                # Здесь можно добавить поля в модель Category для хранения мета-тегов
                # category.meta_title = meta_data['title']
                # category.meta_description = meta_data['description']
                # category.meta_keywords = meta_data['keywords']
                # category.save()
                pass

        self.stdout.write(
            self.style.SUCCESS(f'Обработка категорий завершена! Обработано: {processed_categories}')
        )

    def generate_seo_report(self, products, categories):
        """Генерирует отчет по SEO состоянию"""
        report = {
            'products': {
                'total': products.count(),
                'with_description': products.exclude(description='').count(),
                'with_main_image': products.exclude(main_image='').count(),
                'with_discount': products.filter(has_discount=True).count(),
            },
            'categories': {
                'total': categories.count(),
                'with_description': categories.exclude(description='').count(),
                'with_cover': categories.exclude(cover='').count(),
            }
        }

        self.stdout.write(self.style.SUCCESS('=== SEO ОТЧЕТ ==='))
        self.stdout.write(f'Товары:')
        self.stdout.write(f'  Всего: {report["products"]["total"]}')
        self.stdout.write(f'  С описанием: {report["products"]["with_description"]}')
        self.stdout.write(f'  С изображением: {report["products"]["with_main_image"]}')
        self.stdout.write(f'  Со скидкой: {report["products"]["with_discount"]}')
        
        self.stdout.write(f'Категории:')
        self.stdout.write(f'  Всего: {report["categories"]["total"]}')
        self.stdout.write(f'  С описанием: {report["categories"]["with_description"]}')
        self.stdout.write(f'  С обложкой: {report["categories"]["with_cover"]}')

        return report
