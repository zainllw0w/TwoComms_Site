"""
Django команда для генерации Google Merchant Center фида
Важные изменения:
- Генерация вариантов (цвет × размер) с item_group_id
- Единичные значения для g:size и g:color
- Нормализация g:title (без избыточных ЗАГЛАВНЫХ)
- Исключение недействительных GTIN (не отправляем, если нет валидного)
"""
import xml.etree.ElementTree as ET
from django.core.management.base import BaseCommand
from django.utils import timezone
from storefront.models import Product, Category
from typing import Optional

# Базовые размеры по умолчанию для одежды
DEFAULT_SIZES = ["S", "M", "L", "XL", "XXL"]


def normalize_title_for_feed(title: str) -> str:
    """Снижает долю ЗАГЛАВНЫХ для фида: если заглавных слишком много, делаем Title Case.
    Сайт не затрагиваем — только экспорт.
    """
    if not title:
        return ""
    letters = [c for c in title if c.isalpha()]
    if not letters:
        return title
    upper_count = sum(1 for c in letters if c.isupper())
    ratio = upper_count / len(letters)
    if ratio >= 0.6:
        return title.title()
    return title


def is_valid_gtin(gtin: str) -> bool:
    """Проверяет валидность GTIN по длине и контрольной сумме (модуль 10, алгоритм Луна).
    Поддерживает длины 8, 12, 13, 14. Возвращает True только если gtin полностью состоит из цифр
    и проходит проверку.
    """
    if not gtin or not gtin.isdigit() or len(gtin) not in (8, 12, 13, 14):
        return False
    digits = [int(x) for x in gtin]
    check = digits.pop()
    # Инвертируем для удобства индексации справа
    digits.reverse()
    total = 0
    for i, d in enumerate(digits):
        total += d * (3 if i % 2 == 0 else 1)
    calc = (10 - (total % 10)) % 10
    return calc == check


def hex_to_basic_color_name(primary_hex: str, secondary_hex: Optional[str] = None) -> str:
    """Грубое преобразование hex в человекочитаемое имя цвета.
    Для составного цвета объединяем через '/'. По умолчанию — 'multicolor'.
    """
    def map_one(h: str) -> str:
        h = (h or "").strip().lstrip("#").upper()
        mapping = {
            "000000": "black",
            "FFFFFF": "white",
            "FF0000": "red",
            "00FF00": "green",
            "0000FF": "blue",
            "FFFF00": "yellow",
            "FFA500": "orange",
            "800080": "purple",
            "808080": "gray",
            "A52A2A": "brown",
        }
        return mapping.get(h, None)

    a = map_one(primary_hex)
    b = map_one(secondary_hex or "") if secondary_hex else None

    if a and b and a != b:
        return f"{a}/{b}"
    if a:
        return a
    if b:
        return b
    return "multicolor"


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

            # Сформируем варианты цветов
            variants = []
            try:
                from productcolors.models import ProductColorVariant
                color_variants = ProductColorVariant.objects.filter(product=product).select_related('color')
                for cv in color_variants:
                    color_name = (cv.color.name or "").strip()
                    if not color_name:
                        color_name = hex_to_basic_color_name(getattr(cv.color, 'primary_hex', ''), getattr(cv.color, 'secondary_hex', None))
                    variants.append({
                        'key': f"cv{cv.id}",
                        'color': color_name,
                        'image': (cv.images.first().image if cv.images.exists() else None)
                    })
            except Exception:
                pass

            # Если нет цветовых вариаций — один универсальный вариант
            if not variants:
                variants = [{
                    'key': 'default',
                    'color': 'чорний',
                    'image': product.display_image
                }]

            # Общий item_group_id для группировки (цвет/размер)
            group_id = f"TC-GROUP-{product.id}"

            # Нормализованный заголовок для фида (не меняем на сайте)
            base_title = normalize_title_for_feed(product.title)

            for var in variants:
                for size in DEFAULT_SIZES:
                    # Создаем элемент товара (вариант)
                    item = ET.SubElement(channel, 'item')

                    # Обязательные поля
                    g_id = ET.SubElement(item, 'g:id')
                    g_id.text = f"TC-{product.id}-{var['key']}-{size}"

                    g_item_group_id = ET.SubElement(item, 'g:item_group_id')
                    g_item_group_id.text = group_id

                    g_title = ET.SubElement(item, 'g:title')
                    # Рекомендуется включать цвет и размер в заголовок
                    g_title.text = f"{base_title} — {var['color']} — {size}"

                    g_description = ET.SubElement(item, 'g:description')
                    g_description.text = product.description or f"Якісний {product.category.name.lower() if product.category else 'одяг'} з ексклюзивним дизайном від TwoComms"

                    g_link = ET.SubElement(item, 'g:link')
                    g_link.text = f"https://twocomms.shop/product/{product.slug}/"

                    # Изображение варианта или дефолтное
                    g_image_link = ET.SubElement(item, 'g:image_link')
                    if var.get('image'):
                        g_image_link.text = f"https://twocomms.shop{var['image'].url}"
                    elif product.display_image:
                        g_image_link.text = f"https://twocomms.shop{product.display_image.url}"
                    else:
                        g_image_link.text = "https://twocomms.shop/static/img/placeholder.jpg"

                    g_availability = ET.SubElement(item, 'g:availability')
                    g_availability.text = 'in stock'

                    # Базовая цена и цена со скидкой (если есть)
                    g_price = ET.SubElement(item, 'g:price')
                    g_price.text = f"{product.price} UAH"
                    if product.has_discount:
                        g_sale_price = ET.SubElement(item, 'g:sale_price')
                        g_sale_price.text = f"{product.final_price} UAH"

                    g_condition = ET.SubElement(item, 'g:condition')
                    g_condition.text = 'new'

                    g_brand = ET.SubElement(item, 'g:brand')
                    g_brand.text = 'TwoComms'

                    # Дополнительные поля
                    g_mpn = ET.SubElement(item, 'g:mpn')
                    g_mpn.text = f"TC-{product.id}"

                    # GTIN включаем только если есть валидный; у модели его нет — пропускаем
                    # Пример (на будущее):
                    # if getattr(product, 'gtin', None) and is_valid_gtin(product.gtin):
                    #     g_gtin = ET.SubElement(item, 'g:gtin')
                    #     g_gtin.text = product.gtin

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

                    # Размер — ровно одно значение
                    g_size = ET.SubElement(item, 'g:size')
                    g_size.text = size

                    # Матеріал — залежить від типу товару (визначаємо за slug/категорією)
                    def get_material(p):
                        slug = (p.slug or '').lower()
                        cat = (p.category.name if p.category else '' ).lower()
                        # Hoodie
                        if any(k in slug for k in ['hood', 'hudi', 'hoodie']) or any(k in cat for k in ['худі','худи','hood']):
                            return '90% бавовна, 10% поліестер'
                        # Longsleeve
                        if any(k in slug for k in ['long', 'longsleeve', 'longsliv']) or any(k in cat for k in ['лонгслів','лонгслив','лонг']):
                            return '95% бамбук, 5% еластан'
                        # T-shirt / футболка
                        if any(k in slug for k in ['tshirt','t-shirt','tee','tshort','futbol']) or any(k in cat for k in ['футболк']):
                            return '95% бавовна, 5% еластан'
                        # За замовчуванням — бавовна
                        return '95% бавовна, 5% еластан'

                    g_material = ET.SubElement(item, 'g:material')
                    g_material.text = get_material(product)

                    # Цвет — ровно одно значение на вариант
                    g_color = ET.SubElement(item, 'g:color')
                    g_color.text = var['color']

                    # Дополнительные изображения (общие для товара)
                    try:
                        for i, img in enumerate(product.images.all()[:9]):  # До 9 дополнительных изображений
                            g_additional_image_link = ET.SubElement(item, 'g:additional_image_link')
                            g_additional_image_link.text = f"https://twocomms.shop{img.image.url}"
                    except Exception:
                        pass

                    # Изображения варианта
                    try:
                        from productcolors.models import ProductColorVariant
                        # Найдем снова cv по ключу, только если ключ начинается с 'cv'
                        if var['key'].startswith('cv'):
                            cv_id = int(var['key'][2:])
                            cv = ProductColorVariant.objects.filter(id=cv_id).first()
                            if cv:
                                for img in cv.images.all()[:2]:
                                    g_additional_image_link = ET.SubElement(item, 'g:additional_image_link')
                                    g_additional_image_link.text = f"https://twocomms.shop{img.image.url}"
                    except Exception:
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
