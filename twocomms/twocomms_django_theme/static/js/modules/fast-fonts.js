/**
 * Fast Fonts Loading Strategy
 * Оптимальная загрузка шрифтов для мобильных устройств
 * 
 * Strategy:
 * 1. System fonts сразу (zero FOIT/FOUT)
 * 2. Web fonts асинхронно с font-display: optional
 * 3. Кэширование через Service Worker
 * 4. Preload для критических шрифтов
 * 
 * Version: 1.0.0
 * Date: October 24, 2025
 */

export class FastFonts {
  constructor() {
    this.fontsLoaded = false;
    this.fontFamilies = ['Inter'];
    this.systemFontStack = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';
  }

  /**
   * Инициализация оптимальной загрузки шрифтов
   */
  async init() {
    // Проверяем поддержку Font Loading API
    if (!('fonts' in document)) {
      console.log('[FastFonts] Font Loading API not supported, using fallback');
      this.fallbackFontLoading();
      return;
    }

    try {
      // Используем system fonts сразу
      this.useSystemFonts();

      // Загружаем web fonts асинхронно с низким приоритетом
      await this.loadWebFonts();

      this.fontsLoaded = true;
      document.documentElement.classList.add('fonts-loaded');
      
      console.log('[FastFonts] Web fonts loaded successfully');
    } catch (error) {
      console.warn('[FastFonts] Web fonts failed to load, using system fonts', error);
      // System fonts уже применены, ничего не делаем
    }
  }

  /**
   * Применить system fonts немедленно
   */
  useSystemFonts() {
    document.documentElement.style.setProperty('--font-family-base', this.systemFontStack);
    document.documentElement.classList.add('system-fonts');
  }

  /**
   * Асинхронная загрузка web fonts
   */
  async loadWebFonts() {
    // Проверяем connection quality
    const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    const slowConnection = connection && (
      connection.effectiveType === 'slow-2g' ||
      connection.effectiveType === '2g' ||
      connection.saveData
    );

    // На медленном соединении пропускаем web fonts
    if (slowConnection) {
      console.log('[FastFonts] Slow connection detected, skipping web fonts');
      return;
    }

    // Загружаем только критичные weights
    const fontWeights = [400, 600]; // Regular, SemiBold
    const fontPromises = [];

    for (const weight of fontWeights) {
      const fontFace = new FontFace(
        'Inter',
        `url(https://fonts.gstatic.com/s/inter/v13/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuLyfAZ9hiA.woff2) format('woff2')`,
        {
          weight: weight.toString(),
          style: 'normal',
          display: 'optional' // Критично для performance!
        }
      );

      fontPromises.push(
        fontFace.load().then(loaded => {
          document.fonts.add(loaded);
          return loaded;
        })
      );
    }

    // Ждем загрузки всех шрифтов (с timeout)
    await Promise.race([
      Promise.all(fontPromises),
      new Promise(resolve => setTimeout(resolve, 3000)) // 3s timeout
    ]);

    // Применяем web fonts
    document.documentElement.style.setProperty('--font-family-base', `'Inter', ${this.systemFontStack}`);
    document.documentElement.classList.remove('system-fonts');
  }

  /**
   * Fallback для браузеров без Font Loading API
   */
  fallbackFontLoading() {
    // Просто используем CSS font-display: optional
    // Браузер сам решит когда применить шрифт
    const link = document.createElement('link');
    link.href = 'https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=optional';
    link.rel = 'stylesheet';
    document.head.appendChild(link);
  }

  /**
   * Preload критичных шрифтов (должен быть вызван в <head>)
   */
  static preloadFonts() {
    const preloads = [
      {
        url: 'https://fonts.gstatic.com/s/inter/v13/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuLyfAZ9hiA.woff2',
        type: 'font/woff2',
        crossorigin: 'anonymous'
      }
    ];

    preloads.forEach(font => {
      const link = document.createElement('link');
      link.rel = 'preload';
      link.as = 'font';
      link.type = font.type;
      link.href = font.url;
      link.crossOrigin = font.crossorigin;
      document.head.appendChild(link);
    });
  }

  /**
   * Check если шрифты уже загружены (например, из cache)
   */
  static async checkFontsReady() {
    if (!('fonts' in document)) {
      return false;
    }

    try {
      await document.fonts.ready;
      const inter = document.fonts.check('1em Inter');
      return inter;
    } catch (error) {
      return false;
    }
  }
}

/**
 * Auto-init при import
 */
export async function initFastFonts() {
  const fastFonts = new FastFonts();
  await fastFonts.init();
  return fastFonts;
}

/**
 * Early font optimization (вызывается в <head>)
 */
export function earlyFontOptimization() {
  // Apply system fonts immediately
  const systemFonts = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';
  document.documentElement.style.setProperty('--font-family-base', systemFonts);
  
  // Preload критичные шрифты
  if (
    !navigator.connection ||
    (navigator.connection.effectiveType !== 'slow-2g' && 
     navigator.connection.effectiveType !== '2g' &&
     !navigator.connection.saveData)
  ) {
    FastFonts.preloadFonts();
  }
}

export default FastFonts;

