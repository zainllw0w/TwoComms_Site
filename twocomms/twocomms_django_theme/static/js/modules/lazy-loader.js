// twocomms/twocomms_django_theme/static/js/modules/lazy-loader.js

/**
 * Lazy Loading Module для оптимизации загрузки контента
 * Использует Intersection Observer API для отслеживания видимости элементов
 */

import { prefersReducedMotion, PERF_LITE } from './shared.js';

class LazyLoader {
  constructor() {
    this.observers = new Map();
    this.loadedElements = new WeakSet();
    this.init();
  }

  init() {
    // Загружаем изображения
    this.observeImages();
    
    // Загружаем секции с анимациями
    this.observeSections();
    
    // Загружаем видео и iframes
    this.observeMedia();
    
    console.log('[LazyLoader] Initialized with Intersection Observer');
  }

  /**
   * Создает Intersection Observer с заданными опциями
   */
  createObserver(callback, options = {}) {
    const defaultOptions = {
      root: null,
      rootMargin: '50px', // Начинаем загрузку за 50px до появления
      threshold: 0.01
    };

    return new IntersectionObserver(callback, { ...defaultOptions, ...options });
  }

  /**
   * Lazy loading для изображений
   */
  observeImages() {
    const images = document.querySelectorAll('img[data-src], img[loading="lazy"]');
    
    if (images.length === 0) return;

    const imageObserver = this.createObserver((entries, observer) => {
      entries.forEach(entry => {
        if (entry.isIntersecting && !this.loadedElements.has(entry.target)) {
          this.loadImage(entry.target);
          this.loadedElements.add(entry.target);
          observer.unobserve(entry.target);
        }
      });
    }, { rootMargin: '100px' });

    images.forEach(img => imageObserver.observe(img));
    this.observers.set('images', imageObserver);
  }

  /**
   * Загружает изображение
   */
  loadImage(img) {
    const dataSrc = img.dataset.src;
    const dataSrcset = img.dataset.srcset;
    
    if (dataSrc) {
      img.src = dataSrc;
      img.removeAttribute('data-src');
    }
    
    if (dataSrcset) {
      img.srcset = dataSrcset;
      img.removeAttribute('data-srcset');
    }

    // Добавляем класс после загрузки
    img.addEventListener('load', () => {
      img.classList.add('loaded');
    }, { once: true });

    // Обработка ошибок
    img.addEventListener('error', () => {
      console.error('[LazyLoader] Failed to load image:', img.src);
      img.classList.add('error');
    }, { once: true });
  }

  /**
   * Lazy loading для секций с анимациями
   */
  observeSections() {
    const sections = document.querySelectorAll('[data-lazy-section]');
    
    if (sections.length === 0) return;

    const sectionObserver = this.createObserver((entries, observer) => {
      entries.forEach(entry => {
        if (entry.isIntersecting && !this.loadedElements.has(entry.target)) {
          this.loadSection(entry.target);
          this.loadedElements.add(entry.target);
          observer.unobserve(entry.target);
        }
      });
    }, { rootMargin: '200px', threshold: 0.1 });

    sections.forEach(section => sectionObserver.observe(section));
    this.observers.set('sections', sectionObserver);
  }

  /**
   * Загружает секцию и активирует анимации
   */
  loadSection(section) {
    const animationClass = section.dataset.animation || 'fade-in';
    
    // Отключаем анимации для perf-lite или reduced-motion
    if (PERF_LITE || prefersReducedMotion) {
      section.classList.add('loaded', 'no-animation');
      return;
    }

    // Задержка анимации если указана
    const delay = parseInt(section.dataset.delay) || 0;
    
    setTimeout(() => {
      section.classList.add('loaded', animationClass);
    }, delay);
  }

  /**
   * Lazy loading для видео и iframes
   */
  observeMedia() {
    const media = document.querySelectorAll('iframe[data-src], video[data-src]');
    
    if (media.length === 0) return;

    const mediaObserver = this.createObserver((entries, observer) => {
      entries.forEach(entry => {
        if (entry.isIntersecting && !this.loadedElements.has(entry.target)) {
          this.loadMedia(entry.target);
          this.loadedElements.add(entry.target);
          observer.unobserve(entry.target);
        }
      });
    }, { rootMargin: '300px' });

    media.forEach(element => mediaObserver.observe(element));
    this.observers.set('media', mediaObserver);
  }

  /**
   * Загружает медиа элемент (iframe/video)
   */
  loadMedia(element) {
    const dataSrc = element.dataset.src;
    
    if (!dataSrc) return;

    if (element.tagName === 'IFRAME') {
      // Для iframes (YouTube, etc.)
      element.src = dataSrc;
    } else if (element.tagName === 'VIDEO') {
      // Для video
      element.src = dataSrc;
      
      // Автозапуск если указано
      if (element.dataset.autoplay === 'true') {
        element.play().catch(err => {
          console.warn('[LazyLoader] Autoplay blocked:', err);
        });
      }
    }

    element.removeAttribute('data-src');
    element.classList.add('loaded');
  }

  /**
   * Принудительная загрузка всех элементов (например, при выключенном JS)
   */
  loadAll() {
    this.observers.forEach(observer => observer.disconnect());
    
    document.querySelectorAll('img[data-src]').forEach(img => this.loadImage(img));
    document.querySelectorAll('[data-lazy-section]').forEach(section => this.loadSection(section));
    document.querySelectorAll('iframe[data-src], video[data-src]').forEach(media => this.loadMedia(media));
    
    console.log('[LazyLoader] All elements loaded forcefully');
  }

  /**
   * Очистка (для освобождения памяти)
   */
  destroy() {
    this.observers.forEach(observer => observer.disconnect());
    this.observers.clear();
    this.loadedElements = new WeakSet();
    console.log('[LazyLoader] Destroyed');
  }
}

// Автоматическая инициализация
let lazyLoaderInstance = null;

if ('IntersectionObserver' in window) {
  document.addEventListener('DOMContentLoaded', () => {
    lazyLoaderInstance = new LazyLoader();
  });
} else {
  // Fallback для старых браузеров - загружаем все сразу
  console.warn('[LazyLoader] IntersectionObserver not supported, loading all content immediately');
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('img[data-src]').forEach(img => {
      if (img.dataset.src) img.src = img.dataset.src;
      if (img.dataset.srcset) img.srcset = img.dataset.srcset;
    });
    
    document.querySelectorAll('iframe[data-src], video[data-src]').forEach(media => {
      if (media.dataset.src) media.src = media.dataset.src;
    });
  });
}

export default LazyLoader;
export { lazyLoaderInstance };

