/**
 * Мобильная оптимизация JavaScript
 * Улучшает производительность на мобильных устройствах
 */

(function() {
    'use strict';
    
    // Определяем возможности устройства
    const deviceInfo = {
        isMobile: /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent),
        isTouch: 'ontouchstart' in window || navigator.maxTouchPoints > 0,
        connection: navigator.connection || navigator.mozConnection || navigator.webkitConnection,
        memory: navigator.deviceMemory || 0,
        cores: navigator.hardwareConcurrency || 0
    };
    
    // Определяем медленное соединение
    const isSlowConnection = deviceInfo.connection && 
        (deviceInfo.connection.effectiveType === 'slow-2g' || 
         deviceInfo.connection.effectiveType === '2g' ||
         deviceInfo.connection.saveData);
    
    // Определяем слабое устройство
    const isLowEndDevice = deviceInfo.memory <= 2 || deviceInfo.cores <= 2;
    
    // Применяем оптимизации
    if (isSlowConnection || isLowEndDevice) {
        document.documentElement.classList.add('perf-lite');
    }
    
    // Оптимизация изображений для мобильных
    function optimizeImages() {
        if (!deviceInfo.isMobile) return;
        
        const images = document.querySelectorAll('img[data-src]');
        
        // Intersection Observer для lazy loading
        if ('IntersectionObserver' in window) {
            const imageObserver = new IntersectionObserver((entries, observer) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        img.src = img.dataset.src;
                        img.classList.remove('lazy');
                        observer.unobserve(img);
                    }
                });
            }, {
                rootMargin: '50px 0px',
                threshold: 0.01
            });
            
            images.forEach(img => imageObserver.observe(img));
        } else {
            // Fallback для старых браузеров
            images.forEach(img => {
                img.src = img.dataset.src;
                img.classList.remove('lazy');
            });
        }
    }
    
    // Оптимизация анимаций
    function optimizeAnimations() {
        if (isLowEndDevice || isSlowConnection) {
            // Отключаем сложные анимации
            const style = document.createElement('style');
            style.textContent = `
                .perf-lite * {
                    animation-duration: 0.01ms !important;
                    animation-iteration-count: 1 !important;
                    transition-duration: 0.01ms !important;
                }
                .perf-lite .hero::before,
                .perf-lite .hero::after {
                    display: none !important;
                }
            `;
            document.head.appendChild(style);
        }
    }
    
    // Оптимизация touch событий
    function optimizeTouchEvents() {
        if (!deviceInfo.isTouch) return;
        
        // Предотвращаем двойной тап для зума
        let lastTouchEnd = 0;
        document.addEventListener('touchend', function(event) {
            const now = (new Date()).getTime();
            if (now - lastTouchEnd <= 300) {
                event.preventDefault();
            }
            lastTouchEnd = now;
        }, false);
        
        // Улучшаем прокрутку
        document.addEventListener('touchstart', function() {}, {passive: true});
        document.addEventListener('touchmove', function() {}, {passive: true});
    }
    
    // Оптимизация производительности
    function optimizePerformance() {
        // Debounce для resize событий
        let resizeTimeout;
        window.addEventListener('resize', function() {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(function() {
                // Обновляем layout только после завершения resize
                document.documentElement.style.setProperty('--vh', `${window.innerHeight * 0.01}px`);
            }, 250);
        });
        
        // Оптимизация скролла
        let scrollTimeout;
        window.addEventListener('scroll', function() {
            if (!scrollTimeout) {
                requestAnimationFrame(function() {
                    // Обновляем только при необходимости
                    scrollTimeout = null;
                });
            }
        }, {passive: true});
    }
    
    // Инициализация при загрузке DOM
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            optimizeImages();
            optimizeAnimations();
            optimizeTouchEvents();
            optimizePerformance();
        });
    } else {
        optimizeImages();
        optimizeAnimations();
        optimizeTouchEvents();
        optimizePerformance();
    }
    
    // Экспортируем для использования в других скриптах
    window.MobileOptimization = {
        deviceInfo: deviceInfo,
        isSlowConnection: isSlowConnection,
        isLowEndDevice: isLowEndDevice,
        optimizeImages: optimizeImages,
        optimizeAnimations: optimizeAnimations
    };
    
})();
