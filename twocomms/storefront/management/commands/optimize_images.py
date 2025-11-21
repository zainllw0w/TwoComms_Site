from django.core.management.base import BaseCommand
from django.conf import settings
from image_optimizer import ImageOptimizer
from storefront.models import Product, ProductImage, Category, CatalogOptionValue, SizeGrid
from productcolors.models import ProductColorImage
import os

class Command(BaseCommand):
    help = 'Optimizes images for all products and categories using ImageOptimizer'

    def handle(self, *args, **options):
        optimizer = ImageOptimizer()
        
        self.stdout.write('Starting image optimization...')
        
        # 1. Products Main Images
        products = Product.objects.exclude(main_image='').defer('catalog')
        total_products = products.count()
        self.stdout.write(f'Found {total_products} products with main images')
        
        for i, product in enumerate(products, 1):
            if product.main_image:
                path = product.main_image.path
                if os.path.exists(path):
                    self.stdout.write(f'[{i}/{total_products}] Optimizing Product {product.id}: {product.title}')
                    optimizer.optimize_product_image(path)
        
        # 2. Product Extra Images
        product_images = ProductImage.objects.all()
        total_p_images = product_images.count()
        self.stdout.write(f'\nFound {total_p_images} extra product images')
        
        for i, img in enumerate(product_images, 1):
            if img.image:
                path = img.image.path
                if os.path.exists(path):
                    self.stdout.write(f'[{i}/{total_p_images}] Optimizing ProductImage {img.id}')
                    optimizer.optimize_product_image(path)

        # 3. Product Color Images
        color_images = ProductColorImage.objects.all()
        total_c_images = color_images.count()
        self.stdout.write(f'\nFound {total_c_images} product color images')
        
        for i, img in enumerate(color_images, 1):
            if img.image:
                path = img.image.path
                if os.path.exists(path):
                    self.stdout.write(f'[{i}/{total_c_images}] Optimizing ProductColorImage {img.id}')
                    optimizer.optimize_product_image(path)

        # 4. Categories
        categories = Category.objects.all()
        self.stdout.write(f'\nFound {categories.count()} categories')
        
        for cat in categories:
            # Icon
            if cat.icon:
                path = cat.icon.path
                if os.path.exists(path):
                    self.stdout.write(f'Optimizing Category Icon: {cat.name}')
                    optimizer.optimize_category_icon(path)
            
            # Cover
            if cat.cover:
                path = cat.cover.path
                if os.path.exists(path):
                    self.stdout.write(f'Optimizing Category Cover: {cat.name}')
                    optimizer.optimize_product_image(path) # Treat cover as product image for responsive sizes

        # 5. Catalog Options
        options = CatalogOptionValue.objects.exclude(image='')
        self.stdout.write(f'\nFound {options.count()} catalog options with images')
        
        for opt in options:
            if opt.image:
                path = opt.image.path
                if os.path.exists(path):
                    self.stdout.write(f'Optimizing Option Image: {opt.display_name}')
                    optimizer.optimize_product_image(path)

        # 6. Size Grids
        grids = SizeGrid.objects.exclude(image='')
        self.stdout.write(f'\nFound {grids.count()} size grids with images')
        
        for grid in grids:
            if grid.image:
                path = grid.image.path
                if os.path.exists(path):
                    self.stdout.write(f'Optimizing SizeGrid: {grid.name}')
                    optimizer.optimize_product_image(path)

        self.stdout.write(self.style.SUCCESS('Image optimization completed successfully!'))
