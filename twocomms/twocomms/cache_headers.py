"""
Эффективные настройки кеширования для TwoComms
"""

import os
from pathlib import Path


def add_cache_headers(headers, path, url):
    """
    Добавляет эффективные заголовки кеширования для разных типов ресурсов
    """
    # Определяем тип файла по расширению
    file_extension = Path(path).suffix.lower()
    
    # Критические ресурсы - кешируем на 1 год
    if file_extension in ['.css', '.js'] and 'min' in path:
        headers['Cache-Control'] = 'public, max-age=31536000, immutable'  # 1 год
        headers['ETag'] = f'"{os.path.getmtime(path)}"'
    
    # Изображения - кешируем на 1 год
    elif file_extension in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.ico']:
        headers['Cache-Control'] = 'public, max-age=31536000, immutable'  # 1 год
        headers['ETag'] = f'"{os.path.getmtime(path)}"'
    
    # Шрифты - кешируем на 1 год
    elif file_extension in ['.woff', '.woff2', '.ttf', '.eot']:
        headers['Cache-Control'] = 'public, max-age=31536000, immutable'  # 1 год
        headers['ETag'] = f'"{os.path.getmtime(path)}"'
    
    # HTML файлы - кешируем на 1 час
    elif file_extension in ['.html', '.htm']:
        headers['Cache-Control'] = 'public, max-age=3600'  # 1 час
        headers['ETag'] = f'"{os.path.getmtime(path)}"'
    
    # Медиа файлы - кешируем на 30 дней
    elif file_extension in ['.mp4', '.mp3', '.avi', '.mov']:
        headers['Cache-Control'] = 'public, max-age=2592000'  # 30 дней
        headers['ETag'] = f'"{os.path.getmtime(path)}"'
    
    # Остальные файлы - кешируем на 7 дней
    else:
        headers['Cache-Control'] = 'public, max-age=604800'  # 7 дней
        headers['ETag'] = f'"{os.path.getmtime(path)}"'
    
    # Добавляем заголовки для оптимизации
    headers['Vary'] = 'Accept-Encoding'
    headers['X-Content-Type-Options'] = 'nosniff'
    headers['X-Frame-Options'] = 'SAMEORIGIN'
    
    return headers


def get_media_cache_headers(path):
    """
    Возвращает заголовки кеширования для медиа файлов
    """
    headers = {}
    file_extension = Path(path).suffix.lower()
    
    # Изображения продуктов - кешируем на 30 дней
    if file_extension in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
        headers['Cache-Control'] = 'public, max-age=2592000'  # 30 дней
        headers['ETag'] = f'"{os.path.getmtime(path)}"'
    
    # Аватары - кешируем на 7 дней
    elif 'avatars' in path:
        headers['Cache-Control'] = 'public, max-age=604800'  # 7 дней
        headers['ETag'] = f'"{os.path.getmtime(path)}"'
    
    # Остальные медиа файлы - кешируем на 1 день
    else:
        headers['Cache-Control'] = 'public, max-age=86400'  # 1 день
        headers['ETag'] = f'"{os.path.getmtime(path)}"'
    
    return headers
