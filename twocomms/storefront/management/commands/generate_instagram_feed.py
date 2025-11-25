"""
Django команда для генерации Instagram/Meta Commerce Platform фида
Основана на логике Google Merchant Feed v3, но с учетом требований Meta:
- g:id = get_offer_id() (точное совпадение с content_ids пикселя)
- quantity_to_sell_on_facebook
- rich_text_description (если доступно)
- color и additional_image_link без префикса g:
- последнее добавленное изображение (max id) = основное
"""
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET

from django.core.management.base import BaseCommand

from storefront.models import Product
from storefront.utils.analytics_helpers import get_offer_id

# Базовые размеры для одежды
DEFAULT_SIZES = ["S", "M", "L", "XL", "XXL"]


def normalize_title_for_feed(title: str) -> str:
    """Снижает долю ЗАГЛАВНЫХ: если их слишком много, переводит в Title Case."""
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


def hex_to_basic_color_name(primary_hex: str, secondary_hex: Optional[str] = None) -> str:
    """
    Грубое преобразование hex в базовое имя цвета.
    Для составного цвета объединяем через '/'.
    """
    def map_one(h: str) -> Optional[str]:
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


def format_price_for_meta(price: int) -> str:
    """Форматирует цену для Meta фида: '950.00 UAH'."""
    try:
        value = float(price)
    except (TypeError, ValueError):
        return "0.00 UAH"
    return f"{value:.2f} UAH"


def count_total_images(product) -> int:
    """Подсчитывает общее количество изображений товара (общие + все варианты)."""
    count = len(product.images.all())
    for cv in product.color_variants.all():
        count += len(cv.images.all())
    return count


def get_all_product_images(product) -> List[Dict]:
    """
    Собирает ВСЕ изображения товара и сортирует по id (по убыванию).
    all_images[0] = изображение с максимальным id = последнее добавленное.
    """
    all_images: List[Dict] = []

    for img in product.images.all().order_by("-id"):
        all_images.append({
            "image": img.image,
            "id": img.id,
            "type": "product",
        })

    for cv in product.color_variants.all():
        for img in cv.images.all().order_by("-id"):
            all_images.append({
                "image": img.image,
                "id": img.id,
                "type": "variant",
                "variant_id": cv.id,
            })

    all_images.sort(key=lambda x: x["id"], reverse=True)
    return all_images


def is_hoodie(product) -> bool:
    """Проверяет, относится ли товар к худи (по категории, slug или названию)."""
    if product.category:
        cat_slug = (product.category.slug or "").lower()
        cat_name = (product.category.name or "").lower()
        if any(tok in cat_slug for tok in ["hood", "hoodi", "hoody", "hoodie", "hoodies", "sweatshirt", "sweat"]):
            return True
        if any(tok in cat_name for tok in ["худи", "худі", "hoodie", "hood", "hoody", "sweatshirt"]):
            return True

    title_lower = (product.title or "").lower()
    slug_lower = (product.slug or "").lower()
    category_name = (product.category.name if product.category else "").lower()

    keywords = ["худи", "худі", "hoodie", "hoodies", "hoody", "hood", "hudi", "sweatshirt", "sweat"]
    return any(kw in title_lower or kw in slug_lower or kw in category_name for kw in keywords)


def get_description_for_feed(product) -> tuple:
    """
    Возвращает (description, rich_text_description) с приоритетом rich_text.
    """
    if product.full_description:
        if "<" in product.full_description and ">" in product.full_description:
            return (product.description or product.short_description or "", product.full_description)
        return (product.full_description, None)

    description = product.description or product.short_description or ""
    return (description, None)


def get_quantity_to_sell(product, variant_id: Optional[int] = None, size: str = "S") -> int:
    """
    Возвращает quantity_to_sell_on_facebook.
    Если у варианта есть stock и он > 0 — используем его, иначе дефолт 100 (in stock).
    """
    if variant_id:
        try:
            variant = next((cv for cv in product.color_variants.all() if cv.id == variant_id), None)
            if variant and getattr(variant, "stock", 0) > 0:
                return variant.stock
        except Exception:
            pass
    return 100


def is_special_oshp_225(product) -> bool:
    """
    Фильтр-исключение для конкретного худи "225 ОШП" (по id/названию/slug).
    """
    try:
        if product.id == 225:
            return True
    except Exception:
        pass

    text = " ".join([
        str(product.title or ""),
        str(product.slug or ""),
        str(getattr(product, "sku", "") or ""),
        str(getattr(product, "barcode", "") or ""),
    ]).lower()

    return "225" in text and "ошп" in text


class Command(BaseCommand):
    help = "Генерирует XML фид для Instagram/Meta Commerce Platform"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            default="media/instagram-feed.xml",
            help="Путь к выходному XML файлу",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать что будет сделано без создания файла",
        )
        parser.add_argument(
            "--log-skipped",
            action="store_true",
            help="Логировать причины пропуска товаров (для диагностики)",
        )

    def handle(self, *args, **options):
        output_file = options["output"]
        dry_run = options["dry_run"]
        log_skipped = options["log_skipped"]

        if dry_run:
            self.stdout.write(self.style.WARNING("РЕЖИМ ПРЕДВАРИТЕЛЬНОГО ПРОСМОТРА - файл не будет создан"))

        rss = ET.Element("rss")
        rss.set("version", "2.0")
        rss.set("xmlns:g", "http://base.google.com/ns/1.0")
        rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")

        channel = ET.SubElement(rss, "channel")

        title = ET.SubElement(channel, "title")
        title.text = "TwoComms - Instagram Shop"

        link = ET.SubElement(channel, "link")
        link.text = "https://twocomms.shop"

        description = ET.SubElement(channel, "description")
        description.text = "Product Feed for Instagram Shopping"

        atom_link = ET.SubElement(channel, "{http://www.w3.org/2005/Atom}link")
        atom_link.set("href", "https://twocomms.shop/media/instagram-feed.xml")
        atom_link.set("rel", "self")
        atom_link.set("type", "application/rss+xml")

        products = Product.objects.filter(
            status="published",
            is_dropship_available=True,
        ).select_related("category").prefetch_related(
            "color_variants__color",
            "color_variants__images",
            "images",
        )

        total_products = products.count()
        processed_products = 0
        skipped_products = 0
        skip_reasons = {"not_hoodie": 0, "special_oshp": 0, "few_images": 0}

        self.stdout.write(f"Обрабатываем {total_products} товаров...")

        for product in products.iterator(chunk_size=1000):
            if not is_hoodie(product):
                skipped_products += 1
                skip_reasons["not_hoodie"] += 1
                if log_skipped:
                    self.stdout.write(f"SKIP not hoodie: id={product.id} title='{product.title}' slug='{product.slug}'")
                continue

            if is_special_oshp_225(product):
                skipped_products += 1
                skip_reasons["special_oshp"] += 1
                if log_skipped:
                    self.stdout.write(f"SKIP 225 OSHP: id={product.id} title='{product.title}' slug='{product.slug}'")
                continue

            total_images_count = count_total_images(product)
            if total_images_count < 2:
                skipped_products += 1
                skip_reasons["few_images"] += 1
                if log_skipped:
                    self.stdout.write(f"SKIP few images (<2): id={product.id} title='{product.title}' slug='{product.slug}' (images={total_images_count})")
                continue

            all_images = get_all_product_images(product)
            if not all_images:
                skipped_products += 1
                continue

            main_image = all_images[0]["image"]
            additional_images = all_images[1:]

            variants = []
            try:
                for cv in product.color_variants.all():
                    color_name = (getattr(cv.color, "name", "") or "").strip()
                    if not color_name:
                        color_name = hex_to_basic_color_name(
                            getattr(cv.color, "primary_hex", ""),
                            getattr(cv.color, "secondary_hex", None),
                        )
                    variants.append({
                        "key": f"cv{cv.id}",
                        "color": color_name,
                        "variant_id": cv.id,
                        "stock": getattr(cv, "stock", 0),
                    })
            except Exception:
                pass

            if not variants:
                variants = [{
                    "key": "default",
                    "color": "чорний",
                    "variant_id": None,
                    "stock": None,
                }]

            group_id = f"TC-GROUP-{product.id}"
            base_title = normalize_title_for_feed(product.title)

            for var in variants:
                for size in DEFAULT_SIZES:
                    item = ET.SubElement(channel, "item")

                    g_id = ET.SubElement(item, "g:id")
                    try:
                        offer_id = get_offer_id(
                            product_id=product.id,
                            color_variant_id=var.get("variant_id"),
                            size=size,
                            color_name=var.get("color"),
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Ошибка генерации offer_id для товара {product.id}: {e}. Используется fallback."
                            )
                        )
                        offer_id = f"TC-{product.id:04d}-{var['key']}-{size}"
                    g_id.text = offer_id

                    g_item_group_id = ET.SubElement(item, "g:item_group_id")
                    g_item_group_id.text = group_id

                    g_title = ET.SubElement(item, "g:title")
                    g_title.text = f"{base_title} — {var['color']} — {size}"

                    description_text, rich_text = get_description_for_feed(product)
                    if not description_text:
                        description_text = f"Якісний {product.category.name.lower() if product.category else 'одяг'} з ексклюзивним дизайном від TwoComms"

                    g_description = ET.SubElement(item, "g:description")
                    g_description.text = description_text

                    if rich_text:
                        g_rich_text_description = ET.SubElement(item, "g:rich_text_description")
                        g_rich_text_description.text = rich_text

                    g_link = ET.SubElement(item, "g:link")
                    g_link.text = f"https://twocomms.shop/product/{product.slug}/"

                    g_image_link = ET.SubElement(item, "g:image_link")
                    g_image_link.text = f"https://twocomms.shop{main_image.url}"

                    for img_data in additional_images:
                        additional_image_link = ET.SubElement(item, "additional_image_link")
                        additional_image_link.text = f"https://twocomms.shop{img_data['image'].url}"

                    g_availability = ET.SubElement(item, "g:availability")
                    g_availability.text = "in stock"

                    quantity = get_quantity_to_sell(product, var.get("variant_id"), size)
                    g_quantity = ET.SubElement(item, "quantity_to_sell_on_facebook")
                    g_quantity.text = str(quantity)

                    g_condition = ET.SubElement(item, "g:condition")
                    g_condition.text = "new"

                    g_price = ET.SubElement(item, "g:price")
                    g_price.text = format_price_for_meta(product.price)

                    if product.has_discount:
                        g_sale_price = ET.SubElement(item, "g:sale_price")
                        g_sale_price.text = format_price_for_meta(product.final_price)

                    g_brand = ET.SubElement(item, "g:brand")
                    g_brand.text = "TwoComms"

                    g_mpn = ET.SubElement(item, "g:mpn")
                    g_mpn.text = f"TC-{product.id}"

                    g_size = ET.SubElement(item, "g:size")
                    g_size.text = size

                    color = ET.SubElement(item, "color")
                    color.text = var["color"]

                    if product.category:
                        g_product_type = ET.SubElement(item, "g:product_type")
                        g_product_type.text = product.category.name

                        g_google_product_category = ET.SubElement(item, "g:google_product_category")
                        g_google_product_category.text = "1604"

                    g_age_group = ET.SubElement(item, "g:age_group")
                    g_age_group.text = "adult"

                    g_gender = ET.SubElement(item, "g:gender")
                    if product.category:
                        category_name = product.category.name.lower()
                        if any(word in category_name for word in ["чоловіч", "мужск", "men"]):
                            g_gender.text = "male"
                        elif any(word in category_name for word in ["жіноч", "женск", "women"]):
                            g_gender.text = "female"
                        else:
                            g_gender.text = "unisex"
                    else:
                        g_gender.text = "unisex"

                    def get_material(p):
                        slug = (p.slug or "").lower()
                        cat = (p.category.name if p.category else "").lower()
                        if any(k in slug for k in ["hood", "hudi", "hoodie"]) or any(k in cat for k in ["худі", "худи", "hood"]):
                            return "90% бавовна, 10% поліестер"
                        if any(k in slug for k in ["long", "longsleeve", "longsliv"]) or any(k in cat for k in ["лонгслів", "лонгслив", "лонг"]):
                            return "95% бамбук, 5% еластан"
                        if any(k in slug for k in ["tshirt", "t-shirt", "tee", "tshort", "futbol"]) or any(k in cat for k in ["футболк"]):
                            return "95% бавовна, 5% еластан"
                        return "95% бавовна, 5% еластан"

                    g_material = ET.SubElement(item, "g:material")
                    g_material.text = get_material(product)

                    if is_hoodie(product):
                        internal_label = ET.SubElement(item, "internal_label")
                        internal_label.text = "['hoodie']"

            processed_products += 1

        if not dry_run:
            tree = ET.ElementTree(rss)
            ET.indent(tree, space="  ", level=0)
            with open(output_file, "wb") as f:
                tree.write(f, encoding="utf-8", xml_declaration=True)
            self.stdout.write(self.style.SUCCESS(f"Instagram/Meta фид создан: {output_file}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Будет сгенерирован фид с {processed_products} товарами"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Обработка завершена! Обработано: {processed_products}, Пропущено (мало фото): {skipped_products}"
            )
        )
        self.stdout.write(
            f"Статистика пропусков: not_hoodie={skip_reasons['not_hoodie']}, special_oshp={skip_reasons['special_oshp']}, few_images={skip_reasons['few_images']}"
        )
