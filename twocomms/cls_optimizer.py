"""
Система оптимизации CLS (Cumulative Layout Shift) для TwoComms
"""

import re
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import format_html
import logging

logger = logging.getLogger(__name__)

class CLSOptimizer:
    """Класс для оптимизации CLS"""
    
    def __init__(self):
        self.critical_css = self._get_critical_css()
        self.font_display_css = self._get_font_display_css()
        self.image_dimensions_css = self._get_image_dimensions_css()
    
    def _get_critical_css(self):
        """Критический CSS для предотвращения layout shift"""
        return """
        /* Critical CSS для предотвращения CLS */
        * {
            box-sizing: border-box;
        }
        
        html {
            scroll-behavior: smooth;
        }
        
        body {
            margin: 0;
            padding: 0;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a0a;
            color: #ffffff;
            line-height: 1.6;
            overflow-x: hidden;
        }
        
        /* Предотвращение смещения навбара */
        .navbar {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            z-index: 1030;
            background: rgba(0,0,0,0.8);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid rgba(255,255,255,0.1);
            height: 60px;
            display: flex;
            align-items: center;
        }
        
        /* Предотвращение смещения main контейнера */
        main.container-xxl {
            margin-top: 60px;
            min-height: calc(100vh - 60px);
            padding: 1rem 0;
            width: 100%;
            max-width: 100%;
        }
        
        /* Hero section - фиксированные размеры */
        .hero-section {
            min-height: 100vh;
            display: flex;
            align-items: center;
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 100%);
            position: relative;
            overflow: hidden;
        }
        
        .hero-container {
            position: relative;
            z-index: 2;
            width: 100%;
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 1rem;
        }
        
        /* Hero particles - фиксированные размеры */
        .hero-particles {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 1;
            pointer-events: none;
        }
        
        /* Предотвращение смещения изображений */
        img {
            max-width: 100%;
            height: auto;
            display: block;
        }
        
        /* Карточки товаров - фиксированные размеры */
        .product-card {
            aspect-ratio: 1;
            overflow: hidden;
            border-radius: 8px;
            background: #1a1a1a;
            transition: transform 0.3s ease;
        }
        
        .product-card img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        
        /* Категории - фиксированные размеры */
        .category-item {
            aspect-ratio: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 1rem;
            border-radius: 8px;
            background: #1a1a1a;
            text-decoration: none;
            color: inherit;
            transition: transform 0.3s ease;
        }
        
        .category-icon {
            width: 48px;
            height: 48px;
            margin-bottom: 0.5rem;
        }
        
        /* Footer - фиксированная высота */
        .footer {
            background: #111111;
            padding: 2rem 0;
            margin-top: auto;
        }
        
        /* Мобильная навигация - фиксированная высота */
        .bottom-nav {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            height: 60px;
            background: rgba(0,0,0,0.9);
            backdrop-filter: blur(10px);
            border-top: 1px solid rgba(255,255,255,0.1);
            z-index: 1030;
            display: flex;
            align-items: center;
            justify-content: space-around;
        }
        
        /* Отступ для контента от мобильной навигации */
        @media (max-width: 768px) {
            main.container-xxl {
                padding-bottom: 60px;
            }
        }
        
        /* Предотвращение смещения при загрузке шрифтов */
        .font-loading {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
        }
        
        /* Skeleton loading для изображений */
        .image-skeleton {
            background: linear-gradient(90deg, #1a1a1a 25%, #2a2a2a 50%, #1a1a1a 75%);
            background-size: 200% 100%;
            animation: loading 1.5s infinite;
        }
        
        @keyframes loading {
            0% { background-position: 200% 0; }
            100% { background-position: -200% 0; }
        }
        
        /* Предотвращение смещения при загрузке контента */
        .content-loading {
            opacity: 0;
            transition: opacity 0.3s ease;
        }
        
        .content-loaded {
            opacity: 1;
        }
        """
    
    def _get_font_display_css(self):
        """CSS для оптимизации загрузки шрифтов"""
        return """
        /* Font display optimization */
        @font-face {
            font-family: 'Inter';
            font-style: normal;
            font-weight: 400;
            font-display: swap;
            src: url('https://fonts.gstatic.com/s/inter/v12/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuLyfAZ9hiJ-Ek-_EeA.woff2') format('woff2');
        }
        
        @font-face {
            font-family: 'Inter';
            font-style: normal;
            font-weight: 500;
            font-display: swap;
            src: url('https://fonts.gstatic.com/s/inter/v12/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuI6fAZ9hiJ-Ek-_EeA.woff2') format('woff2');
        }
        
        @font-face {
            font-family: 'Inter';
            font-style: normal;
            font-weight: 600;
            font-display: swap;
            src: url('https://fonts.gstatic.com/s/inter/v12/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuGKYAZ9hiJ-Ek-_EeA.woff2') format('woff2');
        }
        
        @font-face {
            font-family: 'Inter';
            font-style: normal;
            font-weight: 700;
            font-display: swap;
            src: url('https://fonts.gstatic.com/s/inter/v12/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuFuYAZ9hiJ-Ek-_EeA.woff2') format('woff2');
        }
        """
    
    def _get_image_dimensions_css(self):
        """CSS для фиксированных размеров изображений"""
        return """
        /* Фиксированные размеры для изображений товаров */
        .product-image {
            width: 100%;
            aspect-ratio: 1;
            object-fit: cover;
        }
        
        .product-image-large {
            width: 100%;
            aspect-ratio: 4/3;
            object-fit: cover;
        }
        
        /* Фиксированные размеры для иконок категорий */
        .category-icon {
            width: 48px;
            height: 48px;
            object-fit: contain;
        }
        
        .category-icon-small {
            width: 24px;
            height: 24px;
            object-fit: contain;
        }
        
        /* Фиксированные размеры для логотипа */
        .logo {
            height: 40px;
            width: auto;
        }
        
        /* Фиксированные размеры для аватаров */
        .avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            object-fit: cover;
        }
        
        .avatar-large {
            width: 80px;
            height: 80px;
            border-radius: 50%;
            object-fit: cover;
        }
        """
    
    def get_optimized_head(self):
        """Возвращает оптимизированный head с критическим CSS"""
        return format_html("""
        <style>
        {critical_css}
        {font_display_css}
        {image_dimensions_css}
        </style>
        
        <!-- Preload critical resources -->
        <link rel="preload" href="https://fonts.gstatic.com/s/inter/v12/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuLyfAZ9hiJ-Ek-_EeA.woff2" as="font" type="font/woff2" crossorigin>
        <link rel="preload" href="https://fonts.gstatic.com/s/inter/v12/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuI6fAZ9hiJ-Ek-_EeA.woff2" as="font" type="font/woff2" crossorigin>
        
        <!-- DNS prefetch for external resources -->
        <link rel="dns-prefetch" href="//fonts.googleapis.com">
        <link rel="dns-prefetch" href="//fonts.gstatic.com">
        <link rel="dns-prefetch" href="//cdn.jsdelivr.net">
        
        <!-- Preconnect to critical origins -->
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
        """,
        critical_css=self.critical_css,
        font_display_css=self.font_display_css,
        image_dimensions_css=self.image_dimensions_css
        )
    
    def get_optimized_image_tag(self, src, alt="", width=None, height=None, class_name="", lazy=True):
        """Возвращает оптимизированный тег изображения с фиксированными размерами"""
        attributes = []
        
        if width and height:
            attributes.append(f'width="{width}"')
            attributes.append(f'height="{height}"')
            # Добавляем aspect-ratio для предотвращения CLS
            aspect_ratio = width / height
            style = f'aspect-ratio: {aspect_ratio};'
        else:
            style = 'aspect-ratio: 1;'
        
        if class_name:
            attributes.append(f'class="{class_name}"')
        
        if lazy:
            attributes.append('loading="lazy"')
            attributes.append('decoding="async"')
        
        attributes.append(f'style="{style}"')
        attributes.append(f'alt="{alt}"')
        attributes.append(f'src="{src}"')
        
        return format_html('<img {}>', ' '.join(attributes))
    
    def get_optimized_product_card(self, product, image_url, title, price):
        """Возвращает оптимизированную карточку товара"""
        return format_html("""
        <div class="product-card">
            <img src="{image_url}" alt="{title}" class="product-image" width="300" height="300" loading="lazy" decoding="async">
            <div class="product-info">
                <h3 class="product-title">{title}</h3>
                <div class="product-price">{price} грн</div>
            </div>
        </div>
        """,
        image_url=image_url,
        title=title,
        price=price
        )
    
    def get_optimized_category_item(self, category, icon_url, name):
        """Возвращает оптимизированный элемент категории"""
        return format_html("""
        <a href="/category/{slug}/" class="category-item">
            <img src="{icon_url}" alt="{name}" class="category-icon" width="48" height="48" loading="lazy" decoding="async">
            <span class="category-name">{name}</span>
        </a>
        """,
        slug=category.slug,
        icon_url=icon_url,
        name=name
        )
    
    def get_loading_script(self):
        """Возвращает скрипт для предотвращения CLS при загрузке"""
        return """
        <script>
        // Предотвращение CLS при загрузке
        (function() {
            // Показываем контент только после загрузки критических ресурсов
            function showContent() {
                document.body.classList.add('content-loaded');
                document.body.classList.remove('content-loading');
            }
            
            // Проверяем загрузку шрифтов
            if ('fonts' in document) {
                document.fonts.ready.then(showContent);
            } else {
                // Fallback для старых браузеров
                window.addEventListener('load', showContent);
            }
            
            // Предотвращение смещения при загрузке изображений
            const images = document.querySelectorAll('img');
            images.forEach(img => {
                if (img.complete) {
                    img.classList.add('loaded');
                } else {
                    img.addEventListener('load', function() {
                        this.classList.add('loaded');
                    });
                }
            });
            
            // Предотвращение смещения при загрузке CSS
            const stylesheets = document.querySelectorAll('link[rel="stylesheet"]');
            let loadedStylesheets = 0;
            
            stylesheets.forEach(link => {
                if (link.sheet) {
                    loadedStylesheets++;
                } else {
                    link.addEventListener('load', function() {
                        loadedStylesheets++;
                        if (loadedStylesheets === stylesheets.length) {
                            showContent();
                        }
                    });
                }
            });
            
            // Fallback timeout
            setTimeout(showContent, 3000);
        })();
        </script>
        """
