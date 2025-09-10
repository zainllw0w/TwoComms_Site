"""
Django команда для генерации Google Merchant Center фида
"""
import xml.etree.ElementTree as ET
from django.core.management.base import BaseCommand
from django.utils import timezone
from storefront.models import Product, Category


class Command(BaseCommand):
    help = 'Генерирует XML фид для Google Merchant Center'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='google_merchant_feed.xml',
            help='Путь к выходному XML файлу',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет сделано без создания файла',
        )

    def handle(self, *args, **options):
        output_file = options['output']
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(
                self.style.WARNING('РЕЖИМ ПРЕДВАРИТЕЛЬНОГО ПРОСМОТРА - файл не будет создан')
            )

        # Создаем корневой элемент RSS
        rss = ET.Element('rss')
        rss.set('version', '2.0')
        rss.set('xmlns:g', 'http://base.google.com/ns/1.0')

        # Создаем канал
        channel = ET.SubElement(rss, 'channel')
        
        # Заголовок канала
        title = ET.SubElement(channel, 'title')
        title.text = 'TwoComms - Стріт & Мілітарі Одяг'
        
        link = ET.SubElement(channel, 'link')
        link.text = 'https://twocomms.shop'
        
        description = ET.SubElement(channel, 'description')
        description.text = 'Магазин стріт & мілітарі одягу з ексклюзивним дизайном'

        # Получаем все товары
        products = Product.objects.select_related('category').all()
        total_products = products.count()
        processed_products = 0

        self.stdout.write(f'Обрабатываем {total_products} товаров...')

        for product in products:
            processed_products += 1
            self.stdout.write(f'Обрабатываем товар {processed_products}/{total_products}: {product.title}')

            # Создаем элемент товара
            item = ET.SubElement(channel, 'item')

            # Обязательные поля
            g_id = ET.SubElement(item, 'g:id')
            g_id.text = f"TC-{product.id}"

            g_title = ET.SubElement(item, 'g:title')
            g_title.text = product.title

            g_description = ET.SubElement(item, 'g:description')
            g_description.text = product.description or f"Якісний {product.category.name.lower() if product.category else 'одяг'} з ексклюзивним дизайном від TwoComms"

            g_link = ET.SubElement(item, 'g:link')
            g_link.text = f"https://twocomms.shop/product/{product.slug}/"

            g_image_link = ET.SubElement(item, 'g:image_link')
            if product.display_image:
                g_image_link.text = f"https://twocomms.shop{product.display_image.url}"
            else:
                g_image_link.text = "https://twocomms.shop/static/img/placeholder.jpg"

            g_availability = ET.SubElement(item, 'g:availability')
            g_availability.text = 'in stock'

            g_price = ET.SubElement(item, 'g:price')
            g_price.text = f"{product.final_price} UAH"

            g_condition = ET.SubElement(item, 'g:condition')
            g_condition.text = 'new'

            g_brand = ET.SubElement(item, 'g:brand')
            g_brand.text = 'TwoComms'

            # Дополнительные поля
            g_mpn = ET.SubElement(item, 'g:mpn')
            g_mpn.text = f"TC-{product.id}"

            g_gtin = ET.SubElement(item, 'g:gtin')
            g_gtin.text = f"TC{product.id:08d}"

            # Категория
            if product.category:
                g_product_type = ET.SubElement(item, 'g:product_type')
                g_product_type.text = product.category.name

                g_google_product_category = ET.SubElement(item, 'g:google_product_category')
                g_google_product_category.text = '1604'  # Apparel & Accessories > Clothing

            # Возрастная группа и пол
            g_age_group = ET.SubElement(item, 'g:age_group')
            g_age_group.text = 'adult'

            g_gender = ET.SubElement(item, 'g:gender')
            if product.category:
                category_name = product.category.name.lower()
                if any(word in category_name for word in ['чоловіч', 'мужск', 'men']):
                    g_gender.text = 'male'
                elif any(word in category_name for word in ['жіноч', 'женск', 'women']):
                    g_gender.text = 'female'
                else:
                    g_gender.text = 'unisex'
            else:
                g_gender.text = 'unisex'

            # Размеры
            g_size = ET.SubElement(item, 'g:size')
            g_size.text = 'S,M,L,XL,XXL'

            # Материал
            g_material = ET.SubElement(item, 'g:material')
            g_material.text = '100% cotton'

            # Цвета
            try:
                from productcolors.models import ProductColorVariant
                color_variants = ProductColorVariant.objects.filter(product=product)
                colors = []
                for variant in color_variants:
                    if variant.color and variant.color.name:
                        colors.append(variant.color.name)
                
                if colors:
                    g_color = ET.SubElement(item, 'g:color')
                    g_color.text = ','.join(colors[:3])  # Максимум 3 цвета
            except:
                pass

            # Дополнительные изображения
            try:
                for i, img in enumerate(product.images.all()[:9]):  # До 9 дополнительных изображений
                    g_additional_image_link = ET.SubElement(item, 'g:additional_image_link')
                    g_additional_image_link.text = f"https://twocomms.shop{img.image.url}"
            except:
                pass

            # Изображения цветовых вариантов
            try:
                from productcolors.models import ProductColorVariant
                color_variants = ProductColorVariant.objects.filter(product=product)
                for variant in color_variants:
                    for img in variant.images.all()[:2]:
                        g_additional_image_link = ET.SubElement(item, 'g:additional_image_link')
                        g_additional_image_link.text = f"https://twocomms.shop{img.image.url}"
            except:
                pass

        if not dry_run:
            # Сохраняем XML файл
            tree = ET.ElementTree(rss)
            ET.indent(tree, space="  ", level=0)  # Форматируем XML
            
            with open(output_file, 'wb') as f:
                tree.write(f, encoding='utf-8', xml_declaration=True)

            self.stdout.write(
                self.style.SUCCESS(f'Google Merchant Center фид создан: {output_file}')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Будет создан фид с {total_products} товарами')
            )

        self.stdout.write(
            self.style.SUCCESS(f'Обработка завершена! Обработано товаров: {processed_products}')
        )

        if not dry_run:
            self.stdout.write(
                self.style.WARNING(
                    'Для загрузки в Google Merchant Center:\n'
                    '1. Зайдите в Google Merchant Center\n'
                    '2. Перейдите в раздел "Продукты" > "Фиды"\n'
                    '3. Создайте новый фид и загрузите файл\n'
                    '4. Укажите URL фида: https://twocomms.shop/google_merchant_feed.xml'
                )
            )
