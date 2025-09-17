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
        
        # Добавляем атрибут user для совместимости с middleware
        from django.contrib.auth.models import AnonymousUser
        request.user = AnonymousUser()
        
        # Настраиваем sitemaps
        sitemaps = {
            'static': StaticViewSitemap,
            'products': ProductSitemap,
            'categories': CategorySitemap,
        }
        
        # Генерируем sitemap
        response = sitemap(request, sitemaps)
        
        # Рендерим ответ
        response.render()
        
        # Получаем содержимое
        content = response.content.decode('utf-8')
        
        # Путь для сохранения файла в static
        sitemap_static_path = os.path.join(settings.BASE_DIR, 'twocomms', 'static', 'sitemap.xml')
        # Путь для сохранения файла в корень проекта
        sitemap_root_path = os.path.join(settings.BASE_DIR, 'twocomms', 'sitemap.xml')
        
        # Создаем директорию если не существует
        os.makedirs(os.path.dirname(sitemap_static_path), exist_ok=True)
        
        # Сохраняем файл в static
        with open(sitemap_static_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Копируем файл в корень проекта
        with open(sitemap_root_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully generated sitemap.xml at {sitemap_static_path} and {sitemap_root_path}')
        )
