from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.html import strip_tags
from storefront.models import Product, Category
from productcolors.models import ProductColorVariant
import time

# Basic sizes for apparel
DEFAULT_SIZES = ["S", "M", "L", "XL", "XXL"]

def escape_xml(value):
    """Escape special characters for XML."""
    if value is None:
        return ""
    return str(value).replace('&', '&amp;')\
                     .replace('<', '&lt;')\
                     .replace('>', '&gt;')\
                     .replace('"', '&quot;')\
                     .replace("'", '&apos;')

def get_material(product):
    """Determine material based on product category/slug."""
    slug = (product.slug or "").lower()
    cat_name = (product.category.name if product.category else "").lower()
    
    # Logic copied from Google Merchant feed
    if any(k in slug for k in ['hood', 'hudi', 'hoodie']) or any(k in cat_name for k in ['худі', 'худи', 'hood']):
        return '90% бавовна, 10% поліестер'
    if any(k in slug for k in ['long', 'longsleeve', 'longsliv']) or any(k in cat_name for k in ['лонгслів', 'лонгслив', 'лонг']):
        return '95% бамбук, 5% еластан'
    if any(k in slug for k in ['tshirt', 't-shirt', 'tee', 'tshort', 'futbol']) or any(k in cat_name for k in ['футболк']):
        return '95% бавовна, 5% еластан'
    return '95% бавовна, 5% еластан'

def hex_to_label(hex_val):
    """Convert hex to readable label (simple fallback helper)."""
    # In a real scenario we might have a map, but sticking to logic similar to existing usage if needed.
    # The prompt asked to use custom fields. We'll use color.name from relation first.
    return hex_val

class Command(BaseCommand):
    help = 'Generates YML feed for Prom.ua'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='media/prom-feed.xml',
            help='Output file path'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Dry run mode (no file created)'
        )

    def handle(self, *args, **options):
        output_file = options['output']
        dry_run = options['dry_run']
        
        start_time = time.time()
        self.stdout.write("Starting Prom.ua feed generation...")

        # 1. Fetch Categories
        # We need all categories that satisfy the product filter criteria
        # Products filter: status='published', is_dropship_available=True
        relevant_products = Product.objects.filter(status='published', is_dropship_available=True)
        category_ids = relevant_products.values_list('category', flat=True).distinct()
        categories = Category.objects.filter(id__in=category_ids)
        
        # 2. Fetch Products with caching
        products_qs = relevant_products.select_related('category').prefetch_related(
            'color_variants__color', 
            'color_variants__images', 
            'images'
        )

        if dry_run:
            self.stdout.write(f"Found {categories.count()} categories")
            self.stdout.write(f"Found {products_qs.count()} products")
            self.stdout.write("Dry run complete.")
            return

        # 3. Stream to file
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                # Header
                date_str = timezone.now().strftime('%Y-%m-%d %H:%M')
                f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                f.write(f'<yml_catalog date="{date_str}">\n')
                f.write('  <shop>\n')
                f.write('    <name>TwoComms</name>\n')
                f.write('    <company>TwoComms</company>\n')
                f.write('    <url>https://twocomms.shop</url>\n')
                f.write('    <currencies>\n')
                f.write('      <currency id="UAH" rate="1"/>\n')
                f.write('    </currencies>\n')

                # Categories
                f.write('    <categories>\n')
                for cat in categories:
                    # Category uses 'id' and 'name'. If parent exists, add parentId. 
                    # Assuming flat for now based on model inspection.
                    f.write(f'      <category id="{cat.id}">{escape_xml(cat.name)}</category>\n')
                f.write('    </categories>\n')

                # Offers
                f.write('    <offers>\n')
                
                count = 0
                for product in products_qs.iterator(chunk_size=500):
                    count += 1
                    if count % 100 == 0:
                        self.stdout.write(f"Processed {count} products...")

                    # Prepare shared data
                    cat_id = product.category.id if product.category else ""
                    group_id = f"{product.id}" # Matches requirements for grouping variants
                    
                    # Logic: We need to explode products into variants (Color x Size)
                    color_variants = list(product.color_variants.all())
                    
                    final_variants = []
                    
                    if not color_variants:
                        # Fallback for products without variants (unlikely but possible)
                        # Assume stock is 0 or check if dropship available implies stock?
                        # Use 0 as safe default if no variants tracking stock.
                        # BUT prompted "if stock > 0".
                        # If no variants, we can't determine stock from variants.
                        # We will set stock=999 if dropship available? 
                        # Requirements says: "Input Data: Use the existing logic to fetch products, prices, stock status... from the database."
                        # Existing logic (Google feed) sets "in stock" hardcoded.
                        # Prom logic: "available='{true/false}' (Convert logic: if stock > 0 then 'true' else 'false')."
                        # We'll assume if no variants record found, check is_dropship_available. 
                        # If True -> stock=1 (simulated) else 0.
                        stock_val = 100 if product.is_dropship_available else 0
                        
                        fake_variant = {
                            'color_name': '', # No color
                            'images': [],
                            'variant_id': None,
                            'stock': stock_val
                        }
                        if product.main_image:
                             fake_variant['images'].append(product.main_image.url)
                        
                        for size in DEFAULT_SIZES:
                             final_variants.append({
                                 'color_var': fake_variant,
                                 'size': size
                             })
                    else:
                        for cv in color_variants:
                            # Color Name
                            c_name = cv.color.name
                            if not c_name:
                                from storefront.management.commands.generate_google_merchant_feed import hex_to_basic_color_name
                                c_name = hex_to_basic_color_name(
                                    getattr(cv.color, 'primary_hex', ''), 
                                    getattr(cv.color, 'secondary_hex', None)
                                )
                            
                            cv_images = [img.image.url for img in cv.images.all()]
                            
                            var_data = {
                                'color_name': c_name,
                                'images': cv_images,
                                'variant_id': cv.id,
                                'stock': cv.stock # Actual stock
                            }
                            
                            for size in DEFAULT_SIZES:
                                final_variants.append({
                                    'color_var': var_data,
                                    'size': size
                                })

                    # Write XML for each variant
                    for item in final_variants:
                        var = item['color_var']
                        size = item['size']
                        
                        offer_id_suffix = f"-{var['variant_id']}" if var['variant_id'] else "-0"
                        offer_id = f"{product.id}{offer_id_suffix}-{size}"
                        
                        # Availability Logic
                        is_available = "true" if var.get('stock', 0) > 0 else "false"

                        f.write(f'    <offer id="{escape_xml(offer_id)}" available="{is_available}">\n')
                        
                        # URL
                        prod_url = f"https://twocomms.shop/product/{product.slug}/"
                        f.write(f'      <url>{escape_xml(prod_url)}</url>\n')
                        
                        # Price
                        f.write(f'      <price>{product.price}</price>\n')
                        f.write('      <currencyId>UAH</currencyId>\n')
                        f.write(f'      <categoryId>{cat_id}</categoryId>\n')
                        
                        # Pictures
                        # 1. Variant images
                        # 2. Main product image (if not in variant images)
                        # Limit to 10
                        imgs = var['images'][:]
                        if product.main_image and product.main_image.url not in imgs:
                             imgs.append(product.main_image.url)
                        
                        # Add extra product images
                        for p_img in product.images.all():
                            if p_img.image.url not in imgs:
                                imgs.append(p_img.image.url)
                        
                        for img_url in imgs[:10]:
                            full_img_url = f"https://twocomms.shop{img_url}"
                            f.write(f'      <picture>{escape_xml(full_img_url)}</picture>\n')

                        # Name
                        # Prompt: Title: <name> (Do not use g:title)
                        # Maybe useful to include Variant info in title for clarity? 
                        # Prom: "Nike Air Max" is fine if grouped.
                        # But often better to be unique: "Nike Air Max - Red, L"
                        # User Prompt example: <name>Nike Air Max</name> <param name="Size">42</param>
                        # So just product title is likely enough if params provided.
                        f.write(f'      <name>{escape_xml(product.title)}</name>\n')
                        f.write('      <vendor>TwoComms</vendor>\n')
                        f.write(f'      <group_id>{group_id}</group_id>\n')
                        
                        # Description (CDATA)
                        desc = product.full_description or product.description or ""
                        f.write(f'      <description><![CDATA[{desc}]]></description>\n')
                        
                        # Params
                        f.write(f'      <param name="Розмір">{size}</param>\n')
                        f.write(f'      <param name="Колір">{escape_xml(var["color_name"])}</param>\n')
                        f.write(f'      <param name="Матеріал">{escape_xml(get_material(product))}</param>\n')

                        f.write('    </offer>\n')

                f.write('    </offers>\n')
                f.write('  </shop>\n')
                f.write('</yml_catalog>\n')
            
            self.stdout.write(self.style.SUCCESS(f"Successfully generated feed at {output_file}"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error generating feed: {str(e)}"))

