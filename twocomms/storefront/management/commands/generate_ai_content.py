"""
Django команда для генерации AI-контента для всех товаров и категорий
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from storefront.models import Product, Category
from storefront.seo_utils import SEOKeywordGenerator, SEOContentOptimizer
from django.conf import settings
import os


class Command(BaseCommand):
    help = 'Генерирует AI-контент для всех товаров и категорий'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет сделано без внесения изменений',
        )
        parser.add_argument(
            '--products-only',
            action='store_true',
            help='Обработать только товары',
        )
        parser.add_argument(
            '--categories-only',
            action='store_true',
            help='Обработать только категории',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Перегенерировать контент даже если он уже существует',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        products_only = options['products_only']
        categories_only = options['categories_only']
        force = options['force']

        if dry_run:
            self.stdout.write(
                self.style.WARNING('РЕЖИМ ПРЕДВАРИТЕЛЬНОГО ПРОСМОТРА - изменения не будут сохранены')
            )

        # Проверяем настройки AI
        api_key = getattr(settings, 'OPENAI_API_KEY', None) or os.environ.get('OPENAI_API_KEY')
        if not api_key:
            self.stdout.write(
                self.style.ERROR('OPENAI_API_KEY не настроен. Установите переменную окружения.')
            )
            return

        use_keywords = getattr(settings, 'USE_AI_KEYWORDS', False)
        use_descriptions = getattr(settings, 'USE_AI_DESCRIPTIONS', False)
        
        if not use_keywords and not use_descriptions:
            self.stdout.write(
                self.style.WARNING('USE_AI_KEYWORDS и USE_AI_DESCRIPTIONS отключены. Включите их в настройках.')
            )
            return

        processed_products = 0
        processed_categories = 0
        errors = 0

        # Обрабатываем товары
        if not categories_only:
            self.stdout.write('Обрабатываем товары...')
            products = Product.objects.all()
            
            for product in products:
                try:
                    # Пропускаем если контент уже сгенерирован и не принудительная генерация
                    if not force and product.ai_content_generated:
                        continue
                    
                    processed_products += 1
                    self.stdout.write(f'Товар {processed_products}: {product.title}')
                    
                    if not dry_run:
                        with transaction.atomic():
                            # Генерируем AI-ключевые слова
                            if use_keywords:
                                ai_keywords = SEOKeywordGenerator.generate_product_keywords_ai(product)
                                if ai_keywords:
                                    product.ai_keywords = ', '.join(ai_keywords)
                                    self.stdout.write(f'  AI-ключевые слова: {len(ai_keywords)} слов')
                            
                            # Генерируем AI-описание
                            if use_descriptions:
                                ai_description = SEOContentOptimizer.generate_ai_product_description(product)
                                if ai_description:
                                    product.ai_description = ai_description
                                    self.stdout.write(f'  AI-описание: {len(ai_description)} символов')
                            
                            # Отмечаем что контент сгенерирован
                            if (use_keywords and product.ai_keywords) or (use_descriptions and product.ai_description):
                                product.ai_content_generated = True
                                product.save()
                                self.stdout.write(f'  ✅ Сохранено')
                            else:
                                self.stdout.write(f'  ⚠️ AI-контент не сгенерирован')
                    
                except Exception as e:
                    errors += 1
                    self.stdout.write(
                        self.style.ERROR(f'Ошибка при обработке товара {product.id}: {str(e)}')
                    )

        # Обрабатываем категории
        if not products_only:
            self.stdout.write('Обрабатываем категории...')
            categories = Category.objects.all()
            
            for category in categories:
                try:
                    # Пропускаем если контент уже сгенерирован и не принудительная генерация
                    if not force and category.ai_content_generated:
                        continue
                    
                    processed_categories += 1
                    self.stdout.write(f'Категория {processed_categories}: {category.name}')
                    
                    if not dry_run:
                        with transaction.atomic():
                            # Генерируем AI-ключевые слова
                            if use_keywords:
                                ai_keywords = SEOKeywordGenerator.generate_category_keywords_ai(category)
                                if ai_keywords:
                                    category.ai_keywords = ', '.join(ai_keywords)
                                    self.stdout.write(f'  AI-ключевые слова: {len(ai_keywords)} слов')
                            
                            # Генерируем AI-описание
                            if use_descriptions:
                                ai_description = SEOContentOptimizer.generate_ai_category_description(category)
                                if ai_description:
                                    category.ai_description = ai_description
                                    self.stdout.write(f'  AI-описание: {len(ai_description)} символов')
                            
                            # Отмечаем что контент сгенерирован
                            if (use_keywords and category.ai_keywords) or (use_descriptions and category.ai_description):
                                category.ai_content_generated = True
                                category.save()
                                self.stdout.write(f'  ✅ Сохранено')
                            else:
                                self.stdout.write(f'  ⚠️ AI-контент не сгенерирован')
                    
                except Exception as e:
                    errors += 1
                    self.stdout.write(
                        self.style.ERROR(f'Ошибка при обработке категории {category.id}: {str(e)}')
                    )

        # Итоговая статистика
        self.stdout.write(
            self.style.SUCCESS(
                f'Обработка завершена! '
                f'Товаров: {processed_products}, '
                f'Категорий: {processed_categories}, '
                f'Ошибок: {errors}'
            )
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    'Для применения изменений запустите команду без флага --dry-run'
                )
            )
