"""
Django команда для генерации alt-текстов для изображений без них
"""

from django.core.management.base import BaseCommand

from storefront.models import Product, Category, ProductImage
from productcolors.models import ProductColorImage


class Command(BaseCommand):
    help = 'Генерирует alt-тексты для изображений без них'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет сделано без изменений',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Перезаписать существующие alt-тексты',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']

        self.stdout.write(
            self.style.SUCCESS('🚀 Генерация alt-текстов для TwoComms...')
        )

        results = {
            'products_updated': 0,
            'categories_updated': 0,
            'product_images_updated': 0,
            'color_images_updated': 0,
            'total_generated': 0
        }

        # Обрабатываем товары
        results.update(self.process_products(dry_run, force))

        # Обрабатываем категории
        results.update(self.process_categories(dry_run, force))

        # Обрабатываем дополнительные изображения товаров
        results.update(self.process_product_images(dry_run, force))

        # Обрабатываем изображения цветовых вариантов
        results.update(self.process_color_images(dry_run, force))

        # Выводим результаты
        self.print_results(results, dry_run)

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(f'✅ Генерация завершена! Создано {results["total_generated"]} alt-текстов')
            )
        else:
            self.stdout.write(
                self.style.WARNING('🔍 Режим предварительного просмотра. Используйте без --dry-run для применения изменений.')
            )

    def process_products(self, dry_run=False, force=False):
        """Обрабатывает товары"""
        results = {'products_updated': 0, 'products_alt_generated': 0}

        products = Product.objects.all()

        for product in products:
            updated = False

            # Главное изображение товара
            if product.main_image and (not product.main_image_alt or force):
                alt_text = self.generate_product_alt_text(product, 'main')
                if not dry_run:
                    product.main_image_alt = alt_text
                    product.save(update_fields=['main_image_alt'])
                updated = True
                results['products_alt_generated'] += 1

            if updated:
                results['products_updated'] += 1

        return results

    def process_categories(self, dry_run=False, force=False):
        """Обрабатывает категории"""
        results = {'categories_updated': 0, 'categories_alt_generated': 0}

        categories = Category.objects.all()

        for category in categories:
            updated = False

            # Иконка категории
            if category.icon:
                # Предполагаем, что у категории есть поле icon_alt_text
                if hasattr(category, 'icon_alt_text') and (not category.icon_alt_text or force):
                    alt_text = self.generate_category_alt_text(category, 'icon')
                    if not dry_run:
                        category.icon_alt_text = alt_text
                        category.save(update_fields=['icon_alt_text'])
                    updated = True
                    results['categories_alt_generated'] += 1

            # Обложка категории
            if category.cover:
                # Предполагаем, что у категории есть поле cover_alt_text
                if hasattr(category, 'cover_alt_text') and (not category.cover_alt_text or force):
                    alt_text = self.generate_category_alt_text(category, 'cover')
                    if not dry_run:
                        category.cover_alt_text = alt_text
                        category.save(update_fields=['cover_alt_text'])
                    updated = True
                    results['categories_alt_generated'] += 1

            if updated:
                results['categories_updated'] += 1

        return results

    def process_product_images(self, dry_run=False, force=False):
        """Обрабатывает дополнительные изображения товаров"""
        results = {'product_images_updated': 0, 'product_images_alt_generated': 0}

        product_images = ProductImage.objects.all()

        for product_image in product_images:
            if not product_image.alt_text or force:
                alt_text = self.generate_product_alt_text(
                    product_image.product,
                    'gallery',
                    photo_number=product_image.id
                )
                if not dry_run:
                    product_image.alt_text = alt_text
                    product_image.save(update_fields=['alt_text'])
                results['product_images_updated'] += 1
                results['product_images_alt_generated'] += 1

        return results

    def process_color_images(self, dry_run=False, force=False):
        """Обрабатывает изображения цветовых вариантов"""
        results = {'color_images_updated': 0, 'color_images_alt_generated': 0}

        color_images = ProductColorImage.objects.select_related('variant__product', 'variant__color').all()

        for color_image in color_images:
            if not color_image.alt_text or force:
                alt_text = self.generate_color_variant_alt_text(color_image)
                if not dry_run:
                    color_image.alt_text = alt_text
                    color_image.save(update_fields=['alt_text'])
                results['color_images_updated'] += 1
                results['color_images_alt_generated'] += 1

        return results

    def generate_product_alt_text(self, product, image_type='main', photo_number=None):
        """Генерирует alt-текст для товара"""

        # Базовые компоненты
        product_title = product.title
        category_name = product.category.name if product.category else 'одяг'

        # Определяем тип товара
        product_type = self.detect_product_type(product_title, category_name)

        # Определяем цвет из названия
        color = self.detect_color_from_title(product_title)

        # Генерируем alt-текст в зависимости от типа изображения
        if image_type == 'main':
            alt_text = f"{product_title} - {color} {product_type} TwoComms"
        elif image_type == 'gallery':
            photo_num = f" {photo_number}" if photo_number else ""
            alt_text = f"{product_title} - {color} {product_type} - фото{photo_num} TwoComms"
        elif image_type == 'thumbnail':
            alt_text = f"{product_title} - {color} {product_type} - мініатюра TwoComms"
        else:
            alt_text = f"{product_title} - {color} {product_type} TwoComms"

        # Ограничиваем длину
        return self.limit_length(alt_text, 125)

    def generate_category_alt_text(self, category, image_type='icon'):
        """Генерирует alt-текст для категории"""
        category_name = category.name

        if image_type == 'icon':
            alt_text = f"{category_name} іконка - TwoComms"
        elif image_type == 'cover':
            alt_text = f"{category_name} категорія - TwoComms магазин"
        else:
            alt_text = f"{category_name} - TwoComms"

        return self.limit_length(alt_text, 125)

    def generate_color_variant_alt_text(self, color_image):
        """Генерирует alt-текст для цветового варианта"""
        product = color_image.variant.product
        color = color_image.variant.color

        product_title = product.title
        product_type = self.detect_product_type(product_title, product.category.name if product.category else '')
        color_name = self.get_color_name(color)

        alt_text = f"{product_title} - {color_name} {product_type} TwoComms"

        return self.limit_length(alt_text, 125)

    def detect_product_type(self, title, category):
        """Определяет тип товара"""
        title_lower = title.lower()
        category_lower = category.lower() if category else ''

        # Ключевые слова для типов товаров
        product_types = {
            'футболка': ['футболка', 't-shirt', 'tshirt'],
            'худі': ['худі', 'hoodie', 'толстовка'],
            'лонгслів': ['лонгслів', 'longsleeve', 'довгий рукав'],
            'світшот': ['світшот', 'sweatshirt', 'світшот']
        }

        # Проверяем в названии товара
        for product_type, keywords in product_types.items():
            for keyword in keywords:
                if keyword in title_lower:
                    return product_type

        # Проверяем в категории
        for product_type, keywords in product_types.items():
            for keyword in keywords:
                if keyword in category_lower:
                    return product_type

        # По умолчанию
        return 'одяг'

    def detect_color_from_title(self, title):
        """Определяет цвет из названия товара"""
        title_lower = title.lower()

        colors = {
            'чорний': ['чорн', 'black', 'dark'],
            'білий': ['біл', 'white', 'light'],
            'сірий': ['сір', 'grey', 'gray'],
            'зелений': ['зелен', 'green'],
            'синій': ['син', 'blue'],
            'червоний': ['червон', 'red'],
            'коричневий': ['коричнев', 'brown'],
            'бежевий': ['беж', 'beige']
        }

        for color, variations in colors.items():
            for variation in variations:
                if variation in title_lower:
                    return color

        return 'різнокольоровий'

    def get_color_name(self, color):
        """Получает название цвета"""
        if not color:
            return 'різнокольоровий'

        # Если у цвета есть название
        if hasattr(color, 'name') and color.name:
            return color.name.lower()

        # Если есть hex код
        if hasattr(color, 'primary_hex') and color.primary_hex:
            return self.hex_to_color_name(color.primary_hex)

        return 'різнокольоровий'

    def hex_to_color_name(self, hex_color):
        """Преобразует hex цвет в название"""
        hex_to_color = {
            '#000000': 'чорний',
            '#FFFFFF': 'білий',
            '#808080': 'сірий',
            '#008000': 'зелений',
            '#0000FF': 'синій',
            '#FF0000': 'червоний',
            '#A52A2A': 'коричневий',
            '#F5F5DC': 'бежевий'
        }

        return hex_to_color.get(hex_color.upper(), 'різнокольоровий')

    def limit_length(self, text, max_length):
        """Ограничивает длину текста"""
        if len(text) <= max_length:
            return text

        # Обрезаем до последнего пробела
        truncated = text[:max_length-3]
        last_space = truncated.rfind(' ')
        if last_space > max_length * 0.8:  # Если пробел не слишком далеко
            return truncated[:last_space] + '...'

        return truncated + '...'

    def print_results(self, results, dry_run):
        """Выводит результаты"""
        self.stdout.write('\n📊 Результаты:')
        self.stdout.write(f'   Товары: {results["products_updated"]} обновлено, {results["products_alt_generated"]} alt-текстов')
        self.stdout.write(f'   Категории: {results["categories_updated"]} обновлено, {results["categories_alt_generated"]} alt-текстов')
        self.stdout.write(f'   Изображения товаров: {results["product_images_updated"]} обновлено, {results["product_images_alt_generated"]} alt-текстов')
        self.stdout.write(f'   Цветовые варианты: {results["color_images_updated"]} обновлено, {results["color_images_alt_generated"]} alt-текстов')

        total_generated = (results["products_alt_generated"] +
                           results["categories_alt_generated"] +
                           results["product_images_alt_generated"] +
                           results["color_images_alt_generated"])

        self.stdout.write(f'\n🎯 Всего создано alt-текстов: {total_generated}')

        if dry_run:
            self.stdout.write('\n💡 Используйте без --dry-run для применения изменений')
