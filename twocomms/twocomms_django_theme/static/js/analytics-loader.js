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
  var TIKTOK_PIXEL_ID = root.getAttribute('data-tiktok-pixel-id');
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
  win._ttqBuffer = win._ttqBuffer || [];
  win._ttqLoaded = false;

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
      
      // Отправка в TikTok Pixel
      try {
        if (TIKTOK_PIXEL_ID && win.ttq && typeof win.ttq.track === 'function') {
          if (win._ttqLoaded) {
            try {
              // TikTok Pixel поддерживает стандартные e-commerce события
              var ttqPayload = {};
              if (isEcommerceEvent) {
                if (payload.value !== undefined) {
                  ttqPayload.value = parseFloat(payload.value) || 0;
                }
                if (payload.currency) {
                  ttqPayload.currency = payload.currency.toUpperCase();
                }
              }
              // Копируем другие параметры
              for (var ttqKey in payload) {
                if (payload.hasOwnProperty(ttqKey) && ttqKey !== 'value' && ttqKey !== 'currency') {
                  ttqPayload[ttqKey] = payload[ttqKey];
                }
              }
              win.ttq.track(eventName, ttqPayload);
            } catch (ttqErr) {
              if (console && console.debug) {
                console.debug('TikTok Pixel track error (possible blocker):', ttqErr);
              }
              if (win._ttqBuffer) {
                win._ttqBuffer.push({ event: eventName, data: ttqPayload });
              }
            }
          } else if (TIKTOK_PIXEL_ID) {
            // TikTok Pixel еще не загружен - буферизуем
            var ttqBufferedPayload = {};
            if (isEcommerceEvent) {
              if (payload.value !== undefined) {
                ttqBufferedPayload.value = parseFloat(payload.value) || 0;
              }
              if (payload.currency) {
                ttqBufferedPayload.currency = payload.currency.toUpperCase();
              }
            }
            for (var ttqBuffKey in payload) {
              if (payload.hasOwnProperty(ttqBuffKey) && ttqBuffKey !== 'value' && ttqBuffKey !== 'currency') {
                ttqBufferedPayload[ttqBuffKey] = payload[ttqBuffKey];
              }
            }
            if (!win._ttqBuffer) {
              win._ttqBuffer = [];
            }
            win._ttqBuffer.push({ event: eventName, data: ttqBufferedPayload });
          }
        }
      } catch (err4) {
        if (console && console.debug) {
          console.debug('TikTok Pixel track error (possible blocker):', err4);
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

  function loadTikTokPixel() {
    if (!TIKTOK_PIXEL_ID || (win.ttq && win.__ttqPixelLoaded)) {
      return;
    }
    
    // Защита от блокировки: инициализируем TikTok Pixel с проверками
    try {
      !function (w, d, t) {
        if (w[t]) {
          return;
        }
        w.TiktokAnalyticsObject = t;
        var ttq = w[t] = w[t] || [];
        ttq.methods = ["page","track","identify","instances","debug","on","off","once","ready","alias","group","enableCookie","disableCookie","holdConsent","revokeConsent","grantConsent"];
        ttq.setAndDefer = function(t,e){t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}};
        for(var i=0;i<ttq.methods.length;i++)ttq.setAndDefer(ttq,ttq.methods[i]);
        ttq.instance = function(t){
          var e=ttq._i[t]||[],n=0;
          for(n=0;n<ttq.methods.length;n++)ttq.setAndDefer(e,ttq.methods[n]);
          return e
        };
        ttq.load = function(e,n){
          var r="https://analytics.tiktok.com/i18n/pixel/events.js",o=n&&n.partner;
          ttq._i=ttq._i||{};
          ttq._i[e]=[];
          ttq._i[e]._u=r;
          ttq._t=ttq._t||{};
          ttq._t[e]=+new Date;
          ttq._o=ttq._o||{};
          ttq._o[e]=n||{};
          n=doc.createElement("script");
          n.type="text/javascript";
          n.async=!0;
          n.src=r+"?sdkid="+e+"&lib="+t;
          
          // Защита от блокировки: обработчик ошибок
          n.onerror = function() {
            if (console && console.debug) {
              console.debug('TikTok Pixel script failed to load - possible ad blocker');
            }
            w.__ttqPixelLoaded = false;
          };
          
          e=doc.getElementsByTagName("script")[0];
          if (e && e.parentNode) {
            e.parentNode.insertBefore(n,e);
          } else {
            // Fallback: добавляем в head
            (doc.head || doc.getElementsByTagName("head")[0]).appendChild(n);
          }
        };
      }(win, doc, 'ttq');
      
      win.__ttqPixelLoaded = true;
    } catch (err) {
      if (console && console.debug) {
        console.debug('TikTok Pixel initialization error:', err);
      }
      win.__ttqPixelLoaded = false;
      return;
    }
    
    try {
      win.ttq.load(TIKTOK_PIXEL_ID);
    } catch (err) {
      if (console && console.debug) {
        console.debug('TikTok Pixel load error', err);
      }
      win.__ttqPixelLoaded = false;
      return;
    }
    
    try {
      win.ttq.page();
    } catch (errTrack) {
      if (console && console.debug) {
        console.debug('TikTok Pixel page error', errTrack);
      }
    }
    
    // Mark pixel as loaded and process buffered events
    win._ttqLoaded = true;
    if (win._ttqBuffer && win._ttqBuffer.length > 0) {
      if (console && console.log) {
        console.log('TikTok Pixel: Processing ' + win._ttqBuffer.length + ' buffered events');
      }
      win._ttqBuffer.forEach(function(buffered) {
        try {
          win.ttq.track(buffered.event, buffered.data);
        } catch (err) {
          if (console && console.debug) {
            console.debug('TikTok Pixel buffered event error', err);
          }
        }
      });
      win._ttqBuffer = []; // Clear buffer
    }
  }

  setupGlobalEventBridge();
  schedule(loadGoogleAnalytics, 2000);
  schedule(loadClarity, 3000);
  schedule(loadMetaPixel, 500);  // Reduced from 2500ms to 500ms for faster event capture
  schedule(loadTikTokPixel, 600);  // Загружаем TikTok Pixel через 600ms после Meta Pixel
})(window, document);
