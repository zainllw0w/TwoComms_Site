"""
Management команда для генерации статического sitemap.xml
"""
from django.core.management.base import BaseCommand
from django.contrib.sitemaps.views import sitemap
from django.test import RequestFactory
from django.conf import settings
from storefront.sitemaps import StaticViewSitemap, ProductSitemap, CategorySitemap
import os


class Command(BaseCommand):
    help = 'Генерирует статический sitemap.xml файл'

    def handle(self, *args, **options):
        # Создаем фиктивный запрос
        factory = RequestFactory()
        request = factory.get('/sitemap.xml')
        
        # Настраиваем sitemaps
        sitemaps = {
            'static': StaticViewSitemap,
            'products': ProductSitemap,
            'categories': CategorySitemap,
        }
        
        # Генерируем sitemap
        response = sitemap(request, sitemaps)
        
        # Получаем содержимое
        content = response.content.decode('utf-8')
        
        # Путь для сохранения файла
        sitemap_path = os.path.join(settings.BASE_DIR, 'twocomms', 'static', 'sitemap.xml')
        
        # Создаем директорию если не существует
        os.makedirs(os.path.dirname(sitemap_path), exist_ok=True)
        
        # Сохраняем файл
        with open(sitemap_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully generated sitemap.xml at {sitemap_path}')
        )
