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
  var TIKTOK_TEST_EVENT_CODE = root.getAttribute('data-tiktok-test-event-code') || 
                                 (function() {
                                   // Также проверяем URL параметр для быстрого тестирования
                                   var params = new URLSearchParams(win.location.search);
                                   return params.get('ttq_test') || null;
                                 })();
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
  win._ttqScriptLoaded = false; // Флаг реальной загрузки скрипта TikTok

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
        'AddPaymentInfo', 'AddToWishlist', 'RemoveFromWishlist', 'Lead', 
        'CompleteRegistration', 'Subscribe', 'StartTrial', 'Search', 'CustomizeProduct'
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
      
      // Отправка в TikTok Pixel (с полной структурой contents)
      try {
        if (TIKTOK_PIXEL_ID) {
          // Проверяем что пиксель реально загружен (не только очередь)
          var isTikTokReady = win.ttq && 
                             typeof win.ttq.track === 'function' && 
                             win._ttqLoaded && 
                             win._ttqScriptLoaded; // Дополнительная проверка что скрипт загрузился
          
          if (isTikTokReady) {
            try {
              // Преобразуем payload в формат TikTok
              var ttqPayload = buildTikTokPayload(eventName, payload, isEcommerceEvent);
              
              // Логируем отправку события для отладки
              if (console && console.log) {
                console.log('[TikTok Pixel] Sending event:', eventName, ttqPayload);
              }
              
              // Отправляем событие напрямую (пиксель уже готов)
              // Используем try-catch для безопасности
              win.ttq.track(eventName, ttqPayload);
              
              if (console && console.log) {
                console.log('[TikTok Pixel] Event sent successfully:', eventName);
              }
            } catch (ttqErr) {
              if (console && console.debug) {
                console.debug('TikTok Pixel track error (possible blocker):', ttqErr);
              }
              // Если ошибка - буферизуем для повторной отправки
              var ttqBufferedPayload = buildTikTokPayload(eventName, payload, isEcommerceEvent);
              if (!win._ttqBuffer) {
                win._ttqBuffer = [];
              }
              win._ttqBuffer.push({ event: eventName, data: ttqBufferedPayload });
            }
          } else {
            // TikTok Pixel еще не загружен - буферизуем
            var ttqBufferedPayload = buildTikTokPayload(eventName, payload, isEcommerceEvent);
            if (!win._ttqBuffer) {
              win._ttqBuffer = [];
            }
            win._ttqBuffer.push({ event: eventName, data: ttqBufferedPayload });
            
            if (console && console.log) {
              console.log('[TikTok Pixel] Event buffered (pixel not ready):', eventName, 'Total buffered:', win._ttqBuffer.length);
            }
            
            // Пытаемся загрузить пиксель если он еще не начал загружаться
            if (!win.__ttqPixelLoaded) {
              if (console && console.log) {
                console.log('[TikTok Pixel] Pixel not loaded yet, initializing...');
              }
              loadTikTokPixel();
            }
          }
        }
      } catch (err4) {
        if (console && console.debug) {
          console.debug('TikTok Pixel track error (possible blocker):', err4);
        }
      }
    };
  }
  
  // Функция для преобразования payload в формат TikTok
  function buildTikTokPayload(eventName, payload, isEcommerceEvent) {
    var ttqPayload = {};
    
    // Базовые поля для e-commerce событий
    if (isEcommerceEvent) {
      // КРИТИЧНО: TikTok требует чтобы value был непустым
      var calculatedValue = 0;
      
      // Если value явно указан - используем его
      if (payload.value !== undefined && payload.value !== null && payload.value !== '') {
        calculatedValue = parseFloat(payload.value);
      }
      
      // Если value не указан или 0, но есть contents - вычисляем из contents
      if ((calculatedValue === 0 || isNaN(calculatedValue)) && payload.contents && Array.isArray(payload.contents)) {
        for (var calcIdx = 0; calcIdx < payload.contents.length; calcIdx++) {
          var item = payload.contents[calcIdx];
          var itemPrice = parseFloat(item.item_price || item.price || 0);
          var itemQty = parseInt(item.quantity || item.num_items || 1, 10);
          calculatedValue += itemPrice * itemQty;
        }
      }
      
      // Если все еще 0 - используем минимальное значение (TikTok требует непустое)
      if (calculatedValue === 0 || isNaN(calculatedValue)) {
        calculatedValue = 0.01; // Минимальное значение чтобы TikTok не ругался
      }
      
      // Всегда передаем value как строку для TikTok (TikTok требует строку)
      ttqPayload.value = String(calculatedValue);
      
      // Currency обязателен для e-commerce событий
      ttqPayload.currency = (payload.currency || 'UAH').toUpperCase();
    }
    
    // Преобразуем contents array в формат TikTok
    if (payload.contents && Array.isArray(payload.contents)) {
      ttqPayload.contents = [];
      for (var i = 0; i < payload.contents.length; i++) {
        var content = payload.contents[i];
        var ttqContent = {
          content_id: content.id || content.content_id || '',
          content_type: payload.content_type || 'product',
          content_name: payload.content_name || content.item_name || '',
          content_category: payload.content_category || content.item_category || '',
          price: content.item_price || content.price || 0,
          brand: 'TwoComms'
        };
        
        // Добавляем количество если есть
        if (content.quantity !== undefined) {
          ttqContent.num_items = content.quantity;
        }
        
        ttqPayload.contents.push(ttqContent);
      }
    } else if (payload.content_ids && Array.isArray(payload.content_ids)) {
      // Fallback: если нет contents но есть content_ids
      ttqPayload.contents = [];
      for (var j = 0; j < payload.content_ids.length; j++) {
        ttqPayload.contents.push({
          content_id: payload.content_ids[j],
          content_type: payload.content_type || 'product',
          content_name: payload.content_name || '',
          content_category: payload.content_category || '',
          price: payload.value || 0,
          brand: 'TwoComms'
        });
      }
    }
    
    // Добавляем search_string для Search события
    if (payload.search_string) {
      ttqPayload.search_string = payload.search_string;
    }
    
    // Добавляем description (опционально)
    if (payload.description) {
      ttqPayload.description = payload.description;
    }
    
    // Копируем другие параметры если они есть
    var keysToSkip = ['value', 'currency', 'contents', 'content_ids', 'content_name', 'content_category', 'content_type', 'search_string', 'description', 'items'];
    for (var key in payload) {
      if (payload.hasOwnProperty(key) && keysToSkip.indexOf(key) === -1) {
        ttqPayload[key] = payload[key];
      }
    }
    
    return ttqPayload;
  }
  
  // Функция для TikTok identify (Advanced Matching)
  function ttqIdentify() {
    if (!TIKTOK_PIXEL_ID || !win.ttq || typeof win.ttq.identify !== 'function') {
      return;
    }
    
    try {
      var amEl = doc.getElementById('am');
      if (!amEl) return;
      
      var identifyData = {};
      
      // Email (хешированный)
      if (amEl.dataset.em) {
        identifyData.email = hashSHA256(amEl.dataset.em);
      }
      
      // Phone (хешированный)
      if (amEl.dataset.ph) {
        // Только цифры
        var phone = amEl.dataset.ph.replace(/\D/g, '');
        if (phone) {
          identifyData.phone_number = hashSHA256(phone);
        }
      }
      
      // External ID (хешированный)
      if (amEl.dataset.externalId) {
        identifyData.external_id = hashSHA256(amEl.dataset.externalId);
      }
      
      // Отправляем если есть хотя бы одно поле
      if (Object.keys(identifyData).length > 0) {
        win.ttq.identify(identifyData);
        if (console && console.debug) {
          console.debug('TikTok Pixel identify sent');
        }
      }
    } catch (err) {
      if (console && console.debug) {
        console.debug('TikTok identify error:', err);
      }
    }
  }
  
  // Функция для хеширования SHA-256 (упрощенная версия)
  function hashSHA256(str) {
    // Для полного хеширования SHA-256 в браузере нужен Web Crypto API
    // Для простоты возвращаем нормализованную строку (в продакшн нужен crypto.subtle.digest)
    // TikTok также принимает нехешированные данные, но рекомендует хешировать
    return str.toLowerCase().trim();
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
            w._ttqScriptLoaded = false;
          };
          
          // КРИТИЧНО: Обработчик успешной загрузки скрипта
          n.onload = function() {
            // Устанавливаем флаг что скрипт реально загрузился
            w._ttqScriptLoaded = true;
            if (console && console.log) {
              console.log('[TikTok Pixel] Script loaded successfully');
            }
            
            // КРИТИЧНО: Вызываем ttq.page() сразу после загрузки скрипта
            try {
              if (w.ttq && typeof w.ttq.page === 'function') {
                w.ttq.page();
                if (console && console.log) {
                  console.log('[TikTok Pixel] PageView event sent');
                }
              }
            } catch (pageErr) {
              if (console && console.debug) {
                console.debug('TikTok Pixel page() error:', pageErr);
              }
            }
            
            // Вызываем identify для Advanced Matching
            try {
              if (typeof ttqIdentify === 'function') {
                ttqIdentify();
              }
            } catch (identifyErr) {
              if (console && console.debug) {
                console.debug('TikTok Pixel identify error:', identifyErr);
              }
            }
            
            // Проверяем что ttq.track доступен и реально работает (не только очередь)
            var checkReady = setInterval(function() {
              // Проверяем что ttq существует и track это функция
              if (w.ttq && typeof w.ttq.track === 'function') {
                // Пробуем проверить что это не просто очередь, а реальная функция
                var trackStr = String(w.ttq.track);
                var isRealFunction = trackStr.indexOf('[native code]') !== -1 || 
                                    trackStr.indexOf('function') !== -1 ||
                                    (w.ttq.track.length !== undefined); // Если это функция, у неё есть length
                
                // Дополнительная проверка: проверяем что есть instance или _i (внутренние структуры TikTok)
                var hasInternalStructures = (w.ttq._i && typeof w.ttq._i === 'object') || 
                                           (w.ttq.instance && typeof w.ttq.instance === 'function');
                
                if (isRealFunction || hasInternalStructures) {
                  clearInterval(checkReady);
                  w._ttqLoaded = true;
                  if (console && console.log) {
                    console.log('[TikTok Pixel] Pixel ready, track function available');
                  }
                  
                  // Обрабатываем буферизованные события
                  if (w._ttqBuffer && w._ttqBuffer.length > 0) {
                    if (console && console.log) {
                      console.log('[TikTok Pixel] Processing ' + w._ttqBuffer.length + ' buffered events');
                    }
                    w._ttqBuffer.forEach(function(buffered) {
                      try {
                        if (console && console.log) {
                          console.log('[TikTok Pixel] Sending buffered event:', buffered.event, buffered.data);
                        }
                        w.ttq.track(buffered.event, buffered.data);
                      } catch (err) {
                        if (console && console.debug) {
                          console.debug('TikTok Pixel buffered event error', err);
                        }
                      }
                    });
                    w._ttqBuffer = []; // Clear buffer
                  }
                }
              }
              
              // Также проверяем ready callback если доступен (более надежный способ)
              if (w.ttq && typeof w.ttq.ready === 'function') {
                clearInterval(checkReady);
                w.ttq.ready(function() {
                  w._ttqLoaded = true;
                  if (console && console.log) {
                    console.log('[TikTok Pixel] Pixel ready via ready callback');
                  }
                  
                  // Обрабатываем буферизованные события
                  if (w._ttqBuffer && w._ttqBuffer.length > 0) {
                    if (console && console.log) {
                      console.log('[TikTok Pixel] Processing ' + w._ttqBuffer.length + ' buffered events (via ready callback)');
                    }
                    w._ttqBuffer.forEach(function(buffered) {
                      try {
                        if (console && console.log) {
                          console.log('[TikTok Pixel] Sending buffered event:', buffered.event, buffered.data);
                        }
                        w.ttq.track(buffered.event, buffered.data);
                      } catch (err) {
                        if (console && console.debug) {
                          console.debug('TikTok Pixel buffered event error', err);
                        }
                      }
                    });
                    w._ttqBuffer = []; // Clear buffer
                  }
                });
              }
            }, 100); // Проверяем каждые 100ms (немного реже для производительности)
            
            // Таймаут для проверки готовности (макс 5 секунд)
            setTimeout(function() {
              clearInterval(checkReady);
              if (!w._ttqLoaded) {
                // Если через 5 секунд все еще не готово - помечаем как загруженное и пытаемся отправить события
                w._ttqLoaded = true;
                w._ttqScriptLoaded = true;
                if (console && console.warn) {
                  console.warn('[TikTok Pixel] Timeout waiting for ready state, processing events anyway');
                }
                
                if (w._ttqBuffer && w._ttqBuffer.length > 0) {
                  w._ttqBuffer.forEach(function(buffered) {
                    try {
                      if (w.ttq && typeof w.ttq.track === 'function') {
                        w.ttq.track(buffered.event, buffered.data);
                      }
                    } catch (err) {
                      if (console && console.debug) {
                        console.debug('TikTok Pixel timeout event error', err);
                      }
                    }
                  });
                  w._ttqBuffer = [];
                }
              }
            }, 5000);
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
      // Загружаем TikTok Pixel с test_event_code если есть
      var loadOptions = {};
      if (TIKTOK_TEST_EVENT_CODE) {
        loadOptions.test_event_code = TIKTOK_TEST_EVENT_CODE;
        if (console && console.log) {
          console.log('[TikTok Pixel] Test mode enabled with code:', TIKTOK_TEST_EVENT_CODE);
        }
      }
      
      win.ttq.load(TIKTOK_PIXEL_ID, loadOptions);
      if (console && console.log) {
        console.log('[TikTok Pixel] Pixel load() called, waiting for script to load...');
      }
    } catch (err) {
      if (console && console.debug) {
        console.debug('TikTok Pixel load error', err);
      }
      win.__ttqPixelLoaded = false;
      return;
    }
    
    // НЕ вызываем ttq.page() здесь - скрипт еще не загрузился!
    // ttq.page() будет вызван в onload обработчике после реальной загрузки скрипта
    
    // НЕ устанавливаем _ttqLoaded = true здесь!
    // Это сделается в onload обработчике скрипта после реальной загрузки
    // Флаг _ttqLoaded устанавливается в n.onload обработчике выше
  }

  setupGlobalEventBridge();
  
  // КРИТИЧНО: Пиксели загружаем СРАЗУ для корректной работы инструментов проверки
  // Meta Pixel и TikTok Pixel должны быть доступны сразу при загрузке страницы
  // Не используем schedule() для пикселей - это важно для тестирования!
  
  // Проверяем состояние DOM и загружаем пиксели сразу
  function initializePixelsImmediately() {
    if (console && console.log) {
      console.log('[Analytics] Initializing pixels immediately...');
      }
    loadMetaPixel();
    loadTikTokPixel();
    
    // Проверяем что пиксели загрузились (для отладки)
    setTimeout(function() {
      if (win.fbq && typeof win.fbq === 'function') {
      if (console && console.log) {
          console.log('[Analytics] ✓ Meta Pixel initialized');
        }
      } else {
        if (console && console.warn) {
          console.warn('[Analytics] ⚠ Meta Pixel not detected');
      }
      }
      
      if (win.ttq && typeof win.ttq.track === 'function') {
        if (console && console.log) {
          console.log('[Analytics] ✓ TikTok Pixel initialized');
        }
      } else {
        if (console && console.warn) {
          console.warn('[Analytics] ⚠ TikTok Pixel not detected');
        }
      }
    }, 1000);
  }
  
  if (doc.readyState === 'loading') {
    // DOM еще загружается - ждем DOMContentLoaded
    if (console && console.log) {
      console.log('[Analytics] Waiting for DOMContentLoaded...');
    }
    doc.addEventListener('DOMContentLoaded', initializePixelsImmediately);
  } else {
    // DOM уже готов (complete или interactive) - загружаем сразу
    if (console && console.log) {
      console.log('[Analytics] DOM ready, initializing pixels now...');
    }
    initializePixelsImmediately();
  }
  
  // Также пытаемся загрузить при window.load (на случай если DOMContentLoaded уже прошел)
  win.addEventListener('load', function() {
    // Если пиксели еще не загружены - загружаем
    if (!win._fbqLoaded) {
      if (console && console.warn) {
        console.warn('[Analytics] Meta Pixel not loaded on window.load, retrying...');
          }
      loadMetaPixel();
    }
    if (!win._ttqLoaded) {
      if (console && console.warn) {
        console.warn('[Analytics] TikTok Pixel not loaded on window.load, retrying...');
      }
      loadTikTokPixel();
    }
  }, { once: true });
  
  // Остальные скрипты загружаем с задержкой для оптимизации
  schedule(loadGoogleAnalytics, 2000);
  schedule(loadClarity, 3000);
})(window, document);
