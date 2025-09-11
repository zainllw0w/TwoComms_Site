"""
Middleware для автоматического выбора оптимального формата изображений
"""

from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin
import os
from pathlib import Path

class ImageOptimizationMiddleware(MiddlewareMixin):
    """
    Middleware для автоматического выбора WebP/AVIF форматов изображений
    """
    
    def process_request(self, request):
        # Проверяем, что это запрос статического файла изображения
        if not request.path.startswith('/static/'):
            return None
        
        # Получаем путь к файлу
        file_path = request.path[8:]  # Убираем '/static/'
        
        # Проверяем, что это изображение
        if not any(file_path.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif']):
            return None
        
        # Получаем User-Agent
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        
        # Проверяем поддержку AVIF
        supports_avif = any(browser in user_agent for browser in [
            'chrome/100', 'chrome/101', 'chrome/102', 'chrome/103', 'chrome/104', 'chrome/105',
            'chrome/106', 'chrome/107', 'chrome/108', 'chrome/109', 'chrome/110', 'chrome/111',
            'chrome/112', 'chrome/113', 'chrome/114', 'chrome/115', 'chrome/116', 'chrome/117',
            'chrome/118', 'chrome/119', 'chrome/120', 'chrome/121', 'chrome/122', 'chrome/123',
            'chrome/124', 'chrome/125', 'chrome/126', 'chrome/127', 'chrome/128', 'chrome/129',
            'firefox/93', 'firefox/94', 'firefox/95', 'firefox/96', 'firefox/97', 'firefox/98',
            'firefox/99', 'firefox/100', 'firefox/101', 'firefox/102', 'firefox/103', 'firefox/104',
            'firefox/105', 'firefox/106', 'firefox/107', 'firefox/108', 'firefox/109', 'firefox/110',
            'firefox/111', 'firefox/112', 'firefox/113', 'firefox/114', 'firefox/115', 'firefox/116',
            'firefox/117', 'firefox/118', 'firefox/119', 'firefox/120', 'firefox/121', 'firefox/122',
            'firefox/123', 'firefox/124', 'firefox/125', 'firefox/126', 'firefox/127', 'firefox/128',
            'firefox/129', 'safari/16', 'safari/17', 'safari/18'
        ])
        
        # Проверяем поддержку WebP
        supports_webp = any(browser in user_agent for browser in [
            'chrome', 'firefox', 'safari', 'edge', 'opera'
        ]) and not any(browser in user_agent for browser in [
            'msie', 'trident', 'chrome/23', 'chrome/24', 'chrome/25', 'chrome/26', 'chrome/27',
            'chrome/28', 'chrome/29', 'chrome/30', 'chrome/31', 'chrome/32'
        ])
        
        # Определяем оптимальный формат
        base_path = file_path.rsplit('.', 1)[0]
        extension = file_path.rsplit('.', 1)[1]
        
        # Проверяем существование оптимизированных версий
        static_root = Path('staticfiles')
        
        # AVIF (лучший сжатие)
        if supports_avif:
            avif_path = static_root / f"{base_path}.avif"
            if avif_path.exists():
                # Перенаправляем на AVIF версию
                from django.shortcuts import redirect
                return redirect(f'/static/{base_path}.avif')
        
        # WebP (хорошее сжатие, широкая поддержка)
        if supports_webp:
            webp_path = static_root / f"{base_path}.webp"
            if webp_path.exists():
                # Перенаправляем на WebP версию
                from django.shortcuts import redirect
                return redirect(f'/static/{base_path}.webp')
        
        # Если нет оптимизированных версий, возвращаем оригинал
        return None
