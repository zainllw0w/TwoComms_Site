/**
 * Mobile Performance Optimizer
 * Критические оптимизации для мобильных устройств
 */

// Детекция мобильного устройства
export const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
export const isIOS = /iPhone|iPad|iPod/i.test(navigator.userAgent);
export const isAndroid = /Android/i.test(navigator.userAgent);
export const isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;

// Получение информации о соединении
export const getConnectionInfo = () => {
  const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  if (!conn) return { effectiveType: 'unknown', saveData: false };
  
  return {
    effectiveType: conn.effectiveType || 'unknown',
    saveData: conn.saveData || false,
    downlink: conn.downlink || 0,
    rtt: conn.rtt || 0
  };
};

// Проверка слабого соединения
export const isSlowConnection = () => {
  const conn = getConnectionInfo();
  return conn.effectiveType === 'slow-2g' || 
         conn.effectiveType === '2g' || 
         conn.effectiveType === '3g' ||
         conn.saveData;
};

// Проверка слабого устройства
export const isLowEndDevice = () => {
  const memory = navigator.deviceMemory || 4;
  const cores = navigator.hardwareConcurrency || 4;
  return memory <= 2 || cores <= 2;
};

// Оптимизированный debounce для мобильных
export const mobileDebounce = (func, wait = 150) => {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
};

// Оптимизированный throttle для мобильных
export const mobileThrottle = (func, limit = 100) => {
  let inThrottle;
  return function(...args) {
    if (!inThrottle) {
      func.apply(this, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
};

// Passive event listeners для лучшей производительности скролла
export const addPassiveListener = (element, event, handler) => {
  if (element && event && handler) {
    element.addEventListener(event, handler, { passive: true });
  }
};

// Оптимизация скролла
export class ScrollOptimizer {
  constructor() {
    this.ticking = false;
    this.lastScrollY = window.scrollY;
  }

  onScroll(callback) {
    if (!this.ticking) {
      window.requestAnimationFrame(() => {
        callback(window.scrollY, this.lastScrollY);
        this.lastScrollY = window.scrollY;
        this.ticking = false;
      });
      this.ticking = true;
    }
  }

  init(callback) {
    addPassiveListener(window, 'scroll', () => this.onScroll(callback));
  }
}

// Оптимизация touch событий
export class TouchOptimizer {
  constructor() {
    this.startX = 0;
    this.startY = 0;
    this.distX = 0;
    this.distY = 0;
  }

  handleSwipe(element, callbacks) {
    if (!element) return;

    element.addEventListener('touchstart', (e) => {
      const touch = e.touches[0];
      this.startX = touch.clientX;
      this.startY = touch.clientY;
    }, { passive: true });

    element.addEventListener('touchmove', (e) => {
      if (!this.startX || !this.startY) return;
      
      const touch = e.touches[0];
      this.distX = touch.clientX - this.startX;
      this.distY = touch.clientY - this.startY;
    }, { passive: true });

    element.addEventListener('touchend', () => {
      const threshold = 50;
      
      if (Math.abs(this.distX) > threshold) {
        if (this.distX > 0 && callbacks.right) {
          callbacks.right();
        } else if (this.distX < 0 && callbacks.left) {
          callbacks.left();
        }
      }
      
      if (Math.abs(this.distY) > threshold) {
        if (this.distY > 0 && callbacks.down) {
          callbacks.down();
        } else if (this.distY < 0 && callbacks.up) {
          callbacks.up();
        }
      }
      
      this.startX = 0;
      this.startY = 0;
      this.distX = 0;
      this.distY = 0;
    }, { passive: true });
  }
}

// Оптимизация изображений для мобильных
export class MobileImageOptimizer {
  static init() {
    if (!isMobile) return;

    // Используем Intersection Observer для ленивой загрузки
    const imageObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const img = entry.target;
          
          // Загружаем изображение
          if (img.dataset.src) {
            img.src = img.dataset.src;
            img.removeAttribute('data-src');
          }
          
          // Загружаем srcset
          if (img.dataset.srcset) {
            img.srcset = img.dataset.srcset;
            img.removeAttribute('data-srcset');
          }
          
          // Добавляем класс loaded
          img.classList.add('loaded');
          
          imageObserver.unobserve(img);
        }
      });
    }, {
      rootMargin: '50px', // Загружаем немного раньше
      threshold: 0.01
    });

    // Наблюдаем за всеми изображениями с data-src
    document.querySelectorAll('img[data-src], img[loading="lazy"]').forEach(img => {
      imageObserver.observe(img);
    });
  }

  static prefetchImage(url) {
    const link = document.createElement('link');
    link.rel = 'prefetch';
    link.href = url;
    link.as = 'image';
    document.head.appendChild(link);
  }
}

// Оптимизация анимаций
export class AnimationOptimizer {
  static shouldAnimate() {
    // Проверяем prefers-reduced-motion
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return false;
    }
    
    // Проверяем perf-lite
    if (document.documentElement.classList.contains('perf-lite')) {
      return false;
    }
    
    // Проверяем слабое устройство
    if (isLowEndDevice()) {
      return false;
    }
    
    return true;
  }

  static disableHeavyAnimations() {
    if (!this.shouldAnimate()) {
      document.documentElement.classList.add('no-animations');
      
      // Устанавливаем минимальные значения для анимаций
      const style = document.createElement('style');
      style.textContent = `
        * {
          animation-duration: 0.01ms !important;
          animation-delay: 0.01ms !important;
          transition-duration: 0.01ms !important;
          transition-delay: 0.01ms !important;
        }
      `;
      document.head.appendChild(style);
    }
  }
}

// Оптимизация производительности форм
export class FormOptimizer {
  static preventZoom() {
    if (!isMobile) return;

    // Устанавливаем font-size: 16px для всех input, чтобы предотвратить зум на iOS
    const inputs = document.querySelectorAll('input, textarea, select');
    inputs.forEach(input => {
      const computedFontSize = window.getComputedStyle(input).fontSize;
      if (parseFloat(computedFontSize) < 16) {
        input.style.fontSize = '16px';
      }
    });
  }

  static optimizeAutocomplete() {
    // Отключаем автокомплит где не нужен
    const searchInputs = document.querySelectorAll('input[type="search"]');
    searchInputs.forEach(input => {
      if (!input.hasAttribute('autocomplete')) {
        input.setAttribute('autocomplete', 'off');
      }
    });
  }
}

// Оптимизация памяти
export class MemoryOptimizer {
  static clearUnusedResources() {
    // Очищаем неиспользуемые изображения из памяти
    const images = document.querySelectorAll('img');
    images.forEach(img => {
      if (!img.isConnected) {
        img.src = '';
        img.srcset = '';
      }
    });
    
    // Trigger garbage collection (если доступно)
    if (window.gc) {
      window.gc();
    }
  }

  static monitorMemory() {
    if (!performance.memory) return null;

    const memory = performance.memory;
    const used = memory.usedJSHeapSize / 1048576; // MB
    const total = memory.totalJSHeapSize / 1048576; // MB
    const limit = memory.jsHeapSizeLimit / 1048576; // MB

    return {
      used: used.toFixed(2),
      total: total.toFixed(2),
      limit: limit.toFixed(2),
      percentage: ((used / limit) * 100).toFixed(2)
    };
  }
}

// Оптимизация сети
export class NetworkOptimizer {
  static prefetchCriticalResources(urls) {
    if (isSlowConnection()) return;

    urls.forEach(url => {
      const link = document.createElement('link');
      link.rel = 'prefetch';
      link.href = url;
      document.head.appendChild(link);
    });
  }

  static preconnectToDomains(domains) {
    domains.forEach(domain => {
      const link = document.createElement('link');
      link.rel = 'preconnect';
      link.href = domain;
      link.crossOrigin = 'anonymous';
      document.head.appendChild(link);
    });
  }
}

// Главный класс мобильного оптимизатора
export class MobileOptimizer {
  static init() {
    // Добавляем классы к html
    if (isMobile) {
      document.documentElement.classList.add('is-mobile');
    }
    if (isIOS) {
      document.documentElement.classList.add('is-ios');
    }
    if (isAndroid) {
      document.documentElement.classList.add('is-android');
    }
    if (isTouchDevice) {
      document.documentElement.classList.add('touch-device');
    }

    // Инициализируем оптимизации
    AnimationOptimizer.disableHeavyAnimations();
    FormOptimizer.preventZoom();
    FormOptimizer.optimizeAutocomplete();
    MobileImageOptimizer.init();

    // Мониторинг памяти каждые 30 секунд
    if (isMobile) {
      setInterval(() => {
        const memInfo = MemoryOptimizer.monitorMemory();
        if (memInfo && parseFloat(memInfo.percentage) > 80) {
          console.warn('High memory usage detected:', memInfo);
          MemoryOptimizer.clearUnusedResources();
        }
      }, 30000);
    }

    // Слушаем изменения соединения
    if (navigator.connection) {
      navigator.connection.addEventListener('change', () => {
        const conn = getConnectionInfo();
        console.log('Connection changed:', conn);
        
        if (conn.saveData || conn.effectiveType === '2g') {
          document.documentElement.classList.add('perf-lite');
        }
      });
    }

    // Оптимизация при видимости страницы
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        // Страница скрыта - очищаем ресурсы
        MemoryOptimizer.clearUnusedResources();
      }
    });

    console.log('Mobile optimizer initialized:', {
      isMobile,
      isIOS,
      isAndroid,
      isTouchDevice,
      connection: getConnectionInfo(),
      memory: MemoryOptimizer.monitorMemory(),
      lowEnd: isLowEndDevice()
    });
  }
}

// Экспортируем для использования в main.js
export default MobileOptimizer;

