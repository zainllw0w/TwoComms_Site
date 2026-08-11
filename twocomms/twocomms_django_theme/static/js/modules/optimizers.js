// Performance related helpers split from main bundle

import { DOMCache, prefersReducedMotion } from './shared.js';

export const PerformanceOptimizer = {
  scrollHandler: null,
  scrollTimeout: null,

  initScrollOptimization() {
    let ticking = false;
    let lastScrollY = 0;

    const updateScroll = () => {
      if (!ticking) {
        requestAnimationFrame(() => {
          const currentScrollY = window.pageYOffset || document.documentElement.scrollTop;
          this.handleScroll(currentScrollY, lastScrollY);
          lastScrollY = currentScrollY;
          ticking = false;
        });
        ticking = true;
      }
    };

    window.addEventListener('scroll', updateScroll, { passive: true });
  },

  handleScroll(currentY, lastY) {
    const scrollDelta = Math.abs(currentY - lastY);
    if (scrollDelta > 5) {
      this.onScrollChange(currentY, lastY);
    }
  },

  onScrollChange() {},

  getScrollY() {
    return window.pageYOffset || document.documentElement.scrollTop;
  },

  batchDOMOperations(operations) {
    requestAnimationFrame(() => {
      operations.forEach(op => {
        try {
          op();
        } catch (e) {
          console.warn('DOM operation failed:', e);
        }
      });
    });
  }
};

export const MobileOptimizer = {
  touchEventsOptimized: false,

  isMobile() {
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
           window.innerWidth <= 768;
  },

  isLowEndDevice() {
    // Phase 3.1: читаем унифицированный data-device-class, с fallback на старую эвристику.
    const dc = (document.documentElement.dataset.deviceClass || '').toLowerCase();
    if (dc === 'low') return true;
    if (dc === 'mid' || dc === 'high') return false;
    return navigator.hardwareConcurrency <= 2 ||
           navigator.deviceMemory <= 2 ||
           navigator.connection?.effectiveType === 'slow-2g' ||
           navigator.connection?.effectiveType === '2g';
  },

  initMobileOptimizations() {
    if (!this.isMobile()) return;

    // Класс `perf-lite` уже выставлен inline-детектором в base.html (Phase 3.1).
    // Здесь применяем только рантайм-твики, которые невозможны чистым CSS.
    if (this.isLowEndDevice()) {
      const particles = document.querySelectorAll('.particle');
      particles.forEach((particle, index) => {
        if (index > 1) particle.style.display = 'none';
      });
    }

    this.optimizeTouchEvents();
  },

  optimizeTouchEvents() {
    if (this.touchEventsOptimized) return;
    this.touchEventsOptimized = true;

    let touchStartTime = 0;
    let touchStartX = 0;
    let touchStartY = 0;
    let touchMoved = false;
    let suppressClickTarget = null;
    let suppressClickUntil = 0;
    const movementThreshold = 8;
    const interactiveSelector = 'a, button, input, label, textarea, select, [role="button"], [data-bs-toggle]';

    document.addEventListener('touchstart', (event) => {
      const touch = event.touches[0];
      touchStartTime = Date.now();
      touchMoved = false;
      if (touch) {
        touchStartX = touch.clientX;
        touchStartY = touch.clientY;
      }
    }, { passive: true });

    document.addEventListener('touchmove', (event) => {
      const touch = event.touches[0];
      if (!touch) {
        return;
      }
      const deltaX = Math.abs(touch.clientX - touchStartX);
      const deltaY = Math.abs(touch.clientY - touchStartY);
      if (deltaX > movementThreshold || deltaY > movementThreshold) {
        touchMoved = true;
      }
    }, { passive: true });

    document.addEventListener('touchend', (event) => {
      const touchDuration = Date.now() - touchStartTime;
      if (!touchMoved || touchDuration >= 200) {
        return;
      }

      const eventTarget = event.target;
      if (!(eventTarget instanceof Element)) {
        return;
      }

      const interactiveElement = eventTarget.closest(interactiveSelector);
      if (interactiveElement) {
        return;
      }

      suppressClickTarget = eventTarget;
      suppressClickUntil = Date.now() + 400;
    }, { passive: true });

    document.addEventListener('touchcancel', () => {
      touchMoved = false;
    }, { passive: true });

    document.addEventListener('click', (event) => {
      if (!suppressClickTarget || Date.now() > suppressClickUntil) {
        suppressClickTarget = null;
        return;
      }

      const eventTarget = event.target;
      const swipeTarget = suppressClickTarget;
      suppressClickTarget = null;
      if (!(eventTarget instanceof Element) || eventTarget.closest(interactiveSelector)) {
        return;
      }

      const sameTarget = eventTarget === swipeTarget ||
        eventTarget.contains(swipeTarget) ||
        swipeTarget.contains(eventTarget);
      if (!sameTarget) return;

      if (event.cancelable) event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
    }, true);
  },

  // disableBackdropFilters / reduceAnimationFrequency переведены в статический CSS
  // (home.css, блок Phase 3.2) — runtime-инъекция style больше не нужна.

};

export const ImageOptimizer = {
  initLazyImages() {
    const lazyImages = document.querySelectorAll('img[loading="lazy"]');

    if ('IntersectionObserver' in window) {
      const imageObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            const img = entry.target;
            img.classList.add('loaded');
            observer.unobserve(img);
          }
        });
      }, {
        rootMargin: '50px 0px',
        threshold: 0.01
      });

      lazyImages.forEach(img => imageObserver.observe(img));
    } else {
      lazyImages.forEach(img => img.classList.add('loaded'));
    }
  },

  optimizeResponsiveImages() {
    const pictures = document.querySelectorAll('picture');
    pictures.forEach(picture => {
      const img = picture.querySelector('img');
      if (img) {
        img.addEventListener('load', () => {
          img.classList.add('loaded');
        });
        img.style.contain = 'layout';
      }
    });
  },

  init() {
    this.initLazyImages();
    this.optimizeResponsiveImages();
  }
};

export function initOptimizers() {
  document.addEventListener('DOMContentLoaded', () => {
    ImageOptimizer.init();
  });
}
