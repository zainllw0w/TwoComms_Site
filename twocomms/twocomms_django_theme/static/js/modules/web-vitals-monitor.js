// twocomms/twocomms_django_theme/static/js/modules/web-vitals-monitor.js

/**
 * Core Web Vitals Monitoring Module
 * Отслеживает LCP, FID, CLS, FCP, TTFB в реальном времени
 * Отправляет метрики в Google Analytics и собственную аналитику
 */

class WebVitalsMonitor {
  constructor() {
    this.metrics = {};
    this.reported = new Set();
    this.init();
  }

  init() {
    if (!window.performance || !window.PerformanceObserver) {
      console.warn('[WebVitals] Performance API not supported');
      return;
    }

    this.observeLCP();
    this.observeFID();
    this.observeCLS();
    this.observeFCP();
    this.measureTTFB();
    this.observeINP(); // Interaction to Next Paint (новая метрика)
    
    console.log('[WebVitals] Monitoring initialized');
    
    // Отправляем метрики перед уходом со страницы
    this.setupBeforeUnload();
  }

  /**
   * Largest Contentful Paint (LCP)
   * Цель: < 2.5s
   */
  observeLCP() {
    try {
      const observer = new PerformanceObserver((entryList) => {
        const entries = entryList.getEntries();
        const lastEntry = entries[entries.length - 1];
        
        this.metrics.lcp = {
          value: lastEntry.renderTime || lastEntry.loadTime,
          element: lastEntry.element?.tagName || 'unknown',
          url: lastEntry.url || '',
          timestamp: Date.now()
        };
        
        this.reportMetric('LCP', this.metrics.lcp.value);
      });
      
      observer.observe({ type: 'largest-contentful-paint', buffered: true });
    } catch (e) {
      console.error('[WebVitals] LCP observer error:', e);
    }
  }

  /**
   * First Input Delay (FID)
   * Цель: < 100ms
   */
  observeFID() {
    try {
      const observer = new PerformanceObserver((entryList) => {
        const firstInput = entryList.getEntries()[0];
        
        this.metrics.fid = {
          value: firstInput.processingStart - firstInput.startTime,
          name: firstInput.name,
          timestamp: Date.now()
        };
        
        this.reportMetric('FID', this.metrics.fid.value);
      });
      
      observer.observe({ type: 'first-input', buffered: true });
    } catch (e) {
      console.error('[WebVitals] FID observer error:', e);
    }
  }

  /**
   * Cumulative Layout Shift (CLS)
   * Цель: < 0.1
   */
  observeCLS() {
    try {
      let clsValue = 0;
      let sessionValue = 0;
      let sessionEntries = [];
      
      const observer = new PerformanceObserver((entryList) => {
        for (const entry of entryList.getEntries()) {
          // Только неожиданные сдвиги (не по действию пользователя)
          if (!entry.hadRecentInput) {
            const firstSessionEntry = sessionEntries[0];
            const lastSessionEntry = sessionEntries[sessionEntries.length - 1];
            
            // Новая сессия если >1s или >5s от последнего сдвига
            if (sessionValue &&
                entry.startTime - lastSessionEntry.startTime < 1000 &&
                entry.startTime - firstSessionEntry.startTime < 5000) {
              sessionValue += entry.value;
              sessionEntries.push(entry);
            } else {
              sessionValue = entry.value;
              sessionEntries = [entry];
            }
            
            // Обновляем максимальное значение
            if (sessionValue > clsValue) {
              clsValue = sessionValue;
              
              this.metrics.cls = {
                value: clsValue,
                entries: sessionEntries.length,
                timestamp: Date.now()
              };
            }
          }
        }
      });
      
      observer.observe({ type: 'layout-shift', buffered: true });
      
      // Отчет при уходе со страницы
      addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'hidden') {
          this.reportMetric('CLS', clsValue);
        }
      }, { once: true });
    } catch (e) {
      console.error('[WebVitals] CLS observer error:', e);
    }
  }

  /**
   * First Contentful Paint (FCP)
   * Цель: < 1.8s
   */
  observeFCP() {
    try {
      const observer = new PerformanceObserver((entryList) => {
        const entries = entryList.getEntries();
        const fcpEntry = entries.find(entry => entry.name === 'first-contentful-paint');
        
        if (fcpEntry) {
          this.metrics.fcp = {
            value: fcpEntry.startTime,
            timestamp: Date.now()
          };
          
          this.reportMetric('FCP', this.metrics.fcp.value);
        }
      });
      
      observer.observe({ type: 'paint', buffered: true });
    } catch (e) {
      console.error('[WebVitals] FCP observer error:', e);
    }
  }

  /**
   * Time to First Byte (TTFB)
   * Цель: < 600ms
   */
  measureTTFB() {
    try {
      const navEntry = performance.getEntriesByType('navigation')[0];
      
      if (navEntry) {
        this.metrics.ttfb = {
          value: navEntry.responseStart - navEntry.requestStart,
          timestamp: Date.now()
        };
        
        this.reportMetric('TTFB', this.metrics.ttfb.value);
      }
    } catch (e) {
      console.error('[WebVitals] TTFB measurement error:', e);
    }
  }

  /**
   * Interaction to Next Paint (INP)
   * Новая метрика от Google, заменяет FID
   * Цель: < 200ms
   */
  observeINP() {
    try {
      let maxDuration = 0;
      
      const observer = new PerformanceObserver((entryList) => {
        for (const entry of entryList.getEntries()) {
          if (entry.interactionId) {
            const duration = entry.processingEnd - entry.processingStart;
            
            if (duration > maxDuration) {
              maxDuration = duration;
              
              this.metrics.inp = {
                value: duration,
                name: entry.name,
                timestamp: Date.now()
              };
            }
          }
        }
      });
      
      observer.observe({ type: 'event', buffered: true, durationThreshold: 16 });
      
      // Отчет при уходе со страницы
      addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'hidden' && maxDuration > 0) {
          this.reportMetric('INP', maxDuration);
        }
      }, { once: true });
    } catch (e) {
      // INP может быть не поддерживаться в старых браузерах
      console.warn('[WebVitals] INP observer not supported');
    }
  }

  /**
   * Отправка метрики
   */
  reportMetric(name, value) {
    if (this.reported.has(name)) return;
    
    const rating = this.getRating(name, value);
    
    console.log(`[WebVitals] ${name}: ${value.toFixed(2)}ms (${rating})`);
    
    // Отправка в Google Analytics 4
    if (window.gtag) {
      gtag('event', 'web_vitals', {
        event_category: 'Web Vitals',
        event_label: name,
        value: Math.round(value),
        rating: rating,
        non_interaction: true
      });
    }
    
    // Отправка в собственный endpoint (если есть)
    this.sendToAnalytics(name, value, rating);
    
    this.reported.add(name);
  }

  /**
   * Определение оценки метрики (good/needs-improvement/poor)
   */
  getRating(name, value) {
    const thresholds = {
      'LCP': [2500, 4000],
      'FID': [100, 300],
      'CLS': [0.1, 0.25],
      'FCP': [1800, 3000],
      'TTFB': [600, 1500],
      'INP': [200, 500]
    };
    
    const [good, poor] = thresholds[name] || [0, Infinity];
    
    if (value <= good) return 'good';
    if (value <= poor) return 'needs-improvement';
    return 'poor';
  }

  /**
   * Отправка в собственную аналитику
   */
  sendToAnalytics(name, value, rating) {
    const endpoint = '/api/web-vitals/'; // Можно настроить через Django view
    
    const data = {
      metric: name,
      value: Math.round(value * 100) / 100,
      rating: rating,
      url: window.location.pathname,
      timestamp: new Date().toISOString(),
      connection: this.getConnectionInfo(),
      device: this.getDeviceInfo()
    };
    
    // Используем sendBeacon для надежной отправки
    if (navigator.sendBeacon) {
      const blob = new Blob([JSON.stringify(data)], { type: 'application/json' });
      navigator.sendBeacon(endpoint, blob);
    } else {
      // Fallback для старых браузеров
      fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
        keepalive: true
      }).catch(err => console.error('[WebVitals] Failed to send:', err));
    }
  }

  /**
   * Получение информации о соединении
   */
  getConnectionInfo() {
    const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    
    if (!conn) return null;
    
    return {
      effectiveType: conn.effectiveType,
      downlink: conn.downlink,
      rtt: conn.rtt,
      saveData: conn.saveData
    };
  }

  /**
   * Получение информации об устройстве
   */
  getDeviceInfo() {
    return {
      isMobile: /iPhone|iPad|iPod|Android/i.test(navigator.userAgent),
      deviceMemory: navigator.deviceMemory || null,
      hardwareConcurrency: navigator.hardwareConcurrency || null,
      screenWidth: window.screen.width,
      screenHeight: window.screen.height,
      viewportWidth: window.innerWidth,
      viewportHeight: window.innerHeight
    };
  }

  /**
   * Настройка отправки метрик перед уходом
   */
  setupBeforeUnload() {
    addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') {
        this.sendAllMetrics();
      }
    });
  }

  /**
   * Отправка всех собранных метрик
   */
  sendAllMetrics() {
    Object.entries(this.metrics).forEach(([name, data]) => {
      if (!this.reported.has(name.toUpperCase())) {
        this.reportMetric(name.toUpperCase(), data.value);
      }
    });
  }

  /**
   * Получение всех метрик (для debugging)
   */
  getMetrics() {
    return this.metrics;
  }
}

// Автоматическая инициализация
let webVitalsMonitor = null;

if (document.readyState === 'complete') {
  webVitalsMonitor = new WebVitalsMonitor();
} else {
  window.addEventListener('load', () => {
    webVitalsMonitor = new WebVitalsMonitor();
  });
}

export default WebVitalsMonitor;
export { webVitalsMonitor };

