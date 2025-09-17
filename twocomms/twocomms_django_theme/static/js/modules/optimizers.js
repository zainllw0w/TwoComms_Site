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
  isMobile() {
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
           window.innerWidth <= 768;
  },

  isLowEndDevice() {
    return navigator.hardwareConcurrency <= 2 ||
           navigator.deviceMemory <= 2 ||
           navigator.connection?.effectiveType === 'slow-2g' ||
           navigator.connection?.effectiveType === '2g';
  },

  initMobileOptimizations() {
    if (!this.isMobile()) return;

    if (this.isLowEndDevice()) {
      PerformanceOptimizer.scrollThreshold = 20;
      document.documentElement.classList.add('perf-lite');
      const particles = document.querySelectorAll('.particle');
      particles.forEach((particle, index) => {
        if (index > 1) particle.style.display = 'none';
      });
      this.disableBackdropFilters();
      this.reduceAnimationFrequency();
    }

    this.optimizeTouchEvents();
    this.optimizeMobileImages();
  },

  optimizeTouchEvents() {
    let touchStartTime = 0;
    let touchStartX = 0;
    let touchStartY = 0;
    let touchMoved = false;
    const movementThreshold = 8;

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

      const interactiveElement = eventTarget.closest('a, button, input, label, textarea, select, [role="button"], [data-bs-toggle]');
      if (interactiveElement) {
        return;
      }

      event.preventDefault();
    }, { passive: false });
  },

  disableBackdropFilters() {
    const style = document.createElement('style');
    style.textContent = `
      .perf-lite * {
        backdrop-filter: none !important;
        -webkit-backdrop-filter: none !important;
      }
    `;
    document.head.appendChild(style);
  },

  reduceAnimationFrequency() {
    const style = document.createElement('style');
    style.textContent = `
      .perf-lite * {
        animation-duration: 0.3s !important;
        transition-duration: 0.2s !important;
      }
      .perf-lite .particle,
      .perf-lite .floating-logo {
        animation: none !important;
      }
    `;
    document.head.appendChild(style);
  },

  optimizeMobileImages() {
    const images = document.querySelectorAll('img[loading="lazy"]');
    images.forEach(img => {
      if ('IntersectionObserver' in window) {
        const observer = new IntersectionObserver((entries) => {
          entries.forEach(entry => {
            if (entry.isIntersecting) {
              const target = entry.target;
              if (target.dataset.src) {
                target.src = target.dataset.src;
                target.removeAttribute('data-src');
              }
              observer.unobserve(target);
            }
          });
        }, {
          rootMargin: '50px 0px',
          threshold: 0.1
        });
        observer.observe(img);
      }
    });
  }
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
