"""
Современные настройки кеширования для TwoComms
Реализует оптимальные стратегии кеширования для максимальной производительности
"""

import os
import hashlib
from pathlib import Path
from datetime import datetime, timedelta


def add_cache_headers(headers, path, url):
    """
    Добавляет современные заголовки кеширования для разных типов ресурсов
    """
    # Определяем тип файла по расширению
    file_extension = Path(path).suffix.lower()
    file_name = Path(path).name.lower()
    
    # Генерируем ETag на основе содержимого файла
    etag = generate_etag(path)
    
    # Критические статические ресурсы - кешируем на 1 год с immutable
    if (file_extension in ['.css', '.js'] and ('min' in file_name or 'compressed' in file_name)) or \
       file_extension in ['.woff', '.woff2', '.ttf', '.eot']:
        headers['Cache-Control'] = 'public, max-age=31536000, immutable'  # 1 год
        headers['ETag'] = etag
        headers['Expires'] = (datetime.utcnow() + timedelta(days=365)).strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    # Изображения - кешируем на 1 год с immutable
    elif file_extension in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif', '.svg', '.ico']:
        headers['Cache-Control'] = 'public, max-age=31536000, immutable'  # 1 год
        headers['ETag'] = etag
        headers['Expires'] = (datetime.utcnow() + timedelta(days=365)).strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    # HTML файлы - кешируем на 1 час с revalidation
    elif file_extension in ['.html', '.htm']:
        headers['Cache-Control'] = 'public, max-age=3600, must-revalidate'  # 1 час
        headers['ETag'] = etag
        headers['Last-Modified'] = datetime.fromtimestamp(os.path.getmtime(path)).strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    # Медиа файлы - кешируем на 30 дней
    elif file_extension in ['.mp4', '.mp3', '.avi', '.mov', '.webm']:
        headers['Cache-Control'] = 'public, max-age=2592000'  # 30 дней
        headers['ETag'] = etag
        headers['Expires'] = (datetime.utcnow() + timedelta(days=30)).strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    # Остальные статические файлы - кешируем на 7 дней
    else:
        headers['Cache-Control'] = 'public, max-age=604800'  # 7 дней
        headers['ETag'] = etag
        headers['Expires'] = (datetime.utcnow() + timedelta(days=7)).strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    # Добавляем современные заголовки для оптимизации
    headers['Vary'] = 'Accept-Encoding'
    headers['X-Content-Type-Options'] = 'nosniff'
    headers['X-Frame-Options'] = 'DENY'
    headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    # Добавляем заголовки для Service Worker
    headers['X-Cache-Strategy'] = get_cache_strategy(file_extension, file_name)
    
    return headers


def generate_etag(file_path):
    """
    Генерирует ETag на основе содержимого файла
    """
    try:
        stat = os.stat(file_path)
        # Используем размер файла и время модификации для ETag
        etag_data = f"{stat.st_size}-{int(stat.st_mtime)}"
        return f'"{hashlib.md5(etag_data.encode()).hexdigest()}"'
    except (OSError, IOError):
        return f'"{int(datetime.utcnow().timestamp())}"'


def get_cache_strategy(file_extension, file_name):
    """
    Определяет стратегию кеширования для Service Worker
    """
    if file_extension in ['.css', '.js', '.woff', '.woff2', '.ttf', '.eot']:
        return 'cache-first'
    elif file_extension in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif', '.svg', '.ico']:
        return 'cache-first'
    elif file_extension in ['.html', '.htm']:
        return 'stale-while-revalidate'
    elif file_extension in ['.mp4', '.mp3', '.avi', '.mov', '.webm']:
        return 'cache-first'
    else:
        return 'network-first'


def get_media_cache_headers(path):
    """
    Возвращает современные заголовки кеширования для медиа файлов
    """
    headers = {}
    file_extension = Path(path).suffix.lower()
    etag = generate_etag(path)
    
    # Изображения продуктов - кешируем на 30 дней
    if file_extension in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif']:
        headers['Cache-Control'] = 'public, max-age=2592000'  # 30 дней
        headers['ETag'] = etag
        headers['Expires'] = (datetime.utcnow() + timedelta(days=30)).strftime('%a, %d %b %Y %H:%M:%S GMT')
        headers['X-Cache-Strategy'] = 'cache-first'
    
    # Аватары - кешируем на 7 дней
    elif 'avatars' in path:
        headers['Cache-Control'] = 'public, max-age=604800'  # 7 дней
        headers['ETag'] = etag
        headers['Expires'] = (datetime.utcnow() + timedelta(days=7)).strftime('%a, %d %b %Y %H:%M:%S GMT')
        headers['X-Cache-Strategy'] = 'cache-first'
    
    # Документы и файлы - кешируем на 1 день
    elif file_extension in ['.pdf', '.doc', '.docx', '.txt']:
        headers['Cache-Control'] = 'public, max-age=86400'  # 1 день
        headers['ETag'] = etag
        headers['Expires'] = (datetime.utcnow() + timedelta(days=1)).strftime('%a, %d %b %Y %H:%M:%S GMT')
        headers['X-Cache-Strategy'] = 'network-first'
    
    # Остальные медиа файлы - кешируем на 1 день
    else:
        headers['Cache-Control'] = 'public, max-age=86400'  # 1 день
        headers['ETag'] = etag
        headers['Expires'] = (datetime.utcnow() + timedelta(days=1)).strftime('%a, %d %b %Y %H:%M:%S GMT')
        headers['X-Cache-Strategy'] = 'network-first'
    
    # Добавляем общие заголовки
    headers['Vary'] = 'Accept-Encoding'
    headers['X-Content-Type-Options'] = 'nosniff'
    headers['Last-Modified'] = datetime.fromtimestamp(os.path.getmtime(path)).strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    return headers
