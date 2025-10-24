"""
Debug views - Діагностичні view функції для налагодження.

Містить views для:
- Діагностики медіа-файлів
- Тестування завантаження файлів
- Перевірки зображень товарів

⚠️ УВАГА: Ці функції призначені тільки для розробки!
"""

import os
from django.conf import settings
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from ..models import Product


def debug_media(request):
    """
    Діагностика медіа-файлів.
    
    GET: Повертає діагностичну інформацію про медіа-папки
    POST: Тестує завантаження файлу
    
    Перевіряє:
    - Існування MEDIA_ROOT
    - Підпапки (products, avatars, etc.)
    - Права доступу
    - Останні завантажені файли
    """
    # Обработка POST запроса для тестирования загрузки
    if request.method == 'POST':
        uploaded_file = request.FILES.get('test_file')
        if not uploaded_file:
            return JsonResponse(
                {'success': False, 'error': 'Файл не найден в запросе'},
                status=400,
            )

        test_dir = os.path.join(settings.MEDIA_ROOT, 'test')
        try:
            os.makedirs(test_dir, exist_ok=True)
            file_path = os.path.join(test_dir, uploaded_file.name)
            with open(file_path, 'wb+') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
        except OSError as exc:
            return JsonResponse(
                {'success': False, 'error': str(exc)}, status=500
            )

        return JsonResponse({
            'success': True,
            'file_path': file_path,
            'file_url': f"{settings.MEDIA_URL}test/{uploaded_file.name}",
            'file_size': uploaded_file.size,
            'message': 'Файл успешно загружен'
        })
    
    # GET запрос - возвращаем диагностическую информацию
    debug_info = {
        'MEDIA_URL': settings.MEDIA_URL,
        'MEDIA_ROOT': str(settings.MEDIA_ROOT),
        'DEBUG': settings.DEBUG,
        'BASE_DIR': str(settings.BASE_DIR),
    }
    
    # Проверяем существование папок
    media_root = settings.MEDIA_ROOT
    debug_info['media_root_exists'] = os.path.exists(media_root)
    
    if os.path.exists(media_root):
        debug_info['media_root_contents'] = os.listdir(media_root)
        debug_info['media_root_permissions'] = oct(os.stat(media_root).st_mode)[-3:]
    
    # Проверяем подпапки
    subfolders = ['products', 'avatars', 'category_covers', 'category_icons', 'product_colors', 'test']
    debug_info['subfolders'] = {}
    
    for folder in subfolders:
        folder_path = os.path.join(media_root, folder)
        debug_info['subfolders'][folder] = {
            'exists': os.path.exists(folder_path),
            'contents': os.listdir(folder_path) if os.path.exists(folder_path) else [],
            'permissions': oct(os.stat(folder_path).st_mode)[-3:] if os.path.exists(folder_path) else None
        }
    
    # Проверяем последние загруженные файлы
    debug_info['recent_files'] = []
    for folder in subfolders:
        folder_path = os.path.join(media_root, folder)
        if os.path.exists(folder_path):
            files = os.listdir(folder_path)
            for file in files[:5]:  # Показываем первые 5 файлов
                file_path = os.path.join(folder_path, file)
                debug_info['recent_files'].append({
                    'folder': folder,
                    'file': file,
                    'size': os.path.getsize(file_path),
                    'permissions': oct(os.stat(file_path).st_mode)[-3:],
                    'url': f"{settings.MEDIA_URL}{folder}/{file}"
                })
    
    return JsonResponse(debug_info)


def debug_media_page(request):
    """
    Сторінка діагностики медіа-файлів з UI.
    
    Відображає форму для тестування завантаження файлів
    та діагностичну інформацію.
    """
    return render(request, 'pages/debug_media.html')


def debug_product_images(request):
    """
    Діагностика зображень товарів.
    
    Перевіряє:
    - Наявність головного зображення
    - Кількість кольорових варіантів
    - Зображення для кожного варіанту
    
    Returns:
        JSON з інформацією про перші 10 товарів
    """
    products = Product.objects.select_related('category').prefetch_related('images', 'color_variants__images')[:10]  # Берем первые 10 товаров
    
    debug_info = []
    for product in products:
        product_info = {
            'id': product.id,
            'title': product.title,
            'main_image': str(product.main_image) if product.main_image else None,
            'display_image': str(product.display_image) if product.display_image else None,
            'has_color_variants': product.color_variants.exists(),
            'color_variants_count': product.color_variants.count(),
        }
        
        # Проверяем цветовые варианты
        if product.color_variants.exists():
            first_variant = product.color_variants.first()
            product_info['first_variant'] = {
                'id': first_variant.id,
                'color_name': first_variant.color.name,
                'images_count': first_variant.images.count(),
                'first_image': str(first_variant.images.first().image) if first_variant.images.exists() else None,
            }
        
        debug_info.append(product_info)
    
    return JsonResponse({'products': debug_info})

