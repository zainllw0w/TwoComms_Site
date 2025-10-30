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
      
      // Validate and sanitize payload for Meta Pixel
      var fbPayload = {};
      for (var key in payload) {
        if (payload.hasOwnProperty(key)) {
          var value = payload[key];
          // Skip undefined/null values
          if (value === undefined || value === null) {
            continue;
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
      try {
        if (win.fbq && win._fbqLoaded) {
          win.fbq('track', eventName, fbPayload);
        } else if (PIXEL_ID) {
          // Queue event for later
          win._fbqBuffer.push({ event: eventName, data: fbPayload });
        }
      } catch (err1) {
        if (console && console.debug) {
          console.debug('Meta Pixel track error', err1);
        }
      }
      
      try {
        if (win.gtag) {
          win.gtag('event', eventName, payload);
        }
      } catch (err2) {
        if (console && console.debug) {
          console.debug('GA track error', err2);
        }
      }
      try {
        if (win.ym && win.YM_ID) {
          win.ym(win.YM_ID, 'reachGoal', eventName, payload);
        }
      } catch (err3) {
        if (console && console.debug) {
          console.debug('YM track error', err3);
        }
      }
    };
  }

  function loadGoogleAnalytics() {
    if (!GA_ID || win.__gaLoaded) {
      return;
    }
    win.dataLayer = win.dataLayer || [];
    win.gtag =
      win.gtag ||
      function () {
        win.dataLayer.push(arguments);
      };

    var script = doc.createElement('script');
    script.async = true;
    script.src = 'https://www.googletagmanager.com/gtag/js?id=' + GA_ID;
    script.dataset.loader = 'ga4';
    script.onload = function () {
      win.__gaLoaded = true;
      win.gtag('js', new Date());
      win.gtag('config', GA_ID, {
        send_page_view: false,
      });
      win.gtag('event', 'page_view', {
        page_title: doc.title,
        page_location: win.location.href,
      });
    };
    doc.head.appendChild(script);
  }

  function loadClarity() {
    if (!CLARITY_ID || win.__clarityLoaded) {
      return;
    }
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
      y = l.getElementsByTagName(r)[0];
      y.parentNode.insertBefore(t, y);
    })(win, doc, 'clarity', 'script', CLARITY_ID);
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
      s = b.getElementsByTagName(e)[0];
      s.parentNode.insertBefore(t, s);
    }(win, doc, 'script', 'https://connect.facebook.net/en_US/fbevents.js');
    win.__fbPixelLoaded = true;
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
