/**
 * Оптимизация производительности фронтенда
 */

class PerformanceOptimizer {
    constructor() {
        this.init();
    }

    init() {
        this.lazyLoadImages();
        this.optimizeAnimations();
        this.debounceScrollEvents();
        this.preloadCriticalResources();
        this.optimizeAJAXRequests();
    }

    /**
     * Ленивая загрузка изображений
     */
    lazyLoadImages() {
        if ('IntersectionObserver' in window) {
            const imageObserver = new IntersectionObserver((entries, observer) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        img.src = img.dataset.src;
                        img.classList.remove('lazy');
                        imageObserver.unobserve(img);
                    }
                });
            });

            document.querySelectorAll('img[data-src]').forEach(img => {
                imageObserver.observe(img);
            });
        }
    }

    /**
     * Оптимизация анимаций
     */
    optimizeAnimations() {
        // Отключаем анимации для пользователей с предпочтением reduced motion
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            document.documentElement.style.setProperty('--animation-duration', '0s');
        }

        // Оптимизируем анимации с помощью will-change
        document.querySelectorAll('.animate-on-scroll').forEach(el => {
            el.style.willChange = 'transform, opacity';
        });
    }

    /**
     * Дебаунс для событий прокрутки
     */
    debounceScrollEvents() {
        let scrollTimeout;
        const scrollHandler = () => {
            clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(() => {
                this.handleScroll();
            }, 16); // ~60fps
        };

        window.addEventListener('scroll', scrollHandler, { passive: true });
    }

    /**
     * Обработка прокрутки
     */
    handleScroll() {
        const scrollY = window.scrollY;
        const windowHeight = window.innerHeight;
        const documentHeight = document.documentElement.scrollHeight;

        // Обновляем прогресс-бар
        const progress = (scrollY / (documentHeight - windowHeight)) * 100;
        document.documentElement.style.setProperty('--scroll-progress', `${progress}%`);

        // Анимация элементов при прокрутке
        this.animateOnScroll();
    }

    /**
     * Анимация элементов при прокрутке
     */
    animateOnScroll() {
        document.querySelectorAll('.animate-on-scroll').forEach(el => {
            const rect = el.getBoundingClientRect();
            const isVisible = rect.top < window.innerHeight && rect.bottom > 0;

            if (isVisible) {
                el.classList.add('animated');
            }
        });
    }

    /**
     * Предзагрузка критических ресурсов
     */
    preloadCriticalResources() {
        // Предзагружаем критические изображения
        const criticalImages = [
            '/static/img/logo.svg'
            // bg_blur_1.png убран из preload, так как не используется критически
        ];

        criticalImages.forEach(src => {
            const link = document.createElement('link');
            link.rel = 'preload';
            link.as = 'image';
            link.href = src;
            document.head.appendChild(link);
        });

        // Предзагружаем критические шрифты
        const criticalFonts = [
            '/static/fonts/inter-var.woff2'
        ];

        criticalFonts.forEach(src => {
            const link = document.createElement('link');
            link.rel = 'preload';
            link.as = 'font';
            link.type = 'font/woff2';
            link.crossOrigin = 'anonymous';
            link.href = src;
            document.head.appendChild(link);
        });
    }

    /**
     * Оптимизация AJAX запросов
     */
    optimizeAJAXRequests() {
        // Кэширование AJAX запросов
        this.ajaxCache = new Map();
        
        // Дебаунс для поиска
        let searchTimeout;
        const searchInput = document.querySelector('input[name="q"]');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    this.performSearch(e.target.value);
                }, 300);
            });
        }
    }

    /**
     * Выполнение поиска с кэшированием
     */
    async performSearch(query) {
        if (query.length < 2) return;

        const cacheKey = `search_${query}`;
        if (this.ajaxCache.has(cacheKey)) {
            this.displaySearchResults(this.ajaxCache.get(cacheKey));
            return;
        }

        try {
            const response = await fetch(`/search/?q=${encodeURIComponent(query)}`);
            const data = await response.json();
            
            this.ajaxCache.set(cacheKey, data);
            this.displaySearchResults(data);
        } catch (error) {
            console.error('Search error:', error);
        }
    }

    /**
     * Отображение результатов поиска
     */
    displaySearchResults(data) {
        // Логика отображения результатов поиска
        const resultsContainer = document.querySelector('.search-results');
        if (resultsContainer) {
            resultsContainer.innerHTML = data.html || '';
        }
    }

    /**
     * Оптимизация загрузки товаров
     */
    async loadMoreProducts(page) {
        const cacheKey = `products_page_${page}`;
        if (this.ajaxCache.has(cacheKey)) {
            return this.ajaxCache.get(cacheKey);
        }

        try {
            const response = await fetch(`/load-more/?page=${page}`);
            const data = await response.json();
            
            this.ajaxCache.set(cacheKey, data);
            return data;
        } catch (error) {
            console.error('Load more error:', error);
            return null;
        }
    }

    /**
     * Оптимизация изображений
     */
    optimizeImages() {
        // Добавляем loading="lazy" для всех изображений
        document.querySelectorAll('img:not([loading])').forEach(img => {
            img.loading = 'lazy';
        });

        // Оптимизируем размеры изображений
        document.querySelectorAll('img').forEach(img => {
            if (img.naturalWidth > img.clientWidth * 2) {
                img.style.imageRendering = 'crisp-edges';
            }
        });
    }

    /**
     * Мониторинг производительности
     */
    monitorPerformance() {
        // Измеряем Core Web Vitals
        if ('PerformanceObserver' in window) {
            // Largest Contentful Paint
            new PerformanceObserver((list) => {
                const entries = list.getEntries();
                const lastEntry = entries[entries.length - 1];
                console.log('LCP:', lastEntry.startTime);
            }).observe({ entryTypes: ['largest-contentful-paint'] });

            // First Input Delay
            new PerformanceObserver((list) => {
                const entries = list.getEntries();
                entries.forEach(entry => {
                    console.log('FID:', entry.processingStart - entry.startTime);
                });
            }).observe({ entryTypes: ['first-input'] });

            // Cumulative Layout Shift
            new PerformanceObserver((list) => {
                let clsValue = 0;
                const entries = list.getEntries();
                entries.forEach(entry => {
                    if (!entry.hadRecentInput) {
                        clsValue += entry.value;
                    }
                });
                console.log('CLS:', clsValue);
            }).observe({ entryTypes: ['layout-shift'] });
        }
    }
}

// Инициализация при загрузке DOM
document.addEventListener('DOMContentLoaded', () => {
    new PerformanceOptimizer();
});

// Экспорт для использования в других модулях
window.PerformanceOptimizer = PerformanceOptimizer;
