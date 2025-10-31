/**
 * Lightweight orchestrator for third-party analytics.
 * Loads GA4, Microsoft Clarity and Meta Pixel after initial rendering
 * to minimise impact on FCP/TTI.
 */
(function (win, doc) {
  'use strict';

  if (!doc || !doc.documentElement) {
    return;
  }

  var root = doc.documentElement;
  var GA_ID = root.getAttribute('data-ga-id');
  var CLARITY_ID = root.getAttribute('data-clarity-id');
  var PIXEL_ID = root.getAttribute('data-meta-pixel-id');
  var YM_ID = root.getAttribute('data-ym-id');

  function schedule(fn, timeout) {
    if (!fn) {
      return;
    }
    if ('requestIdleCallback' in win) {
      win.requestIdleCallback(fn, { timeout: timeout || 2000 });
      return;
    }
    var invoked = false;
    function run() {
      if (invoked) {
        return;
      }
      invoked = true;
      fn();
    }
    if (doc.readyState === 'complete') {
      setTimeout(run, timeout || 0);
    } else {
      win.addEventListener('load', run, { once: true });
      setTimeout(run, timeout || 2000);
    }
  }

  // Event buffer to queue events before pixel loads
  win._fbqBuffer = win._fbqBuffer || [];
  win._fbqLoaded = false;

  function setupGlobalEventBridge() {
    if (typeof win.trackEvent === 'function') {
      return;
    }
    win.YM_ID = YM_ID ? parseInt(YM_ID, 10) || 0 : 0;
    win.trackEvent = function (eventName, payload) {
      if (!eventName) {
        return;
      }
      payload = payload || {};
      
      // Meta Pixel standard e-commerce events that support value/currency
      var ecommerceEvents = [
        'ViewContent', 'AddToCart', 'InitiateCheckout', 'Purchase',
        'AddPaymentInfo', 'AddToWishlist', 'Lead', 'CompleteRegistration',
        'Subscribe', 'StartTrial'
      ];
      var isEcommerceEvent = ecommerceEvents.indexOf(eventName) !== -1;
      
      // Validate and sanitize payload for Meta Pixel
      var fbPayload = {};
      for (var key in payload) {
        if (payload.hasOwnProperty(key)) {
          var value = payload[key];
          // Skip undefined/null values
          if (value === undefined || value === null) {
            continue;
          }
          // Only include value/currency for e-commerce events
          if (key === 'value' || key === 'currency') {
            if (!isEcommerceEvent) {
              continue; // Skip these params for non-ecommerce events
            }
          }
          // Validate numeric values
          if (key === 'value') {
            var numValue = parseFloat(value);
            if (!isNaN(numValue) && numValue >= 0) {
              fbPayload[key] = numValue;
            }
          }
          // Validate currency
          else if (key === 'currency') {
            if (typeof value === 'string' && value.length > 0) {
              fbPayload[key] = value.toUpperCase();
            }
          }
          // Copy other values as-is
          else {
            fbPayload[key] = value;
          }
        }
      }
      
      // Buffer Meta Pixel events until loaded
      // Защита от блокировки: проверяем что Pixel действительно доступен
      try {
        if (PIXEL_ID && win.fbq && typeof win.fbq === 'function') {
          // Проверяем что Pixel инициализирован
          if (win._fbqLoaded) {
            try {
          win.fbq('track', eventName, fbPayload);
            } catch (fbErr) {
              if (console && console.debug) {
                console.debug('Meta Pixel track error (possible blocker):', fbErr);
              }
              // Fallback: буферизуем событие на случай если это временная ошибка
              if (win._fbqBuffer) {
                win._fbqBuffer.push({ event: eventName, data: fbPayload });
              }
            }
        } else if (PIXEL_ID) {
            // Pixel еще не загружен - буферизуем
            if (!win._fbqBuffer) {
              win._fbqBuffer = [];
            }
          win._fbqBuffer.push({ event: eventName, data: fbPayload });
          }
        }
      } catch (err1) {
        if (console && console.debug) {
          console.debug('Meta Pixel track error (possible blocker):', err1);
        }
      }
      
      // Отправка в Google Analytics через dataLayer (работает с GTM и GA4)
      try {
        // ИСПРАВЛЕНИЕ: Используем существующий dataLayer от GTM
        win.dataLayer = win.dataLayer || [];
        
        // Если есть gtag - используем его (GA4 direct)
        if (win.gtag && typeof win.gtag === 'function') {
          win.gtag('event', eventName, payload);
        } else {
          // Fallback: отправляем напрямую в dataLayer (GTM подхватит)
          win.dataLayer.push({
            'event': eventName,
            'eventParameters': payload
          });
        }
      } catch (err2) {
        if (console && console.debug) {
          console.debug('GA/GTM track error (possible blocker):', err2);
        }
      }
      // Отправка в Yandex Metrika (если подключена)
      try {
        if (win.ym && typeof win.ym === 'function' && win.YM_ID) {
          win.ym(win.YM_ID, 'reachGoal', eventName, payload);
        }
      } catch (err3) {
        if (console && console.debug) {
          console.debug('YM track error (possible blocker):', err3);
        }
      }
    };
  }

  function loadGoogleAnalytics() {
    if (!GA_ID || win.__gaLoaded) {
      return;
    }
    
    // ИСПРАВЛЕНИЕ: Используем существующий dataLayer от GTM (не создаем новый)
    // GTM уже создает dataLayer в base.html, используем его
    win.dataLayer = win.dataLayer || [];
    
    // Создаем gtag функцию если её еще нет (GTM может её не создать)
    if (!win.gtag) {
      win.gtag = function () {
        win.dataLayer.push(arguments);
      };
    }

    // Защита от блокировки: проверяем что скрипт действительно загрузился
    var script = doc.createElement('script');
    script.async = true;
    script.src = 'https://www.googletagmanager.com/gtag/js?id=' + GA_ID;
    script.dataset.loader = 'ga4';
    
    var loadTimeout = setTimeout(function() {
      if (!win.__gaLoaded) {
        console.debug('GA4 script load timeout - possible ad blocker');
      }
    }, 5000);
    
    script.onload = function () {
      clearTimeout(loadTimeout);
      // Проверяем что gtag действительно работает
      try {
      win.__gaLoaded = true;
      win.gtag('js', new Date());
      win.gtag('config', GA_ID, {
        send_page_view: false,
      });
      win.gtag('event', 'page_view', {
        page_title: doc.title,
        page_location: win.location.href,
      });
      } catch (err) {
        if (console && console.debug) {
          console.debug('GA4 initialization error (possible blocker):', err);
        }
      }
    };
    
    script.onerror = function() {
      clearTimeout(loadTimeout);
      if (console && console.debug) {
        console.debug('GA4 script failed to load - possible ad blocker');
      }
    };
    
    try {
    doc.head.appendChild(script);
    } catch (err) {
      if (console && console.debug) {
        console.debug('Failed to append GA4 script:', err);
      }
    }
  }

  function loadClarity() {
    if (!CLARITY_ID || win.__clarityLoaded) {
      return;
    }
    
    // Защита от блокировки: инициализируем Clarity с проверками
    try {
    win.__clarityLoaded = true;
    (function (c, l, a, r, i, t, y) {
      c[a] =
        c[a] ||
        function () {
          (c[a].q = c[a].q || []).push(arguments);
        };
      t = l.createElement(r);
      t.async = true;
      t.src = 'https://www.clarity.ms/tag/' + i;
        
        // Защита от блокировки: обработчик ошибок
        t.onerror = function() {
          if (console && console.debug) {
            console.debug('Clarity script failed to load - possible ad blocker');
          }
          c.__clarityLoaded = false;
        };
        
      y = l.getElementsByTagName(r)[0];
        if (y && y.parentNode) {
      y.parentNode.insertBefore(t, y);
        } else {
          // Fallback: добавляем в head
          (l.head || l.getElementsByTagName('head')[0]).appendChild(t);
        }
    })(win, doc, 'clarity', 'script', CLARITY_ID);
    } catch (err) {
      if (console && console.debug) {
        console.debug('Clarity initialization error:', err);
      }
      win.__clarityLoaded = false;
    }
  }

  function buildAdvancedMatchingMap() {
    var amEl = doc.getElementById('am');
    if (!amEl) {
      return {};
    }
    var attrs = amEl.dataset || {};
    var match = {};
    var fullName = (attrs.fn || '').trim();
    if (fullName) {
      var parts = fullName.split(/\s+/);
      if (parts.length > 1) {
        match.fn = parts[0];
        match.ln = parts.slice(1).join(' ');
      } else {
        match.fn = fullName;
      }
    }
    if (attrs.externalId) {
      match.external_id = attrs.externalId;
    }
    if (attrs.em) {
      match.em = attrs.em;
    }
    if (attrs.ph) {
      match.ph = attrs.ph;
    }
    if (attrs.ct) {
      match.ct = attrs.ct;
    }
    return match;
  }

  function loadMetaPixel() {
    if (!PIXEL_ID || (win.fbq && win.__fbPixelLoaded)) {
      return;
    }
    
    // Защита от блокировки: инициализируем Pixel с проверками
    try {
    !function (f, b, e, v, n, t, s) {
      if (f.fbq) {
        return;
      }
      n = f.fbq = function () {
        n.callMethod ? n.callMethod.apply(n, arguments) : n.queue.push(arguments);
      };
      if (!f._fbq) {
        f._fbq = n;
      }
      n.push = n;
      n.loaded = true;
      n.version = '2.0';
      n.queue = [];
      t = b.createElement(e);
      t.async = true;
      t.src = v;
        
        // Защита от блокировки: добавляем onerror обработчик
        t.onerror = function() {
          if (console && console.debug) {
            console.debug('Meta Pixel script failed to load - possible ad blocker');
          }
          // Помечаем что Pixel не загружен, но продолжаем работу
          f._fbqLoaded = false;
        };
        
      s = b.getElementsByTagName(e)[0];
        if (s && s.parentNode) {
      s.parentNode.insertBefore(t, s);
        } else {
          // Fallback: добавляем в head если script[0] не найден
          (b.head || b.getElementsByTagName('head')[0]).appendChild(t);
        }
    }(win, doc, 'script', 'https://connect.facebook.net/en_US/fbevents.js');
      
    win.__fbPixelLoaded = true;
    } catch (err) {
      if (console && console.debug) {
        console.debug('Meta Pixel initialization error:', err);
      }
      win.__fbPixelLoaded = false;
    }
    try {
      var advancedMatching = buildAdvancedMatchingMap();
      win.fbq('init', PIXEL_ID, advancedMatching);
    } catch (err) {
      if (console && console.debug) {
        console.debug('Meta Pixel init error', err);
      }
      try {
        win.fbq('init', PIXEL_ID);
      } catch (err2) {
        if (console && console.debug) {
          console.debug('Meta Pixel fallback error', err2);
        }
      }
    }
    try {
      win.fbq('track', 'PageView');
    } catch (errTrack) {
      if (console && console.debug) {
        console.debug('Meta Pixel track error', errTrack);
      }
    }
    
    // Mark pixel as loaded and process buffered events
    win._fbqLoaded = true;
    if (win._fbqBuffer && win._fbqBuffer.length > 0) {
      if (console && console.log) {
        console.log('Meta Pixel: Processing ' + win._fbqBuffer.length + ' buffered events');
      }
      win._fbqBuffer.forEach(function(buffered) {
        try {
          win.fbq('track', buffered.event, buffered.data);
        } catch (err) {
          if (console && console.debug) {
            console.debug('Meta Pixel buffered event error', err);
          }
        }
      });
      win._fbqBuffer = []; // Clear buffer
    }
  }

  setupGlobalEventBridge();
  schedule(loadGoogleAnalytics, 2000);
  schedule(loadClarity, 3000);
  schedule(loadMetaPixel, 500);  // Reduced from 2500ms to 500ms for faster event capture
})(window, document);
