import os
import time
from pathlib import Path

from django.core.management.base import BaseCommand
from django.conf import settings

from image_optimizer import ImageOptimizer
from storefront.models import Product, ProductImage, Category, CatalogOptionValue, SizeGrid
from productcolors.models import ProductColorImage

class Command(BaseCommand):
    help = 'Optimizes images for all products and categories using ImageOptimizer'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Maximum number of images to process in one run (for staged execution).'
        )
        parser.add_argument(
            '--steps',
            type=str,
            default='product_main,product_extra,color,category,option,size,proposal',
            help='Comma-separated steps to run: product_main,product_extra,color,category,option,size,proposal'
        )
        parser.add_argument(
            '--sleep',
            type=float,
            default=0.0,
            help='Sleep seconds between items to reduce CPU spikes on constrained hosts.'
        )

    def handle(self, *args, **options):
        optimizer = ImageOptimizer()
        limit = options.get('limit')
        steps = {step.strip() for step in (options.get('steps') or '').split(',') if step.strip()}
        if not steps:
            steps = {
                'product_main', 'product_extra', 'color',
                'category', 'option', 'size', 'proposal'
            }
        sleep = float(options.get('sleep') or 0)
        
        self.stdout.write('Starting image optimization...')
        self.stdout.flush()
        
        def _already_optimized(image_path: Path) -> bool:
            """
            Быстрый пропуск, если оптимизированные версии уже есть.
            """
            optimized_dir = image_path.parent / "optimized"
            webp = optimized_dir / f"{image_path.stem}.webp"
            avif = optimized_dir / f"{image_path.stem}.avif"
            return webp.exists() and avif.exists()

        saved_total = 0
        processed = 0
        def _pause():
            if sleep > 0:
                time.sleep(sleep)

        def _should_stop() -> bool:
            return limit is not None and processed >= limit

        # 1. Products Main Images
        if 'product_main' in steps:
            products = Product.objects.exclude(main_image='').defer('catalog')
            total_products = products.count()
            self.stdout.write(f'Found {total_products} products with main images')
            self.stdout.flush()
            
            for i, product in enumerate(products, 1):
                if product.main_image:
                    path = Path(product.main_image.path)
                    if path.exists():
                        if _already_optimized(path):
                            continue
                        self.stdout.write(f'[{i}/{total_products}] Optimizing Product {product.id}: {product.title}')
                        self.stdout.flush()
                        variants = optimizer.optimize_product_image(str(path))
                        if variants:
                            optimizer.save_optimized_images(variants, path.parent / "optimized")
                            saved_total += len(variants)
                            processed += 1
                            _pause()
                            if _should_stop():
                                self.stdout.write(self.style.WARNING(f'Reached limit {limit}, stopping early.'))
                                self.stdout.write(self.style.SUCCESS(f'Saved {saved_total} optimized files.'))
                                return

        # 2. Product Extra Images
        if 'product_extra' in steps:
            product_images = ProductImage.objects.all()
            total_p_images = product_images.count()
            self.stdout.write(f'\nFound {total_p_images} extra product images')
            self.stdout.flush()
            
            for i, img in enumerate(product_images, 1):
                if img.image:
                    path = Path(img.image.path)
                    if path.exists():
                        if _already_optimized(path):
                            continue
                        self.stdout.write(f'[{i}/{total_p_images}] Optimizing ProductImage {img.id}')
                        self.stdout.flush()
                        variants = optimizer.optimize_product_image(str(path))
                        if variants:
                            optimizer.save_optimized_images(variants, path.parent / "optimized")
                            saved_total += len(variants)
                            processed += 1
                            _pause()
                            if _should_stop():
                                self.stdout.write(self.style.WARNING(f'Reached limit {limit}, stopping early.'))
                                self.stdout.write(self.style.SUCCESS(f'Saved {saved_total} optimized files.'))
                                return

        # 3. Product Color Images
        if 'color' in steps:
            color_images = ProductColorImage.objects.all()
            total_c_images = color_images.count()
            self.stdout.write(f'\nFound {total_c_images} product color images')
            self.stdout.flush()
            
            for i, img in enumerate(color_images, 1):
                if img.image:
                    path = Path(img.image.path)
                    if path.exists():
                        if _already_optimized(path):
                            continue
                        self.stdout.write(f'[{i}/{total_c_images}] Optimizing ProductColorImage {img.id}')
                        self.stdout.flush()
                        variants = optimizer.optimize_product_image(str(path))
                        if variants:
                            optimizer.save_optimized_images(variants, path.parent / "optimized")
                            saved_total += len(variants)
                            processed += 1
                            _pause()
                            if _should_stop():
                                self.stdout.write(self.style.WARNING(f'Reached limit {limit}, stopping early.'))
                                self.stdout.write(self.style.SUCCESS(f'Saved {saved_total} optimized files.'))
                                return

        # 4. Categories
        if 'category' in steps:
            categories = Category.objects.all()
            self.stdout.write(f'\nFound {categories.count()} categories')
            self.stdout.flush()
            
            for cat in categories:
                # Icon
                if cat.icon:
                    path = Path(cat.icon.path)
                    if path.exists():
                        if not _already_optimized(path):
                            self.stdout.write(f'Optimizing Category Icon: {cat.name}')
                            self.stdout.flush()
                            variants = optimizer.optimize_category_icon(str(path))
                            if variants:
                                optimizer.save_optimized_images(variants, path.parent / "optimized")
                                saved_total += len(variants)
                                processed += 1
                                _pause()
                                if _should_stop():
                                    self.stdout.write(self.style.WARNING(f'Reached limit {limit}, stopping early.'))
                                    self.stdout.write(self.style.SUCCESS(f'Saved {saved_total} optimized files.'))
                                    return
                
                # Cover
                if cat.cover:
                    path = Path(cat.cover.path)
                    if path.exists():
                        if not _already_optimized(path):
                            self.stdout.write(f'Optimizing Category Cover: {cat.name}')
                            self.stdout.flush()
                            variants = optimizer.optimize_product_image(str(path)) # Treat cover as product image for responsive sizes
                            if variants:
                                optimizer.save_optimized_images(variants, path.parent / "optimized")
                                saved_total += len(variants)
                                processed += 1
                                _pause()
                                if _should_stop():
                                    self.stdout.write(self.style.WARNING(f'Reached limit {limit}, stopping early.'))
                                    self.stdout.write(self.style.SUCCESS(f'Saved {saved_total} optimized files.'))
                                    return

        # 5. Catalog Options
        if 'option' in steps:
            options = CatalogOptionValue.objects.exclude(image='')
            self.stdout.write(f'\nFound {options.count()} catalog options with images')
            self.stdout.flush()
            
            for opt in options:
                if opt.image:
                    path = Path(opt.image.path)
                    if path.exists():
                        if _already_optimized(path):
                            continue
                        self.stdout.write(f'Optimizing Option Image: {opt.display_name}')
                        self.stdout.flush()
                        variants = optimizer.optimize_product_image(str(path))
                        if variants:
                            optimizer.save_optimized_images(variants, path.parent / "optimized")
                            saved_total += len(variants)
                            processed += 1
                            _pause()
                            if _should_stop():
                                self.stdout.write(self.style.WARNING(f'Reached limit {limit}, stopping early.'))
                                self.stdout.write(self.style.SUCCESS(f'Saved {saved_total} optimized files.'))
                                return

        # 6. Size Grids
        if 'size' in steps:
            grids = SizeGrid.objects.exclude(image='')
            self.stdout.write(f'\nFound {grids.count()} size grids with images')
            self.stdout.flush()
            
            for grid in grids:
                if grid.image:
                    path = Path(grid.image.path)
                    if path.exists():
                        if _already_optimized(path):
                            continue
                        self.stdout.write(f'Optimizing SizeGrid: {grid.name}')
                        self.stdout.flush()
                        variants = optimizer.optimize_product_image(str(path))
                        if variants:
                            optimizer.save_optimized_images(variants, path.parent / "optimized")
                            saved_total += len(variants)
                            processed += 1
                            _pause()
                            if _should_stop():
                                self.stdout.write(self.style.WARNING(f'Reached limit {limit}, stopping early.'))
                                self.stdout.write(self.style.SUCCESS(f'Saved {saved_total} optimized files.'))
                                return

        # 7. Print Proposals (если есть)
        if 'proposal' in steps:
            from storefront.models import PrintProposal
            proposals = PrintProposal.objects.exclude(image='')
            self.stdout.write(f'\nFound {proposals.count()} print proposals with images')
            self.stdout.flush()
            for proposal in proposals:
                if proposal.image:
                    path = Path(proposal.image.path)
                    if path.exists():
                        if _already_optimized(path):
                            continue
                        self.stdout.write(f'Optimizing PrintProposal: {proposal.id}')
                        self.stdout.flush()
                        variants = optimizer.optimize_product_image(str(path))
                        if variants:
                            optimizer.save_optimized_images(variants, path.parent / "optimized")
                            saved_total += len(variants)
                            processed += 1
                            _pause()
                            if _should_stop():
                                self.stdout.write(self.style.WARNING(f'Reached limit {limit}, stopping early.'))
                                self.stdout.write(self.style.SUCCESS(f'Saved {saved_total} optimized files.'))
                                return

        self.stdout.write(self.style.SUCCESS(f'Image optimization completed. Saved {saved_total} optimized files.'))
