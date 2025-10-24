// main-optimized.js - Optimized version with code splitting

import {
  DOMCache,
  debounce,
  scheduleIdle,
  prefersReducedMotion,
  PERF_LITE,
  nextEvt,
  nowTs,
  getCookie
} from './modules/shared.js';

// Critical imports - загружаются сразу
import MobileOptimizer from './modules/mobile-optimizer.js';

// Инициализируем мобильный оптимизатор сразу
MobileOptimizer.init();

// Помечаем, что основной JS инициализирован
document.documentElement.classList.add('js-ready');

// ===== DYNAMIC IMPORTS =====
// Lazy modules - загружаются по требованию

let PerformanceOptimizer, ImageOptimizer;
let LazyLoader, WebVitalsMonitor;

// Загружаем критические оптимизаторы при idle
scheduleIdle(async () => {
  const { PerformanceOptimizer: PerfOpt, ImageOptimizer: ImgOpt } = await import('./modules/optimizers.js');
  PerformanceOptimizer = PerfOpt;
  ImageOptimizer = ImgOpt;
  ImageOptimizer.init();
});

// Загружаем monitoring только если нужен
if (!window.location.pathname.includes('/admin/')) {
  scheduleIdle(async () => {
    const { default: Monitor } = await import('./modules/web-vitals-monitor.js');
    WebVitalsMonitor = Monitor;
  });
}

// Lazy loader всегда нужен
scheduleIdle(async () => {
  const { default: Loader } = await import('./modules/lazy-loader.js');
  LazyLoader = Loader;
});

// ===== ROUTE-BASED CODE SPLITTING =====

const currentPath = window.location.pathname;

// Продуктовая страница
if (currentPath.includes('/product/') || currentPath.includes('/p/')) {
  scheduleIdle(async () => {
    const { initProductPage } = await import('./modules/product-media.js');
    initProductPage();
  });
}

// Корзина
if (currentPath.includes('/cart/') || document.querySelector('#cart-panel')) {
  scheduleIdle(async () => {
    const { initCart } = await import('./modules/cart.js');
    initCart();
  });
}

// Главная страница
if (currentPath === '/' || currentPath === '/home/') {
  scheduleIdle(async () => {
    const { initHomepage } = await import('./modules/homepage.js');
    initHomepage();
  });
}

// ===== BASIC ANIMATIONS (Critical, inline) =====

const observerOptions = {
  threshold: 0.12,
  rootMargin: '0px 0px -10% 0px',
  passive: true
};

const supportsIO = 'IntersectionObserver' in window;
const io = supportsIO ? new IntersectionObserver(e => {
  e.forEach(t => {
    if (t.isIntersecting) {
      t.target.classList.add('visible');
      io.unobserve(t.target);
    }
  });
}, observerOptions) : null;

document.addEventListener('DOMContentLoaded', () => {
  // Базовые reveal анимации
  const registerRevealTargets = (scope = document) => {
    const basicTargets = scope.querySelectorAll('.reveal, .reveal-fast');
    if (!supportsIO) {
      basicTargets.forEach(el => el.classList.add('visible'));
      return;
    }
    basicTargets.forEach(el => io.observe(el));
  };
  registerRevealTargets();

  // Stagger grid анимации
  const gridObserver = supportsIO ? new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      const grid = entry.target;
      const ordered = Array.from(grid.querySelectorAll('.stagger-item'));
      const count = ordered.length || 1;
      const step = (prefersReducedMotion || PERF_LITE) ? 0 : Math.max(50, Math.min(110, Math.floor(900 / count)));
      
      ordered.forEach((el, i) => {
        el.style.setProperty('--d', (i * step) + 'ms');
        const revealCard = () => {
          el.classList.add('visible');
          const colorDots = el.closest('.product-card-wrap')?.querySelector('.product-card-dots');
          if (colorDots) {
            colorDots.classList.add('visible');
            const dots = colorDots.querySelectorAll('.color-dot');
            dots.forEach((dot, dotIndex) => {
              setTimeout(() => dot.classList.add('visible'), prefersReducedMotion ? 0 : (dotIndex * 60));
            });
          }
        };
        step === 0 ? revealCard() : setTimeout(revealCard, i * step);
      });
      gridObserver.unobserve(grid);
    });
  }, { threshold: .12, rootMargin: '0px 0px -10% 0px' }) : null;

  const grids = document.querySelectorAll('[data-stagger-grid]');
  if (!supportsIO) {
    grids.forEach(grid => {
      const items = grid.querySelectorAll('.stagger-item');
      items.forEach(el => el.classList.add('visible'));
    });
  } else {
    grids.forEach(g => gridObserver.observe(g));
  }
});

// ===== FEATURE DETECTION =====

// Preload критических ресурсов для следующих страниц
const prefetchOnHover = (selector, moduleUrl) => {
  document.addEventListener('mouseover', (e) => {
    const link = e.target.closest(selector);
    if (link && !link.dataset.prefetched) {
      link.dataset.prefetched = 'true';
      const prefetchLink = document.createElement('link');
      prefetchLink.rel = 'prefetch';
      prefetchLink.href = moduleUrl;
      document.head.appendChild(prefetchLink);
    }
  }, { passive: true });
};

// Prefetch модулей при hover на ссылках
prefetchOnHover('a[href*="/product/"]', '/static/js/modules/product-media.js');
prefetchOnHover('a[href*="/cart/"]', '/static/js/modules/cart.js');

// Export для глобального доступа (если нужно)
window.TwoComms = {
  get PerformanceOptimizer() { return PerformanceOptimizer; },
  get ImageOptimizer() { return ImageOptimizer; },
  get LazyLoader() { return LazyLoader; },
  get WebVitalsMonitor() { return WebVitalsMonitor; },
  MobileOptimizer,
  DOMCache,
  debounce,
  scheduleIdle
};

console.log('[TwoComms] Main app initialized with code splitting ✨');

