import {
  DOMCache,
  debounce,
  scheduleIdle,
  prefersReducedMotion,
  PERF_LITE,
  nextEvt,
  nowTs,
  getCookie,
  escapeHtml
} from './modules/shared.js';
import { PerformanceOptimizer, ImageOptimizer, MobileOptimizer } from './modules/optimizers.js';
import { initProductMedia } from './modules/product-media.js';
import { initWebPush } from './modules/web-push.js';

// Помечаем, что основной JS инициализирован и можно запускать анимации
document.documentElement.classList.add('js-ready');
initWebPush();

const ANALYTICS_BRAND_NAME = 'TwoComms';

function getAnalyticsTrackingContext() {
  if (typeof window.getTrackingContext === 'function') {
    try {
      return window.getTrackingContext() || {};
    } catch (err) {
      if (console && console.debug) {
        console.debug('getTrackingContext error:', err);
      }
    }
  }
  return { fbp: null, fbc: null };
}

function safeGenerateAnalyticsEventId() {
  if (typeof window.generateEventId === 'function') {
    try {
      return window.generateEventId();
    } catch (err) {
      if (console && console.debug) {
        console.debug('generateEventId error:', err);
      }
    }
  }
  return Date.now() + '_' + Math.random().toString(36).substring(2, 11);
}

const GUEST_STORAGE_PREFIX = '_twc_guest_';
const GUEST_STORAGE_FIELDS = ['full_name', 'phone', 'city', 'np_office', 'email'];

function readGuestStorageValue(name) {
  if (!name) {
    return '';
  }
  try {
    if (typeof window.sessionStorage !== 'undefined') {
      return window.sessionStorage.getItem(GUEST_STORAGE_PREFIX + name) || '';
    }
  } catch (_) { }
  return '';
}

function writeGuestStorageValue(name, value) {
  if (!name) {
    return;
  }
  try {
    if (typeof window.sessionStorage === 'undefined') {
      return;
    }
    const key = GUEST_STORAGE_PREFIX + name;
    if (value) {
      window.sessionStorage.setItem(key, value);
    } else {
      window.sessionStorage.removeItem(key);
    }
  } catch (_) { }
}

function attachGuestFormPersistence() {
  const form = document.getElementById('guest-form');
  if (!form) {
    return;
  }
  GUEST_STORAGE_FIELDS.forEach((fieldName) => {
    const input = form.querySelector(`[name="${fieldName}"]`);
    if (!input) {
      return;
    }
    const storedValue = readGuestStorageValue(fieldName);
    if (storedValue && !input.value) {
      input.value = storedValue;
    }
    const handler = () => {
      writeGuestStorageValue(fieldName, (input.value || '').trim());
    };
    input.addEventListener('input', handler);
    input.addEventListener('change', handler);
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    try { attachGuestFormPersistence(); } catch (_) { }
  });
} else {
  try { attachGuestFormPersistence(); } catch (_) { }
}

function buildMetaWithUserData(eventId, baseMeta) {
  const meta = Object.assign({}, baseMeta || {});
  if (eventId) {
    meta.event_id = eventId;
  }
  if (typeof window.buildUserDataForEvent !== 'function') {
    return meta;
  }
  try {
    const context = window.buildUserDataForEvent();
    if (!context || typeof context !== 'object') {
      return meta;
    }
    if (context.user_data && Object.keys(context.user_data).length) {
      meta.user_data = context.user_data;
    }
    if (context.external_id) {
      meta.external_id = context.external_id;
    }
    if (context.fbp) {
      meta.fbp = context.fbp;
    }
    if (context.fbc) {
      meta.fbc = context.fbc;
    }
  } catch (err) {
    if (console && console.debug) {
      console.debug('buildUserDataForEvent error:', err);
    }
  }
  return meta;
}

function pushDataLayerEvent(config) {
  if (!config || !config.eventName || !config.eventId || !config.ecommerce || !config.eventModel) {
    return null;
  }
  window.dataLayer = window.dataLayer || [];
  const ctx = getAnalyticsTrackingContext();
  if (!config.eventModel.event_id) {
    config.eventModel.event_id = config.eventId;
  }
  const payload = {
    event: config.eventName,
    event_id: config.eventId,
    fbp: ctx.fbp || null,
    fbc: ctx.fbc || null,
    ecommerce: config.ecommerce,
    eventModel: config.eventModel
  };
  if (config.userData && typeof config.userData === 'object' && Object.keys(config.userData).length) {
    payload.user_data = config.userData;
  }
  if (config.extraFields && typeof config.extraFields === 'object') {
    Object.keys(config.extraFields).forEach(key => {
      const value = config.extraFields[key];
      if (value !== undefined && value !== null) {
        payload[key] = value;
      }
    });
  }
  window.dataLayer.push(payload);
  return payload;
}

function mapContentsToGaItems(items, currency) {
  return (items || []).map(item => {
    const id = item.id || item.offer_id || item.item_id || '';
    if (!id) {
      return null;
    }
    const qty = Number(item.quantity || item.qty || 1) || 1;
    const price = Number(item.price || item.item_price || item.unit_price || 0) || 0;
    return {
      item_id: String(id),
      item_name: item.item_name || item.name || item.product_title || '',
      item_brand: ANALYTICS_BRAND_NAME,
      item_category: item.item_category || item.product_category || '',
      item_variant: (item.variant || item.size || item.item_variant || '').toString().toUpperCase(),
      price: price,
      quantity: qty,
      currency: currency || item.currency || 'UAH'
    };
  }).filter(Boolean);
}

function mapGaItemsToEventItems(items) {
  return (items || []).map(item => ({
    id: item.item_id,
    name: item.item_name,
    price: item.price,
    quantity: item.quantity
  }));
}

function fetchCartAnalyticsSnapshot() {
  return fetch('/cart/items/', {
    headers: { 'X-Requested-With': 'XMLHttpRequest' },
    cache: 'no-store'
  }).then(response => {
    if (!response.ok) {
      throw new Error('cart snapshot failed');
    }
    return response.json();
  });
}

function pushAddToCartEvent(params) {
  const eventId = params.eventId || safeGenerateAnalyticsEventId();
  const currency = params.currency || 'UAH';
  const value = Number(params.value || params.itemPrice * params.quantity || 0) || 0;
  const baseItem = {
    item_id: params.offerId,
    item_name: params.contentName || '',
    item_brand: ANALYTICS_BRAND_NAME,
    item_category: params.contentCategory || '',
    item_variant: (params.variant || '').toString().toUpperCase(),
    price: Number(params.itemPrice || 0) || 0,
    quantity: Number(params.quantity || 1) || 1,
    currency: currency
  };

  const pushSnapshot = snapshot => {
    const snapshotItems = snapshot && Array.isArray(snapshot.items) ? snapshot.items : [];
    const ecommProdid = snapshotItems
      .map(item => item.offer_id || item.id)
      .filter(Boolean);
    const totalValue = Number(snapshot && snapshot.total) || value;

    pushDataLayerEvent({
      eventName: 'add_to_cart',
      eventId: eventId,
      ecommerce: {
        currency: currency,
        value: value,
        items: [baseItem]
      },
      eventModel: {
        event_id: eventId,
        value: value,
        currency: currency,
        content_name: baseItem.item_name,
        items: [{
          id: baseItem.item_id,
          name: baseItem.item_name,
          price: baseItem.price,
          quantity: baseItem.quantity
        }],
        ecomm_prodid: ecommProdid.length ? ecommProdid : [baseItem.item_id],
        ecomm_pagetype: 'cart',
        ecomm_totalvalue: totalValue
      }
    });
  };

  fetchCartAnalyticsSnapshot()
    .then(pushSnapshot)
    .catch(() => pushSnapshot(null));

  return eventId;
}

function pushBeginCheckoutEvent(analytics, options) {
  if (!analytics) {
    return null;
  }
  const eventId = (options && options.eventId) || safeGenerateAnalyticsEventId();
  const currency = analytics.currency || 'UAH';
  let gaItems = mapContentsToGaItems(analytics.contents || [], currency);
  if (!gaItems.length && Array.isArray(analytics.content_ids)) {
    gaItems = analytics.content_ids.map(id => ({
      item_id: String(id),
      item_name: '',
      item_brand: ANALYTICS_BRAND_NAME,
      item_category: '',
      item_variant: '',
      price: 0,
      quantity: 1,
      currency: currency
    }));
  }
  const ecommProdid = Array.isArray(analytics.content_ids) && analytics.content_ids.length
    ? analytics.content_ids
    : gaItems.map(item => item.item_id);

  pushDataLayerEvent({
    eventName: 'begin_checkout',
    eventId: eventId,
    ecommerce: {
      currency: currency,
      value: analytics.value || 0,
      items: gaItems
    },
    eventModel: {
      event_id: eventId,
      value: analytics.value || 0,
      currency: currency,
      event_category: 'Оформлення замовлення',
      event_label: (options && options.eventLabel) || 'TwoComms',
      items: mapGaItemsToEventItems(gaItems),
      ecomm_prodid: ecommProdid,
      ecomm_pagetype: 'cart',
      ecomm_totalvalue: analytics.value || 0
    }
  });
  return eventId;
}

window.__twcAnalytics = window.__twcAnalytics || {};
Object.assign(window.__twcAnalytics, {
  brand: ANALYTICS_BRAND_NAME,
  safeGenerateEventId: safeGenerateAnalyticsEventId,
  getTrackingContext: getAnalyticsTrackingContext,
  pushDataLayerEvent: pushDataLayerEvent,
  mapContentsToGaItems: mapContentsToGaItems,
  mapGaItemsToEventItems: mapGaItemsToEventItems,
  fetchCartAnalyticsSnapshot: fetchCartAnalyticsSnapshot,
  pushAddToCartEvent: pushAddToCartEvent,
  pushBeginCheckoutEvent: pushBeginCheckoutEvent
});

// ===== ОПТИМИЗАЦИЯ ПРОИЗВОДИТЕЛЬНОСТИ =====
// Анимации появления
// Оптимизированные настройки IntersectionObserver
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
  // Инициализация оптимизации изображений переносится в idle, чтобы не блокировать главный поток
  scheduleIdle(() => {
    ImageOptimizer.init();
    MobileOptimizer.initMobileOptimizations();
  });

  const registerRevealTargets = (scope = document) => {
    const basicTargets = scope.querySelectorAll('.reveal, .reveal-fast');
    if (!supportsIO) {
      basicTargets.forEach(el => el.classList.add('visible'));
      return;
    }
    basicTargets.forEach(el => io.observe(el));
  };
  registerRevealTargets();

  // Стаггер-анимация карточек в гриде — по порядку DOM, без измерений
  const gridObserver = supportsIO ? new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      const grid = entry.target;
      const ordered = Array.from(grid.querySelectorAll('.stagger-item'));

      // Мягкий каскад без дёрганий: шаг зависит от числа карточек,
      // отключается при reduced motion/перф-лайт
      const count = ordered.length || 1;
      const step = (prefersReducedMotion || PERF_LITE)
        ? 0
        : Math.max(50, Math.min(110, Math.floor(900 / count)));
      try { if (window.equalizeCardHeights) window.equalizeCardHeights(); } catch (_) { }
      ordered.forEach((el, i) => {
        el.style.setProperty('--d', (i * step) + 'ms'); // дублируем задержку в CSS (на всякий)
        const revealCard = () => {
          el.classList.add('visible');

          // Анимация цветов товаров - СТРОГО вместе с карточкой
          const colorDots = el.closest('.product-card-wrap').querySelector('.product-card-dots');
          if (colorDots) {
            // Цвета появляются одновременно с карточкой
            colorDots.classList.add('visible');
            // Анимация отдельных цветовых точек
            const dots = colorDots.querySelectorAll('.color-dot');
            dots.forEach((dot, dotIndex) => {
              setTimeout(() => {
                dot.classList.add('visible');
              }, prefersReducedMotion ? 0 : (dotIndex * 60)); // Быстрая анимация точек
            });
          }
        };
        if (step === 0) {
          revealCard();
        } else {
          setTimeout(revealCard, i * step);
        }
      });

      gridObserver.unobserve(grid);
    });
  }, { threshold: .12, rootMargin: '0px 0px -10% 0px' }) : null;
  const grids = document.querySelectorAll('[data-stagger-grid]');
  if (!supportsIO) {
    grids.forEach(grid => {
      grid.querySelectorAll('.stagger-item').forEach(el => el.classList.add('visible'));
    });
  } else {
    grids.forEach(grid => gridObserver.observe(grid));
  }

  requestAnimationFrame(() => {
    document.documentElement.classList.add('reveal-ready');
    if (!supportsIO || prefersReducedMotion) {
      document.querySelectorAll('.reveal, .reveal-fast, .reveal-stagger, .stagger-item').forEach(el => el.classList.add('visible'));
    }
  });

  // Экспортируем функцию для динамически подгруженных карточек (load more)
  window.registerRevealTargets = registerRevealTargets;
});

// ===== Force hide cart/profile on mobile: handled by CSS (base.html media query
// + Bootstrap d-none d-lg-block on header). JS removed 2026-04-20 — было dead-code:
// toggled class .mobile-hidden, у которого нет CSS-правил; видимость уже
// обеспечивается media query. =====

// ===== Корзина (AJAX) =====

const panelState = () => ({
  userShown: !(DOMCache.get('user-panel') || { classList: { contains: () => true } }).classList.contains('d-none'),
  userMobileShown: !(DOMCache.get('user-panel-mobile') || { classList: { contains: () => true } }).classList.contains('d-none'),
  cartShown: !(miniCartPanel() || { classList: { contains: () => true } }).classList.contains('d-none')
});
function updateCartBadge(count) {
  const normalizedCount = Number.isFinite(Number(count)) ? Number(count) : 0;
  setCartSyncEnabled(normalizedCount > 0);
  const n = String(count || 0);
  const desktop = DOMCache.get('cart-count');
  const mobile = DOMCache.get('cart-count-mobile');

  requestAnimationFrame(() => {
    if (desktop) {
      desktop.textContent = n;
      desktop.classList.add('visible');
    }
    if (mobile) {
      mobile.textContent = n;
      mobile.classList.add('visible');
    }
  });
}
window.updateCartBadge = updateCartBadge;

const CART_SYNC_HINT_KEY = 'twc-sync-cart';
const FAVORITES_SYNC_HINT_KEY = 'twc-sync-favs';

function persistSyncHint(key, enabled) {
  try {
    if (!window.localStorage) return;
    if (enabled) {
      window.localStorage.setItem(key, '1');
    } else {
      window.localStorage.removeItem(key);
    }
  } catch (_) { }
}

function setCartSyncEnabled(enabled) {
  const normalized = !!enabled;
  window.__TC_SYNC_CART = normalized;
  persistSyncHint(CART_SYNC_HINT_KEY, normalized);
}
window.setCartSyncEnabled = setCartSyncEnabled;

function setFavoritesSyncEnabled(enabled) {
  const normalized = !!enabled;
  window.__TC_SYNC_FAVS = normalized;
  persistSyncHint(FAVORITES_SYNC_HINT_KEY, normalized);
}
window.setFavoritesSyncEnabled = setFavoritesSyncEnabled;

function refreshCartSummary() {
  return fetch('/cart/summary/', {
    headers: { 'X-Requested-With': 'XMLHttpRequest' },
    cache: 'no-store'
  })
    .then(r => r.ok ? r.json() : null)
    .then(d => { if (d && d.ok && typeof d.count === 'number') { updateCartBadge(d.count); } })
    .catch(() => { });
}
window.refreshCartSummary = refreshCartSummary;

// Функция для обновления счетчика избранного
function updateFavoritesBadge(count) {
  const normalizedCount = Number.isFinite(Number(count)) ? Number(count) : 0;
  setFavoritesSyncEnabled(normalizedCount > 0);
  const n = String(count || 0);
  const desktop = DOMCache.get('favorites-count');
  const mobile = DOMCache.get('favorites-count-mobile');
  const mini = DOMCache.get('favorites-count-mini');
  const favoritesWrapper = DOMCache.query('.favorites-icon-wrapper');
  const mobileIcon = DOMCache.query('a[href*="favorites"] .bottom-nav-icon');

  // Используем requestAnimationFrame для избежания принудительной компоновки
  requestAnimationFrame(() => {
    // Обновляем десктопный счетчик
    if (desktop) {
      desktop.textContent = n;
      desktop.classList.add('visible');

      if (count > 0) {
        // Добавляем класс для анимации когда есть товары
        if (favoritesWrapper) {
          favoritesWrapper.classList.add('has-items');
        }
      } else {
        // Убираем класс когда нет товаров
        if (favoritesWrapper) {
          favoritesWrapper.classList.remove('has-items');
        }
      }
    }

    // Обновляем мобильный счетчик
    if (mobile) {
      mobile.textContent = n;

      if (count > 0) {
        mobile.classList.add('visible');
        if (mobileIcon) {
          mobileIcon.classList.add('has-items');
        }
      } else {
        mobile.classList.remove('visible');
        if (mobileIcon) {
          mobileIcon.classList.remove('has-items');
        }
      }
    }

    // Обновляем счетчик в минипрофиле
    if (mini) {
      mini.textContent = n;

      if (count > 0) {
        mini.classList.add('visible');
      } else {
        mini.classList.remove('visible');
      }
    }
  });
}

// Применение цветов свотчей (включая комбинированные) по data-* атрибутам
function applySwatchColors(root) {
  try {
    const scope = root || document;
    const list = scope.querySelectorAll('.cart-item-swatch, .swatch, .order-item-swatch, .color-dot, .featured-color-dot');
    list.forEach(function (el) {
      const primary = el.getAttribute('data-primary') || '';
      const secondary = el.getAttribute('data-secondary') || '';

      // Используем requestAnimationFrame для избежания принудительной компоновки
      requestAnimationFrame(() => {
        // Устанавливаем CSS-переменные для комбинированных цветов
        if (primary) el.style.setProperty('--primary-color', primary);
        if (secondary && secondary !== 'None') {
          el.style.setProperty('--secondary-color', secondary);
        } else {
          el.style.removeProperty('--secondary-color');
        }

        // Устанавливаем прямой background-color для .swatch элементов
        if (el.classList.contains('swatch') && primary) {
          el.style.backgroundColor = primary;
        }
      });
    });
  } catch (_) { }
}

// Мини‑корзина с кэшированием
function miniCartPanel() {
  if (window.innerWidth < 576) {
    return DOMCache.get('mini-cart-panel-mobile');
  } else {
    return DOMCache.get('mini-cart-panel');
  }
}
// Небольшая защита от мгновенного закрытия при переключении панелей
let uiGuardUntil = 0;
let suppressGlobalCloseUntil = 0;
let suppressNextDocPointerdownUntil = 0; // блокируем ближайший pointerdown от документа (клик по тогглеру)
function showAnimatedPanel(panel) {
  if (!panel) return;
  panel.classList.remove('hiding');
  panel.classList.remove('d-none');
  panel.removeAttribute('inert');
  panel.setAttribute('aria-hidden', 'false');
  const commitOpen = () => {
    panel.classList.add('show');
  };
  if ('requestAnimationFrame' in window) {
    requestAnimationFrame(() => {
      requestAnimationFrame(commitOpen);
    });
  } else {
    setTimeout(commitOpen, 0);
  }
}
function openMiniCart(opts = {}) {
  const { skipRefresh = false } = opts;
  const id = nextEvt();
  const panel = miniCartPanel(); if (!panel) return;
  // Оп‑токен: любое новое действие отменяет старые таймауты/слушатели
  panel._opId = (panel._opId || 0) + 1; const opId = panel._opId;
  if (panel._hideTimeout) { clearTimeout(panel._hideTimeout); panel._hideTimeout = null; }
  panel.classList.remove('hiding');
  // Закрываем открытый мини‑профиль (desktop/mobile), если он был открыт
  [DOMCache.get('user-panel'), DOMCache.get('user-panel-mobile')]
    .forEach(up => { if (up && !up.classList.contains('d-none')) { up.classList.remove('show'); setTimeout(() => up.classList.add('d-none'), 200); } });
  panel.classList.remove('d-none', 'hiding');
  // Мобильный полноэкранный режим
  if (window.innerWidth < 576) {
    panel.classList.add('position-fixed', 'top-0', 'start-0', 'vw-100', 'vh-100', 'rounded-0');
    panel.style.right = '';
    panel.style.top = '0';
  } else {
    panel.classList.remove('position-fixed', 'top-0', 'start-0', 'vw-100', 'vh-100', 'rounded-0');
    panel.style.right = '0';
    panel.style.top = 'calc(100% + 8px)';
  }
  const markOpened = () => {
    panel.classList.add('show');
    uiGuardUntil = Date.now() + 220;
    suppressGlobalCloseUntil = Date.now() + 180;
  };
  if ('requestAnimationFrame' in window) {
    requestAnimationFrame(markOpened);
  } else {
    markOpened();
  }
  if (!skipRefresh) refreshMiniCart();
}
function closeMiniCart(reason) {
  const id = nextEvt();
  const panel = miniCartPanel(); if (!panel) return;
  panel._opId = (panel._opId || 0) + 1; const opId = panel._opId;
  panel.classList.remove('show');
  panel.classList.add('hiding');
  const hideAfter = setTimeout(() => {
    if (opId !== panel._opId) return; // Уже было другое действие
    panel.classList.add('d-none');
    panel.classList.remove('hiding');
  }, 260);
  panel._hideTimeout = hideAfter;
  // если есть transitionend — ускорим скрытие
  panel.addEventListener('transitionend', function onTrEnd(e) {
    if (e.target !== panel) return;
    panel.removeEventListener('transitionend', onTrEnd);
    if (opId !== panel._opId) return; // Не актуально
    clearTimeout(hideAfter);
    panel.classList.add('d-none');
    panel.classList.remove('hiding');
  });
}
function toggleMiniCart() {
  const panel = miniCartPanel(); if (!panel) return;
  if (panel.classList.contains('d-none') || !panel.classList.contains('show')) openMiniCart(); else closeMiniCart();
}

// Mono/Monobank checkout — extracted to modules/checkout-mono.js (Phase 2.1).
// The module is loaded lazily on first detection of a mono/monobank trigger.
window.__twcMono = {
  readGuestStorageValue: readGuestStorageValue,
  buildMetaWithUserData: buildMetaWithUserData,
  safeGenerateAnalyticsEventId: safeGenerateAnalyticsEventId,
};
let __monoModulePromise = null;
function __loadMonoModule() {
  if (!__monoModulePromise) {
    __monoModulePromise = import('./modules/checkout-mono.js?v=20260422').catch((err) => {
      __monoModulePromise = null;
      throw err;
    });
  }
  return __monoModulePromise;
}
function bindMonoCheckout(scope) {
  const root = scope || document;
  if (!root || typeof root.querySelector !== 'function') return;
  if (!root.querySelector('[data-mono-checkout-trigger]')) return;
  __loadMonoModule().then((m) => { try { m.bindMonoCheckout(root); } catch (_) {} }).catch(() => {});
}
function bindMonobankPay(scope) {
  const root = scope || document;
  if (!root || typeof root.querySelector !== 'function') return;
  if (!root.querySelector('[data-monobank-pay-trigger]')) return;
  __loadMonoModule().then((m) => { try { m.bindMonobankPay(root); } catch (_) {} }).catch(() => {});
}


let miniCartFetchController = null;
let miniCartFetchSeq = 0;

function refreshMiniCart() {
  const panel = miniCartPanel(); if (!panel) return Promise.resolve();
  const content = panel.querySelector('#mini-cart-content') || panel.querySelector('#mini-cart-content-mobile') || panel;
  content.innerHTML = "<div class='text-secondary small'>Завантаження…</div>";

  if (typeof AbortController !== 'undefined') {
    if (miniCartFetchController) {
      try { miniCartFetchController.abort(); } catch (_) { }
    }
    miniCartFetchController = new AbortController();
  } else {
    miniCartFetchController = null;
  }

  const currentSeq = ++miniCartFetchSeq;
  const controller = miniCartFetchController;

  return fetch('/cart/mini/', {
    headers: { 'X-Requested-With': 'XMLHttpRequest' },
    cache: 'no-store',
    signal: controller ? controller.signal : undefined
  })
    .then(r => r.text())
    .then(html => {
      if (currentSeq !== miniCartFetchSeq) return;
      content.innerHTML = html;
      try { applySwatchColors(content); } catch (_) { }
      try { bindMonoCheckout(content); } catch (_) { }
    })
    .catch(err => {
      if (controller && err && err.name === 'AbortError') return;
      if (currentSeq !== miniCartFetchSeq) return;
      content.innerHTML = "<div class='text-danger small'>Не вдалося завантажити кошик</div>";
    })
    .finally(() => {
      if (controller && miniCartFetchController === controller) {
        miniCartFetchController = null;
      }
    });
}
window.refreshMiniCart = refreshMiniCart;
window.openMiniCart = openMiniCart;

// Обновляем сводку при загрузке - DEFERRED до после LCP
document.addEventListener('DOMContentLoaded', () => {
  try { bindMonoCheckout(document); } catch (_) { }
  try { bindMonobankPay(document); } catch (_) { }
  const docEl = document.documentElement;
  const routeName = (docEl.dataset.routeName || '').toLowerCase();
  const deviceClass = (docEl.dataset.deviceClass || '').toLowerCase();
  const pageShell = (docEl.dataset.pageShell || '').toLowerCase();
  const isMarketingShell = pageShell === 'marketing';
  const cartBootEvents = routeName === 'home'
    ? ['click', 'pointerdown', 'keydown']
    : (isMarketingShell
      ? ['click', 'pointerdown', 'keydown']
      : ['scroll', 'click', 'touchstart', 'pointerdown', 'keydown']);
  const cartBootDelay = routeName === 'home'
    ? (deviceClass === 'low' ? 3500 : 2500)
    : (isMarketingShell
      ? (deviceClass === 'low' ? 6500 : 4500)
      : 2000);
  
  // PERF: Delay cart/favorites requests until AFTER LCP (1.5s) or user interaction
  // This is critical for mobile PageSpeed TBT score
  const loadCartData = () => {
    // Guard against multiple calls
    if (window.__cartDataLoaded) return;
    window.__cartDataLoaded = true;
    
    // Remove interaction listeners
    cartBootEvents.forEach(evt => {
      window.removeEventListener(evt, loadCartData, { passive: true, capture: true });
    });
    
    scheduleIdle(() => {
      // SSR-маркер: если cart пуст на сервере, не дёргаем /cart/summary/
      if (window.__TC_SYNC_CART !== false) {
        refreshCartSummary();
      }
      if (window.__TC_SYNC_FAVS !== false) {
        fetch('/favorites/count/', { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
          .then(r => r.ok ? r.json() : null)
          .then(d => {
            if (d && d.count !== undefined) {
              updateFavoritesBadge(d.count);
            }
          })
          .catch(() => { });
      }
    });
  };
  
  // Load on user interaction (more aggressive for PageSpeed)
  cartBootEvents.forEach(evt => {
    window.addEventListener(evt, loadCartData, { passive: true, capture: true, once: true });
  });
  
  // Fallback: home gets a longer quiet window to keep LCP clean on weaker devices.
  setTimeout(loadCartData, cartBootDelay);

  // Применим цвета для свотчей на текущей странице
  scheduleIdle(function () { try { applySwatchColors(document); } catch (_) { } });

  // Перемещаем галерею товара в левую колонку и синхронизируем миниатюры
  scheduleIdle(function () {
    const galleryBlock = document.querySelector('.product-gallery-block');
    const carouselEl = document.getElementById('productCarousel');
    if (!(galleryBlock && carouselEl)) return;

    // Функция: есть ли у элемента класс вида col-*
    const hasColClass = (el) => {
      if (!el || !el.classList) return false;
      return Array.from(el.classList).some(c => c.startsWith('col-'));
    };

    // 1) Найдём ближайшую к галерее колонку Bootstrap и её левую "соседнюю" колонку
    let currentCol = galleryBlock.closest('*');
    while (currentCol && !hasColClass(currentCol)) currentCol = currentCol.parentElement;

    let leftCol = null;
    if (currentCol && currentCol.parentElement) {
      // Ищем предыдущий элемент-колонку в пределах той же строки
      let prev = currentCol.previousElementSibling;
      while (prev && !hasColClass(prev)) prev = prev.previousElementSibling;
      if (prev && hasColClass(prev)) leftCol = prev;
    }

    // Если нашли левую колонку — вставим туда галерею и удалим старое изображение
    if (leftCol) {
      const oldImgWrap = leftCol.querySelector('.ratio, img');
      // Вставим галерею в начало левой колонки
      leftCol.insertBefore(galleryBlock, leftCol.firstChild);
      if (oldImgWrap) oldImgWrap.remove();
      // Удалим возможные старые полоски миниатюр в этой колонке (не входящие в нашу галерею)
      Array.from(leftCol.children)
        .filter(el => el !== galleryBlock && !galleryBlock.contains(el) && el.querySelectorAll && el.querySelectorAll('img').length >= 2)
        .forEach(el => el.remove());
    } else {
      // 2) Альтернативная цель: конкретные селекторы
      const tryLeft = document.querySelector('.row .col-12.col-md-5') || document.querySelector('.row .col-md-6');
      if (tryLeft) {
        const old = tryLeft.querySelector('.ratio, img');
        tryLeft.insertBefore(galleryBlock, tryLeft.firstChild);
        if (old) old.remove();
        // Удалим возможные старые полоски миниатюр (дубликаты) в колонке
        Array.from(tryLeft.children)
          .filter(el => el !== galleryBlock && !galleryBlock.contains(el) && el.querySelectorAll && el.querySelectorAll('img').length >= 2)
          .forEach(el => el.remove());
      } else {
        // 3) Фолбэк: заменить контейнер #mainImage, если он есть
        const mainImg = document.getElementById('mainImage');
        let targetHost = null;
        if (mainImg) {
          targetHost = mainImg.closest('.ratio') ? mainImg.closest('.ratio').parentElement : mainImg.parentElement;
        }
        if (targetHost && targetHost.parentElement) {
          targetHost.parentElement.replaceChild(galleryBlock, targetHost);
        }
      }
    }

    // Синхронизация активной миниатюры (подсветка рамкой)
    const thumbButtons = Array.from(document.querySelectorAll('.thumb[data-bs-target="#productCarousel"]'));
    const setActiveThumb = (idx) => {
      thumbButtons.forEach(b => {
        const to = parseInt(b.getAttribute('data-bs-slide-to') || '-1', 10);
        b.classList.toggle('active', to === idx);
      });
    };
    setActiveThumb(0);
    try {
      carouselEl.addEventListener('slid.bs.carousel', (ev) => {
        if (typeof ev.to === 'number') { setActiveThumb(ev.to); }
      });
    } catch (_) { }
    thumbButtons.forEach(b => {
      b.addEventListener('click', () => {
        const to = parseInt(b.getAttribute('data-bs-slide-to') || '-1', 10);
        if (to >= 0) setActiveThumb(to);
      });
    });
  });

  // Переміщення блоку «Кольори»: спочатку ПЕРЕД кнопками «Опис/Розмірна сітка», потім фолбеки
  scheduleIdle(function () {
    const card = document.getElementById('color-picker-card');
    if (!card) return;
    if (card.dataset.placed === '1') return;

    const placeBefore = (node) => {
      if (node && node.parentElement) {
        node.parentElement.insertBefore(card, node);
        card.dataset.placed = '1';
        return true;
      }
      return false;
    };
    const placeAfter = (node) => {
      if (node && node.parentElement) {
        if (node.nextSibling) node.parentElement.insertBefore(card, node.nextSibling);
        else node.parentElement.appendChild(card);
        card.dataset.placed = '1';
        return true;
      }
      return false;
    };

    // A) ПЕРВОЕ: ищем строку с кнопками (id, по .toggle-chip, по тексту)
    let togglesRow = document.getElementById('desc-size-toggles');

    if (!togglesRow) {
      const chips = Array.from(document.querySelectorAll('.toggle-chip'));
      if (chips.length) {
        // общий контейнер для чипов
        let cont = chips[0];
        while (cont && cont.parentElement && cont.tagName !== 'DIV') { cont = cont.parentElement; }
        togglesRow = cont || chips[0].parentElement;
      }
    }
    if (!togglesRow) {
      const btns = Array.from(document.querySelectorAll('button, a, .btn')).filter(el => {
        const t = (el.textContent || '').trim().toLowerCase();
        return t.includes('опис') || t.includes('розмірна сітка') || t.includes('розмірна') || t.includes('size');
      });
      if (btns.length) {
        let cont = btns[0];
        while (cont && cont.parentElement && cont.tagName !== 'DIV') { cont = cont.parentElement; }
        togglesRow = cont || btns[0].parentElement;
      }
    }
    if (togglesRow && placeBefore(togglesRow)) return;

    // B) ВТОРОЕ: если строка кнопок не найдена — ищем контроль размера и ставим ПОСЛЕ него
    const sizeCtrl = document.querySelector('[data-size-picker]') ||
      document.querySelector('select[name="size"]') ||
      document.querySelector('select[name*="size" i]') ||
      document.querySelector('[name="size"]');
    if (sizeCtrl && placeAfter(sizeCtrl)) return;

    // C) ФОЛБЕК: перед панелями опису/сітки
    const panels = document.querySelector('.panel-wrap');
    if (panels && placeBefore(panels)) return;

    // D) DOM может обновляться — наблюдаем и вставляем как только появится строка кнопок
    const observer = new MutationObserver(() => {
      if (card.dataset.placed === '1') { observer.disconnect(); return; }
      const row = document.getElementById('desc-size-toggles') ||
        (document.querySelector('.toggle-chip') && document.querySelector('.toggle-chip').closest('div'));
      if (row && placeBefore(row)) { observer.disconnect(); }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  });

  // Переносимо блоки з «Кольори» у «Новинках» всередину самої карточки (щоб анімація була єдиною)
  (function () {
    const dotsList = Array.from(document.querySelectorAll('.product-card-dots'));
    dotsList.forEach(dots => {
      // Находим ближайшую карточку (попередній сусід включає card)
      let card = dots.previousElementSibling;
      if (card && !card.classList.contains('card')) card = card.closest('.card');
      if (card) {
        card.style.position = card.style.position || 'relative';
        card.appendChild(dots);
      }
    });
  });

  // Тогглер мини‑корзины (и по id, и по data-атрибуту)
  const bindCartToggle = (el) => {
    if (!el) return;
    if (el.dataset.uiBoundCart === '1') return;
    el.dataset.uiBoundCart = '1';
    el.addEventListener('pointerdown', (e) => { suppressNextDocPointerdownUntil = Date.now() + 250; }, { passive: true });
    el.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); toggleMiniCart(); });
  };
  bindCartToggle(document.getElementById('cart-toggle'));
  bindCartToggle(document.getElementById('cart-toggle-mobile'));
  document.querySelectorAll('[data-cart-toggle]').forEach(bindCartToggle);

  // Пользовательская панель (десктоп)
  const userToggle = document.getElementById('user-toggle');
  const userPanel = document.getElementById('user-panel');
  if (userToggle && userPanel) {
    const openUser = () => { const id = nextEvt(); userPanel._opId = (userPanel._opId || 0) + 1; const opId = userPanel._opId; if (userPanel._hideTimeout) { clearTimeout(userPanel._hideTimeout); userPanel._hideTimeout = null; } showAnimatedPanel(userPanel); };
    const closeUser = (reason) => { const id = nextEvt(); userPanel._opId = (userPanel._opId || 0) + 1; const opId = userPanel._opId; userPanel.classList.remove('show'); userPanel.classList.add('hiding'); const t = setTimeout(() => { if (opId !== userPanel._opId) return; userPanel.classList.add('d-none'); userPanel.classList.remove('hiding'); userPanel.setAttribute('inert', ''); userPanel.setAttribute('aria-hidden', 'true'); }, 220); userPanel._hideTimeout = t; userPanel.addEventListener('transitionend', function onEnd(e) { if (e.target !== userPanel) return; userPanel.removeEventListener('transitionend', onEnd); if (opId !== userPanel._opId) return; clearTimeout(t); userPanel.classList.add('d-none'); userPanel.classList.remove('hiding'); userPanel.setAttribute('inert', ''); userPanel.setAttribute('aria-hidden', 'true'); }); };
    if (!userToggle.dataset.uiBoundUser) {
      userToggle.dataset.uiBoundUser = '1';
      userToggle.addEventListener('pointerdown', (e) => { suppressNextDocPointerdownUntil = Date.now() + 250; }, { passive: true });
      userToggle.addEventListener('click', (e) => { const id = nextEvt(); e.preventDefault(); e.stopPropagation(); if (Date.now() < uiGuardUntil) { return; } const cartOpen = miniCartPanel() && !miniCartPanel().classList.contains('d-none'); if (cartOpen) closeMiniCart('userToggle'); if (userPanel.classList.contains('d-none') || !userPanel.classList.contains('show')) { openUser(); } else { closeUser('userToggle'); } suppressGlobalCloseUntil = Date.now() + 220; });
    }
    document.addEventListener('pointerdown', (e) => { const id = nextEvt(); const tgt = e.target; const state = panelState(); const supNext = Date.now() < suppressNextDocPointerdownUntil; const supGlob = Date.now() < suppressGlobalCloseUntil; const outside = !userPanel.contains(tgt) && !userToggle.contains(tgt); if (supNext || supGlob) return; if (userPanel.classList.contains('d-none')) return; if (outside) { closeUser('docOutside'); } }, { passive: true });
    const uc = document.querySelector('[data-user-close]'); if (uc) { uc.addEventListener('click', (e) => { e.preventDefault(); closeUser(); }); }
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeUser(); });
  }

  // Пользовательская панель (мобильная)
  const userToggleMobile = document.getElementById('user-toggle-mobile');
  const userPanelMobile = document.getElementById('user-panel-mobile');
  if (userToggleMobile && userPanelMobile) {
    const openUserMobile = () => { const id = nextEvt(); userPanelMobile._opId = (userPanelMobile._opId || 0) + 1; const opId = userPanelMobile._opId; if (userPanelMobile._hideTimeout) { clearTimeout(userPanelMobile._hideTimeout); userPanelMobile._hideTimeout = null; } showAnimatedPanel(userPanelMobile); };
    const closeUserMobile = (reason) => { const id = nextEvt(); userPanelMobile._opId = (userPanelMobile._opId || 0) + 1; const opId = userPanelMobile._opId; userPanelMobile.classList.remove('show'); userPanelMobile.classList.add('hiding'); const t = setTimeout(() => { if (opId !== userPanelMobile._opId) return; userPanelMobile.classList.add('d-none'); userPanelMobile.classList.remove('hiding'); userPanelMobile.setAttribute('inert', ''); userPanelMobile.setAttribute('aria-hidden', 'true'); }, 220); userPanelMobile._hideTimeout = t; userPanelMobile.addEventListener('transitionend', function onEnd(e) { if (e.target !== userPanelMobile) return; userPanelMobile.removeEventListener('transitionend', onEnd); if (opId !== userPanelMobile._opId) return; clearTimeout(t); userPanelMobile.classList.add('d-none'); userPanelMobile.classList.remove('hiding'); userPanelMobile.setAttribute('inert', ''); userPanelMobile.setAttribute('aria-hidden', 'true'); }); };
    if (!userToggleMobile.dataset.uiBoundUser) {
      userToggleMobile.dataset.uiBoundUser = '1';
      userToggleMobile.addEventListener('pointerdown', (e) => { suppressNextDocPointerdownUntil = Date.now() + 250; }, { passive: true });
      userToggleMobile.addEventListener('click', (e) => { const id = nextEvt(); e.preventDefault(); e.stopPropagation(); if (Date.now() < uiGuardUntil) { return; } const cartOpen = miniCartPanel() && !miniCartPanel().classList.contains('d-none'); if (cartOpen) closeMiniCart('userToggleMobile'); if (userPanelMobile.classList.contains('d-none') || !userPanelMobile.classList.contains('show')) { openUserMobile(); } else { closeUserMobile('userToggleMobile'); } suppressGlobalCloseUntil = Date.now() + 220; });
    }
    document.addEventListener('pointerdown', (e) => { const id = nextEvt(); const tgt = e.target; const state = panelState(); const supNext = Date.now() < suppressNextDocPointerdownUntil; const supGlob = Date.now() < suppressGlobalCloseUntil; const outside = !userPanelMobile.contains(tgt) && !userToggleMobile.contains(tgt); if (supNext || supGlob) return; if (userPanelMobile.classList.contains('d-none')) return; if (outside) { closeUserMobile('docOutside'); } }, { passive: true });
    const ucMobile = userPanelMobile.querySelector('[data-user-close-mobile]'); if (ucMobile) { ucMobile.addEventListener('click', (e) => { e.preventDefault(); closeUserMobile(); }); }
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeUserMobile(); });
  }

  // Кнопка закрытия мини‑кошика
  const hookClose = () => {
    const c = document.querySelector('[data-cart-close]');
    const cMobile = document.querySelector('[data-cart-close-mobile]');
    if (c) { c.addEventListener('click', (e) => { e.preventDefault(); closeMiniCart(); }); }
    if (cMobile) { cMobile.addEventListener('click', (e) => { e.preventDefault(); closeMiniCart(); }); }
  };
  hookClose();

  // Закрытие по клику снаружи
  document.addEventListener('pointerdown', (e) => {
    const id = nextEvt();
    const supNext = Date.now() < suppressNextDocPointerdownUntil;
    if (supNext) { return; }
    const supGuard = Date.now() < uiGuardUntil;
    const supGlob = Date.now() < suppressGlobalCloseUntil;
    const panel = miniCartPanel();
    const toggle = window.innerWidth < 576 ?
      document.getElementById('cart-toggle-mobile') :
      document.getElementById('cart-toggle') || document.querySelector('[data-cart-toggle]');
    if (!panel) return;
    if (panel.classList.contains('d-none')) return;
    const tgt = e.target;
    const outside = !panel.contains(tgt) && (!toggle || !toggle.contains(tgt));
    if (supGuard || supGlob) return;
    if (outside) {
      closeMiniCart('docOutside');
    }
  }, { passive: true });
  // Закрытие по ESC
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeMiniCart(); });

  // Адаптация при ресайзе
  window.addEventListener('resize', debounce(() => {
    const panel = miniCartPanel();
    if (panel && !panel.classList.contains('d-none')) {
      // пересчитать позиционирование, сохраняя анимационные классы
      const wasShown = panel.classList.contains('show');
      if (wasShown) panel.classList.remove('show');
      // режим позиционирования
      if (window.innerWidth < 576) {
        panel.classList.add('position-fixed', 'top-0', 'start-0', 'vw-100', 'vh-100', 'rounded-0');
        panel.style.right = '';
        panel.style.top = '0';
      } else {
        panel.classList.remove('position-fixed', 'top-0', 'start-0', 'vw-100', 'vh-100', 'rounded-0');
        panel.style.right = '0';
        panel.style.top = 'calc(100% + 8px)';
      }
      if (wasShown) {
        if ('requestAnimationFrame' in window) {
          requestAnimationFrame(() => panel.classList.add('show'));
        } else {
          panel.classList.add('show');
        }
      }
    }
  }, 150));

  // ===== Мобильное нижнее меню: скрытие/показ по скроллу, фокусу и свайпу =====
  (function () {
    const bottomNav = document.querySelector('.bottom-nav');
    if (!bottomNav) return;
    const bottomNavDeviceClass = (document.documentElement.dataset.deviceClass || 'high').toLowerCase();
    const isSmallScreen = window.matchMedia('(max-width: 768px)').matches;
    const scrollAdaptiveEnabled = !isSmallScreen && bottomNavDeviceClass === 'high';
    bottomNav.dataset.scrollMode = scrollAdaptiveEnabled ? 'adaptive' : 'static';

    let lastScrollY = PerformanceOptimizer.getScrollY();
    let hidden = false;
    let hintShown = sessionStorage.getItem('bottom-nav-hint') === '1';
    let touchStartY = null;
    let touchStartX = null;
    let touchMoved = false;
    let isScrolling = false;
    let scrollEndTimer = null;

    // Улучшенная система предотвращения мерцания
    let scrollDirection = 0; // -1 = вверх, 1 = вниз, 0 = нет
    let scrollMomentum = 0; // Накопленный импульс скролла
    let lastToggleTime = 0;
    const TOGGLE_COOLDOWN = 400; // Минимальная пауза между переключениями

    const setHidden = (v, force = false) => {
      if (hidden === v) return;

      // Защита от частых переключений
      const now = Date.now();
      if (!force && now - lastToggleTime < TOGGLE_COOLDOWN) return;

      hidden = v;
      lastToggleTime = now;
      scrollMomentum = 0; // Полный сброс при переключении

      PerformanceOptimizer.batchDOMOperations([
        () => bottomNav.classList.toggle('bottom-nav--hidden', hidden)
      ]);
    };

    const maybeShowHint = () => {
      if (!scrollAdaptiveEnabled) return;
      if (hintShown) return;
      if (prefersReducedMotion || PERF_LITE) { hintShown = true; return; }
      bottomNav.classList.add('hint-wiggle');
      setTimeout(() => bottomNav.classList.remove('hint-wiggle'), 950);
      sessionStorage.setItem('bottom-nav-hint', '1');
      hintShown = true;
    };

    if (scrollAdaptiveEnabled) {
      // Оптимизированная обработка скролла
      PerformanceOptimizer.onScrollChange = (currentY, lastY) => {
        const dy = currentY - lastY;
        if (Math.abs(dy) < 1) return; // Игнорируем микро-движения

        isScrolling = true;
        clearTimeout(scrollEndTimer);
        scrollEndTimer = setTimeout(() => {
          isScrolling = false;
          scrollMomentum = 0; // Сброс после остановки скролла
        }, 150);

        // Определяем направление с гистерезисом
        const currentDirection = dy > 2 ? 1 : (dy < -2 ? -1 : 0);

        // Сброс импульса при смене направления
        if (currentDirection !== 0 && scrollDirection !== 0 && currentDirection !== scrollDirection) {
          scrollMomentum = 0;
        }
        scrollDirection = currentDirection;

        // Накапливаем импульс
        scrollMomentum += dy;

        // Разные пороги для скрытия и показа (гистерезис)
        const HIDE_THRESHOLD = 50;  // Нужно проскроллить вниз 50px
        const SHOW_THRESHOLD = -20; // Нужно проскроллить вверх 20px

        // Скрытие меню - только при значительном скролле вниз
        if (!hidden && scrollMomentum > HIDE_THRESHOLD) {
          setHidden(true);
        }
        // Показ меню - при любом скролле вверх (если скрыто)
        else if (hidden && scrollMomentum < SHOW_THRESHOLD) {
          setHidden(false);
        }

        // Ограничиваем импульс
        scrollMomentum = Math.max(-100, Math.min(100, scrollMomentum));
      };

      // Инициализируем оптимизированный скролл
      PerformanceOptimizer.initScrollOptimization();
    } else {
      bottomNav.classList.remove('bottom-nav--hidden', 'hint-wiggle');
      hidden = false;
    }

    // Фокус в полях ввода — скрыть; блюр — показать
    document.addEventListener('focusin', (e) => {
      if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable)) {
        setHidden(true);
      }
    });
    document.addEventListener('focusout', (e) => {
      if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable)) {
        setHidden(false);
        if (scrollAdaptiveEnabled) {
          maybeShowHint();
        }
      }
    });

    if (scrollAdaptiveEnabled) {
      // Свайпы - только для явных жестов, не конфликтующих со скроллом
      const onTouchStart = (e) => {
        const t = e.touches ? e.touches[0] : e;
        touchStartY = t.clientY;
        touchStartX = t.clientX;
        touchMoved = false;
      };
      const onTouchMove = (e) => {
        touchMoved = true;
      };
      const onTouchEnd = (e) => {
        if (touchStartY == null) return;

        // Игнорируем тач-события во время активного скролла
        if (isScrolling) {
          touchStartY = touchStartX = null;
          touchMoved = false;
          return;
        }

        const t = (e.changedTouches && e.changedTouches[0]) || e;
        const dy = (t.clientY - touchStartY) || 0;
        const dx = (t.clientX - touchStartX) || 0;
        const absY = Math.abs(dy), absX = Math.abs(dx);

        // Только явные вертикальные свайпы (не скролл!)
        // Увеличенный порог для предотвращения ложных срабатываний
        if (absY > 40 && absY > absX * 2) {
          if (dy > 0) {
            setHidden(true, true); // force = true для свайпов
          } else if (hidden) {
            setHidden(false, true);
          }
          maybeShowHint();
        }
        touchStartY = touchStartX = null;
        touchMoved = false;
      };

      // Навешиваем только на меню (не глобально, чтобы не конфликтовать со скроллом)
      bottomNav.addEventListener('touchstart', onTouchStart, { passive: true });
      bottomNav.addEventListener('touchmove', onTouchMove, { passive: true });
      bottomNav.addEventListener('touchend', onTouchEnd, { passive: true });

      // Первичная ненавязчивая подсказка — один раз за сессию
      setTimeout(() => { maybeShowHint(); }, 800);
    }
  })();
});

// Runtime diagnostics removed for production

// ===== Авто-оптимизация тяжёлых эффектов без изменения вида =====
document.addEventListener('DOMContentLoaded', function () {
  // На `data-device-class="low"` те же эффекты уже глобально killed статическим CSS
  // (Phase 3.2). Runtime-релаксация тут лишь включала бы их обратно с inline !important,
  // перекрывая CSS. Поэтому на low — просто выходим.
  const _dc = (document.documentElement.dataset.deviceClass || '').toLowerCase();
  if (_dc === 'low') return;
  if (!(PERF_LITE || prefersReducedMotion)) return;
  scheduleIdle(() => {
    const candidateSelectors = [
      '.hero.bg-hero', '.bottom-nav', '#mini-cart-panel-mobile', '#user-panel-mobile',
      '.featured-bg-unified', '.categories-bg-unified', '.card.product',
      '[class*="particles" i]', '[class*="spark" i]', '[class*="glow" i]'
    ];
    const unique = new Set();
    const candidates = [];
    candidateSelectors.forEach(sel => {
      document.querySelectorAll(sel).forEach(el => {
        if (!el || unique.has(el)) return; unique.add(el); candidates.push(el);
      });
    });

    const heavyMeta = [];
    const metaMap = new Map();
    candidates.forEach(el => {
      try {
        const cs = DOMCache.getComputedStyle(el);
        const hasBackdrop = (cs.backdropFilter && cs.backdropFilter !== 'none') || (cs.webkitBackdropFilter && cs.webkitBackdropFilter !== 'none');
        const hasBlur = (cs.filter || '').includes('blur');
        const hasBigShadow = (cs.boxShadow || '').includes('px');
        const isAnimatedInf = (cs.animationIterationCount || '').includes('infinite');
        if (hasBackdrop || hasBlur || hasBigShadow || isAnimatedInf) {
          const meta = { el, hasBackdrop, hasInfiniteAnim: isAnimatedInf };
          heavyMeta.push(meta);
          metaMap.set(el, meta);
        }
      } catch (_) { }
    });

    const animatedHeavyMeta = heavyMeta.filter(({ hasInfiniteAnim }) => hasInfiniteAnim);
    if (!animatedHeavyMeta.length) return;

    let relaxTimer = null;
    let relaxed = false;
    function relaxHeavy() {
      if (relaxed) return; relaxed = true;
      animatedHeavyMeta.forEach(({ el, hasInfiniteAnim }) => {
        try {
          if (hasInfiniteAnim) {
            el.style.setProperty('animation-play-state', 'paused', 'important');
          }
        } catch (_) { }
      });
    }
    function restoreHeavy() {
      if (!relaxed) return; relaxed = false;
      animatedHeavyMeta.forEach(({ el }) => {
        try {
          el.style.removeProperty('animation-play-state');
        } catch (_) { }
      });
    }
    function onScroll() {
      relaxHeavy();
      if (relaxTimer) clearTimeout(relaxTimer);
      relaxTimer = setTimeout(restoreHeavy, 350);
    }
    window.addEventListener('scroll', onScroll, { passive: true });

    if ('IntersectionObserver' in window) {
      const io = new IntersectionObserver(entries => {
        PerformanceOptimizer.batchDOMOperations(
          entries.map(entry => () => {
            const meta = metaMap.get(entry.target);
            if (!meta || !meta.hasInfiniteAnim) return;
            try {
              entry.target.style.setProperty('animation-play-state', entry.isIntersecting ? 'running' : 'paused', 'important');
            } catch (_) { }
          })
        );
      }, { threshold: 0.05 });
      animatedHeavyMeta.forEach(({ el }) => { try { io.observe(el); } catch (_) { } });
    }
  });
});


// Делегирование клика "добавить в корзину"
function getQtyFromTrigger(btn) {
  if (!btn || typeof btn.closest !== 'function') {
    return null;
  }
  let scope = btn.closest('[data-qty]');
  let qtyInput = scope ? scope.querySelector('input[type="number"]') : null;
  if (!qtyInput) {
    qtyInput = document.getElementById('qty');
  }
  if (!qtyInput) {
    return null;
  }
  const parsed = parseInt(qtyInput.value || '1', 10);
  if (!Number.isNaN(parsed) && parsed > 0) {
    return parsed;
  }
  return null;
}

function trackAddToCartAnalytics(serverData, triggerButton, fallbackQty) {
  try {
    if (!window.trackEvent || !serverData || !serverData.ok) {
      return;
    }
    const analyticsItem = serverData.item || null;
    const productId = (analyticsItem && analyticsItem.product_id) || (triggerButton && triggerButton.getAttribute && triggerButton.getAttribute('data-add-to-cart'));
    if (!productId) {
      return;
    }
    const productContainer = document.getElementById('product-detail-container');
    const productAnalyticsEl = document.getElementById('product-analytics-payload');
    let offerId = analyticsItem && analyticsItem.offer_id;
    if (!offerId && productContainer) {
      offerId = productContainer.getAttribute('data-current-offer-id');
    }
    if (!offerId) {
      offerId = 'TC-' + String(productId) + '-default-S';
    }

    let quantity = Number(analyticsItem && analyticsItem.quantity);
    if (!Number.isFinite(quantity) || quantity <= 0) {
      if (typeof fallbackQty === 'number' && fallbackQty > 0) {
        quantity = fallbackQty;
      } else {
        const qtyFromDom = getQtyFromTrigger(triggerButton);
        if (qtyFromDom) {
          quantity = qtyFromDom;
        }
      }
    }
    if (!Number.isFinite(quantity) || quantity <= 0) {
      quantity = 1;
    }

    let fallbackPrice = triggerButton ? parseFloat(triggerButton.getAttribute('data-product-price') || '0') : NaN;
    if ((!Number.isFinite(fallbackPrice) || fallbackPrice <= 0) && productAnalyticsEl) {
      const datasetPrice = parseFloat(productAnalyticsEl.dataset.price || '0');
      if (Number.isFinite(datasetPrice) && datasetPrice >= 0) {
        fallbackPrice = datasetPrice;
      }
    }
    let itemPrice = Number(analyticsItem && analyticsItem.item_price);
    if (!Number.isFinite(itemPrice) || itemPrice < 0) {
      itemPrice = Number.isFinite(fallbackPrice) && fallbackPrice >= 0 ? fallbackPrice : 0;
    }

    let value = Number(analyticsItem && analyticsItem.value);
    if (!Number.isFinite(value) || value < 0) {
      value = itemPrice * quantity;
    }
    const currency = (analyticsItem && analyticsItem.currency) || 'UAH';

    let contentName = analyticsItem && analyticsItem.product_title;
    if (!contentName && productAnalyticsEl) {
      contentName = productAnalyticsEl.dataset.title || '';
    }
    if (!contentName && triggerButton) {
      contentName = triggerButton.getAttribute('data-product-name') || '';
    }

    let contentCategory = analyticsItem && analyticsItem.product_category;
    if (!contentCategory && productAnalyticsEl) {
      contentCategory = productAnalyticsEl.dataset.category || '';
    }
    if (!contentCategory && triggerButton) {
      contentCategory = triggerButton.getAttribute('data-product-category') || '';
    }

    let variantLabel = (analyticsItem && analyticsItem.size) ? analyticsItem.size : '';
    if (!variantLabel) {
      const selectedSize = document.querySelector('input[name="size"]:checked');
      if (selectedSize && selectedSize.value) {
        variantLabel = selectedSize.value;
      }
    }
    const payload = {
      content_ids: [offerId],
      content_type: 'product',
      value: value,
      currency: currency,
      num_items: quantity,
      contents: [{
        id: offerId,
        quantity: quantity,
        item_price: itemPrice
      }]
    };

    if (contentName) {
      payload.content_name = contentName;
      payload.contents[0].item_name = contentName;
    }
    if (contentCategory) {
      payload.content_category = contentCategory;
      payload.contents[0].item_category = contentCategory;
    }
    payload.contents[0].brand = 'TwoComms';
    const eventId = safeGenerateAnalyticsEventId();
    payload.event_id = eventId;
    payload.__meta = buildMetaWithUserData(eventId, payload.__meta);

    window.trackEvent('AddToCart', payload);
    try {
      if (window.__twcAnalytics && typeof window.__twcAnalytics.pushAddToCartEvent === 'function') {
        window.__twcAnalytics.pushAddToCartEvent({
          eventId,
          offerId,
          contentName,
          contentCategory,
          currency,
          itemPrice,
          quantity,
          value,
          variant: variantLabel
        });
      }
    } catch (err) {
      if (console && console.debug) {
        console.debug('AddToCart dataLayer error:', err);
      }
    }
  } catch (err) {
    if (console && console.debug) {
      console.debug('AddToCart analytics error:', err);
    }
  }
}
window.__twcTrackAddToCart = trackAddToCartAnalytics;

document.addEventListener('click', (e) => {
  const btn = e.target.closest('[data-add-to-cart]');
  if (!btn) return;
  // Если на кнопке есть inline-обработчик (AddToCart), не дублируем запрос
  if (btn.hasAttribute('onclick')) return;
  e.preventDefault();
  const productId = btn.getAttribute('data-add-to-cart');
  const sizeInput = document.querySelector('input[name="size"]:checked');
  const size = sizeInput ? sizeInput.value : '';
  const qtyFromDom = getQtyFromTrigger(btn);
  const qty = qtyFromDom && qtyFromDom > 0 ? qtyFromDom : 1;

  // Получаем выбранный цвет
  let colorVariantId = null;
  const activeColorSwatch = document.querySelector('#color-picker .color-swatch.active');
  if (activeColorSwatch) {
    colorVariantId = activeColorSwatch.getAttribute('data-variant');
  }

  const normalizedSize = size ? String(size).toUpperCase() : '';
  const body = new URLSearchParams({ product_id: productId, size: normalizedSize, qty: String(qty) });
  if (colorVariantId) {
    body.append('color_variant_id', colorVariantId);
  }

  // Открываем мини-корзину сразу, чтобы пользователь видел текущее состояние
  try { openMiniCart({ skipRefresh: true }); } catch (_) { }

  fetch('/cart/add/', {
    method: 'POST',
    headers: {
      'X-CSRFToken': getCookie('csrftoken'),
      'X-Requested-With': 'XMLHttpRequest',
      'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
    },
    body
  })
    .then(r => r.json())
    .then(d => {
      if (d && d.ok) {
        if (typeof d.count === 'number') { updateCartBadge(d.count); }
        const miniUpdate = refreshMiniCart();
        miniUpdate
          .then(() => { openMiniCart({ skipRefresh: true }); })
          .catch(() => { openMiniCart({ skipRefresh: true }); })
          .finally(() => { refreshCartSummary(); });

        // Отправляем событие обновления корзины для страницы корзины
        try {
          document.dispatchEvent(new CustomEvent('cartUpdated', { detail: { action: 'add', productId: productId } }));
        } catch (_) { }

        // Небольшой визуальный отклик
        btn.classList.add('btn-success');
        setTimeout(() => btn.classList.remove('btn-success'), 400);

        trackAddToCartAnalytics(d, btn, qty);
      } else {
        btn.classList.add('btn-danger');
        setTimeout(() => btn.classList.remove('btn-danger'), 600);
      }
    })
    .catch(() => {
      btn.classList.add('btn-danger');
      setTimeout(() => btn.classList.remove('btn-danger'), 600);
    });
});

// ====== PRODUCT DETAIL: цвета и галерея (lazy — modules/product-gallery.js) ======
document.addEventListener('DOMContentLoaded', function () {
  if (!document.getElementById('productCarousel')) return;
  if (!document.getElementById('variant-data') || !document.getElementById('color-picker')) return;
  import('./modules/product-gallery.js')
    .then((m) => { try { m.initProductGallery(); } catch (_) {} })
    .catch(() => {});
});

// ====== CONTACTS: показать телефон ======
document.addEventListener('DOMContentLoaded', function () {
  const btn = document.getElementById('show-phone-btn'); const phone = document.getElementById('phone-number'); if (btn && phone) { btn.addEventListener('click', () => { phone.style.display = 'inline-block'; btn.style.display = 'none'; }); }
});

// ===== ИЗБРАННЫЕ ТОВАРЫ: глобальные стабы + lazy-loader (Phase 2.1 ext) =====
// Реальная реализация живёт в modules/favorites.js и грузится по первому же
// клику heart-кнопки или первому IO-событию для .favorite-btn в viewport.
// Inline `onclick="toggleFavorite(...)"` в шаблонах продолжает работать:
// стабы сохраняют синхронный вызов, затем dynamic-import + делегация.
window.updateFavoritesBadge = updateFavoritesBadge;

let __favModulePromise = null;
function __loadFavModule() {
  if (!__favModulePromise) {
    __favModulePromise = import('./modules/favorites.js').catch((err) => {
      __favModulePromise = null;
      throw err;
    });
  }
  return __favModulePromise;
}

function toggleFavorite(productId, button) {
  if (button) button.classList.add('loading');
  __loadFavModule()
    .then((m) => { try { m.toggleFavorite(productId, button); } catch (_) { if (button) button.classList.remove('loading'); } })
    .catch(() => { if (button) button.classList.remove('loading'); });
}

function checkFavoriteStatus(productId, button) {
  __loadFavModule()
    .then((m) => { try { m.checkFavoriteStatus(productId, button); } catch (_) {} })
    .catch(() => {});
}

function showNotification(message, type = 'info') {
  __loadFavModule()
    .then((m) => { try { m.showNotification(message, type); } catch (_) {} })
    .catch(() => {});
}
window.toggleFavorite = toggleFavorite;
window.checkFavoriteStatus = checkFavoriteStatus;
window.showNotification = showNotification;

// Инициализация статуса избранного — ленивая проверка только для видимых кнопок.
document.addEventListener('DOMContentLoaded', function () {
  const favoriteButtons = document.querySelectorAll('.favorite-btn');
  if (!favoriteButtons.length) return;
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const button = entry.target;
        const productId = button.getAttribute('data-product-id');
        if (productId) { checkFavoriteStatus(productId, button); }
        io.unobserve(button);
      });
    }, { root: null, rootMargin: '100px 0px', threshold: 0.01 });
    favoriteButtons.forEach((btn) => io.observe(btn));
  } else {
    favoriteButtons.forEach((button) => {
      const productId = button.getAttribute('data-product-id');
      if (productId) { checkFavoriteStatus(productId, button); }
    });
  }
});

// ===== ФУНКЦИОНАЛЬНОСТЬ СВОРАЧИВАНИЯ КАТЕГОРИЙ =====

// Поиск в шапке
document.addEventListener('DOMContentLoaded', function () {
  const headerSearch = document.querySelector('form[role="search"] input[name="q"]');
  if (headerSearch) {
    headerSearch.addEventListener('search', function () {
      const term = (headerSearch.value || '').trim();
      if (term) { try { if (window.trackEvent) { window.trackEvent('Search', { search_string: term }); } } catch (_) { } }
    });
    headerSearch.form && headerSearch.form.addEventListener('submit', function () {
      const term = (headerSearch.value || '').trim();
      if (term) { try { if (window.trackEvent) { window.trackEvent('Search', { search_string: term }); } } catch (_) { } }
    });
  }
});

// Трекинг выбора отделения НП (поле np_office в корзине/чекауте)
document.addEventListener('input', function (e) {
  const el = e.target;
  if (!el || el.name !== 'np_office') return;
  const val = (el.value || '').trim();
  if (val && val.length >= 3) {
    try { if (window.trackEvent) { window.trackEvent('FindLocation', { query: val }); } } catch (_) { }
  }
});

// ViewContent на листингах — по клику на любую область карточки
document.addEventListener('click', function (e) {
  try {
    const card = e.target.closest && e.target.closest('.card.product');
    if (!card) return;
    const pid = card.getAttribute('data-product-id');
    const title = card.getAttribute('data-product-title');
    const price = card.getAttribute('data-product-price');

    if (pid && window.trackEvent) {
      // Для карточек в каталоге используем базовый offer_id (default color, size S)
      const offerId = 'TC-' + pid + '-default-S';
      const priceNum = price ? parseFloat(price) : undefined;

      const eventId = safeGenerateAnalyticsEventId();
      const meta = buildMetaWithUserData(eventId);
      window.trackEvent('ViewContent', {
        content_ids: [offerId],
        content_type: 'product',
        content_name: title,
        value: priceNum,
        currency: 'UAH',
        contents: [{
          id: offerId,
          quantity: 1,
          item_price: priceNum
        }],
        event_id: eventId,
        __meta: meta
      });
    }
  } catch (_) { }
});

// Опрос монтируется page-scoped импортом (index.html). Дубль init удалён ради экономии startup JS.

// Цветовые точки, корзина и пагинация подгружаются по требованию, чтобы сократить работу в главном потоке
document.addEventListener('DOMContentLoaded', () => {
  scheduleIdle(() => {
    if (document.querySelector('.product-card-wrap') || document.getElementById('productCarousel')) {
      import('./modules/product-media.js')
        .then(({ initProductMedia }) => initProductMedia())
        .catch(() => { });
    }
    if (document.querySelector('.cart-page-container') || document.getElementById('promo-code-input')) {
      import('./modules/cart.js?v=20260422b')
        .then(({ initCartInteractions }) => initCartInteractions())
        .catch(() => { });
    }
    // Home-only блоки: featured toggle, categories toggle, card equalization,
    // pagination — все в одном модуле, подгружаются lazy при наличии маркеров.
    if (
      document.getElementById('load-more-btn') ||
      document.getElementById('products-container') ||
      document.getElementById('featuredToggle') ||
      document.getElementById('featured-toggle') ||
      document.getElementById('categoriesToggle')
    ) {
      import('./modules/homepage.js')
        .then(({ initHomepage }) => initHomepage())
        .catch(() => { });
    }
  });
});
