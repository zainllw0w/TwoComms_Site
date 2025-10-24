/**
 * MOBILE OPTIMIZATIONS MODULE
 * Оптимизации производительности специально для мобильных устройств
 */

// Детекция мобильного устройства
export const isMobile = () => {
  return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
         window.innerWidth <= 768;
};

// Детекция iOS
export const isIOS = () => {
  return /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
};

// Детекция slow connection
export const isSlowConnection = () => {
  const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  if (!connection) return false;
  
  return connection.saveData ||
         connection.effectiveType === 'slow-2g' ||
         connection.effectiveType === '2g' ||
         connection.effectiveType === '3g' ||
         (connection.downlink && connection.downlink < 1.5);
};

// Детекция low-end device
export const isLowEndDevice = () => {
  const memory = navigator.deviceMemory || 4;
  const cores = navigator.hardwareConcurrency || 4;
  return memory <= 2 || cores <= 2;
};

/**
 * Passive Event Listeners для улучшения scroll performance
 */
export function setupPassiveListeners() {
  if (!('passive' in Object.getOwnPropertyDescriptor(EventTarget.prototype, 'addEventListener'))) {
    return; // Browser doesn't support passive listeners
  }
  
  // Override addEventListener для автоматического добавления passive где возможно
  const supportsPassive = (() => {
    let passive = false;
    try {
      const opts = Object.defineProperty({}, 'passive', {
        get: () => { passive = true; }
      });
      window.addEventListener('test', null, opts);
      window.removeEventListener('test', null, opts);
    } catch (e) {}
    return passive;
  })();
  
  if (!supportsPassive) return;
  
  // События которые должны быть passive для scroll performance
  const passiveEvents = ['touchstart', 'touchmove', 'wheel', 'mousewheel'];
  
  passiveEvents.forEach(eventName => {
    document.addEventListener(eventName, () => {}, { passive: true });
  });
}

/**
 * Оптимизация touch событий - предотвращение 300ms delay
 */
export function optimizeTouchEvents() {
  // Добавляем meta viewport если его нет
  let viewport = document.querySelector('meta[name="viewport"]');
  if (!viewport) {
    viewport = document.createElement('meta');
    viewport.name = 'viewport';
    viewport.content = 'width=device-width, initial-scale=1, viewport-fit=cover, user-scalable=no, maximum-scale=1';
    document.head.appendChild(viewport);
  }
  
  // FastClick альтернатива - используем touch-action в CSS
  document.documentElement.style.touchAction = 'manipulation';
}

/**
 * Lazy Loading для изображений (улучшенная версия)
 */
export function setupLazyLoading() {
  if ('loading' in HTMLImageElement.prototype) {
    // Browser supports native lazy loading
    const images = document.querySelectorAll('img[data-src]');
    images.forEach(img => {
      img.src = img.dataset.src;
      img.loading = 'lazy';
      if (img.dataset.srcset) {
        img.srcset = img.dataset.srcset;
      }
    });
  } else {
    // Fallback to Intersection Observer
    const imageObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const img = entry.target;
          if (img.dataset.src) {
            img.src = img.dataset.src;
          }
          if (img.dataset.srcset) {
            img.srcset = img.dataset.srcset;
          }
          img.classList.add('loaded');
          observer.unobserve(img);
        }
      });
    }, {
      rootMargin: '50px 0px', // Load images 50px before they enter viewport
      threshold: 0.01
    });
    
    const images = document.querySelectorAll('img[data-src]');
    images.forEach(img => imageObserver.observe(img));
  }
}

/**
 * Оптимизация скролла - предотвращение layout thrashing
 */
export function setupScrollOptimization() {
  let ticking = false;
  let lastScrollY = window.scrollY;
  
  const handleScroll = () => {
    lastScrollY = window.scrollY;
    if (!ticking) {
      window.requestAnimationFrame(() => {
        // Здесь можно добавить логику на scroll
        ticking = false;
      });
      ticking = true;
    }
  };
  
  window.addEventListener('scroll', handleScroll, { passive: true });
}

/**
 * Оптимизация анимаций - use will-change wisely
 */
export function optimizeAnimations() {
  // Добавляем will-change только когда элемент начинает анимироваться
  const animatedElements = document.querySelectorAll('.animated, [data-animate]');
  
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.willChange = 'transform, opacity';
        setTimeout(() => {
          entry.target.style.willChange = 'auto';
        }, 1000); // Remove after animation completes
      }
    });
  }, { threshold: 0.1 });
  
  animatedElements.forEach(el => observer.observe(el));
}

/**
 * Debounce функция для оптимизации событий
 */
export function debounce(func, wait = 100) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

/**
 * Throttle функция для оптимизации событий
 */
export function throttle(func, limit = 100) {
  let inThrottle;
  return function(...args) {
    if (!inThrottle) {
      func.apply(this, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
}

/**
 * Prefetch для важных ресурсов
 */
export function setupResourcePrefetch() {
  // Prefetch только на WiFi или быстром соединении
  if (isSlowConnection()) return;
  
  // Prefetch следующей страницы при hover на ссылку
  const prefetchLinks = document.querySelectorAll('a[data-prefetch]');
  
  prefetchLinks.forEach(link => {
    link.addEventListener('mouseenter', () => {
      const href = link.getAttribute('href');
      if (!href || href.startsWith('#')) return;
      
      const prefetchLink = document.createElement('link');
      prefetchLink.rel = 'prefetch';
      prefetchLink.href = href;
      document.head.appendChild(prefetchLink);
    }, { once: true, passive: true });
  });
}

/**
 * Reduce Motion для пользователей с настройкой accessibility
 */
export function setupReducedMotion() {
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  
  const applyReducedMotion = () => {
    if (prefersReducedMotion.matches) {
      document.documentElement.classList.add('reduced-motion');
      // Disable all animations
      const style = document.createElement('style');
      style.textContent = `
        .reduced-motion *,
        .reduced-motion *::before,
        .reduced-motion *::after {
          animation-duration: 0.01ms !important;
          animation-iteration-count: 1 !important;
          transition-duration: 0.01ms !important;
          scroll-behavior: auto !important;
        }
      `;
      document.head.appendChild(style);
    }
  };
  
  applyReducedMotion();
  prefersReducedMotion.addEventListener('change', applyReducedMotion);
}

/**
 * Оптимизация форм для мобильных
 */
export function optimizeMobileForms() {
  // Prevent zoom on input focus (iOS)
  const inputs = document.querySelectorAll('input, select, textarea');
  inputs.forEach(input => {
    // Set font-size to at least 16px to prevent zoom
    if (window.getComputedStyle(input).fontSize.replace('px', '') < 16) {
      input.style.fontSize = '16px';
    }
  });
  
  // Auto-capitalize first letter where appropriate
  const textInputs = document.querySelectorAll('input[type="text"]:not([autocapitalize])');
  textInputs.forEach(input => {
    if (input.name?.includes('name') || input.name?.includes('city')) {
      input.setAttribute('autocapitalize', 'words');
    }
  });
}

/**
 * Battery Status API - optimize based on battery
 */
export async function setupBatteryOptimization() {
  if (!('getBattery' in navigator)) return;
  
  try {
    const battery = await navigator.getBattery();
    
    const optimizeForBattery = () => {
      const isLowBattery = battery.level < 0.2 && !battery.charging;
      
      if (isLowBattery) {
        document.documentElement.classList.add('battery-saver');
        // Disable expensive animations
        document.querySelectorAll('video, [data-animation]').forEach(el => {
          el.pause?.();
          el.style.display = 'none';
        });
      } else {
        document.documentElement.classList.remove('battery-saver');
      }
    };
    
    optimizeForBattery();
    battery.addEventListener('levelchange', optimizeForBattery);
    battery.addEventListener('chargingchange', optimizeForBattery);
  } catch (error) {
    console.warn('Battery API not available:', error);
  }
}

/**
 * Vibration Feedback для touch events (опционально)
 */
export function addHapticFeedback(element, pattern = 10) {
  if (!('vibrate' in navigator)) return;
  
  element.addEventListener('click', () => {
    navigator.vibrate(pattern);
  }, { passive: true });
}

/**
 * Viewport Height Fix для мобильных браузеров
 */
export function fixViewportHeight() {
  const setVh = () => {
    const vh = window.innerHeight * 0.01;
    document.documentElement.style.setProperty('--vh', `${vh}px`);
  };
  
  setVh();
  window.addEventListener('resize', debounce(setVh, 100), { passive: true });
  window.addEventListener('orientationchange', setVh, { passive: true });
}

/**
 * Инициализация всех мобильных оптимизаций
 */
export function initMobileOptimizations() {
  if (!isMobile()) {
    console.log('Desktop detected, skipping mobile-specific optimizations');
    return;
  }
  
  console.log('Initializing mobile optimizations...');
  
  // Core optimizations
  setupPassiveListeners();
  optimizeTouchEvents();
  fixViewportHeight();
  
  // Performance optimizations
  setupScrollOptimization();
  optimizeAnimations();
  setupReducedMotion();
  
  // Resource optimizations
  setupLazyLoading();
  setupResourcePrefetch();
  
  // Form optimizations
  optimizeMobileForms();
  
  // Battery optimization (async)
  setupBatteryOptimization();
  
  // Low-end device detection
  if (isLowEndDevice() || isSlowConnection()) {
    document.documentElement.classList.add('perf-lite');
    console.log('Low-end device or slow connection detected, enabling performance mode');
  }
  
  console.log('Mobile optimizations initialized successfully');
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initMobileOptimizations);
} else {
  initMobileOptimizations();
}

export default {
  isMobile,
  isIOS,
  isSlowConnection,
  isLowEndDevice,
  setupPassiveListeners,
  optimizeTouchEvents,
  setupLazyLoading,
  setupScrollOptimization,
  optimizeAnimations,
  debounce,
  throttle,
  setupResourcePrefetch,
  setupReducedMotion,
  optimizeMobileForms,
  setupBatteryOptimization,
  addHapticFeedback,
  fixViewportHeight,
  initMobileOptimizations
};

