import {
  DOMCache,
  debounce,
  scheduleIdle,
  prefersReducedMotion,
  PERF_LITE,
  nextEvt,
  nowTs,
  getCookie
} from './modules/shared.js';
import { PerformanceOptimizer, ImageOptimizer } from './modules/optimizers.js';

// Помечаем, что основной JS инициализирован и можно запускать анимации
document.documentElement.classList.add('js-ready');

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

document.addEventListener('DOMContentLoaded',()=>{
  // Инициализация оптимизации изображений переносится в idle, чтобы не блокировать главный поток
  scheduleIdle(()=> ImageOptimizer.init());
  
  const registerRevealTargets = (scope=document)=>{
    const basicTargets = scope.querySelectorAll('.reveal, .reveal-fast');
    if(!supportsIO){
      basicTargets.forEach(el=>el.classList.add('visible'));
      return;
    }
    basicTargets.forEach(el=>io.observe(el));
  };
  registerRevealTargets();
  
  // Стаггер-анимация карточек в гриде — по порядку DOM, без измерений
  const gridObserver = supportsIO ? new IntersectionObserver(entries=>{
    entries.forEach(entry=>{
      if(!entry.isIntersecting) return;
      const grid = entry.target;
      const ordered = Array.from(grid.querySelectorAll('.stagger-item'));

      // Мягкий каскад без дёрганий: шаг зависит от числа карточек,
      // отключается при reduced motion/перф-лайт
      const count = ordered.length || 1;
      const step = (prefersReducedMotion || PERF_LITE)
        ? 0
        : Math.max(50, Math.min(110, Math.floor(900 / count)));
      try{ if(window.equalizeCardHeights) window.equalizeCardHeights(); }catch(_){ }
      ordered.forEach((el,i)=>{
        el.style.setProperty('--d', (i*step)+'ms'); // дублируем задержку в CSS (на всякий)
        const revealCard = ()=>{
          el.classList.add('visible'); 
          
          // Анимация цветов товаров - СТРОГО вместе с карточкой
          const colorDots = el.closest('.product-card-wrap').querySelector('.product-card-dots');
          if(colorDots) {
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
        if(step === 0){
          revealCard();
        } else {
          setTimeout(revealCard, i*step);
        }
      });

      gridObserver.unobserve(grid);
    });
  },{threshold:.12, rootMargin:'0px 0px -10% 0px'}) : null;
  const grids = document.querySelectorAll('[data-stagger-grid]');
  if(!supportsIO){
    grids.forEach(grid=>{
      grid.querySelectorAll('.stagger-item').forEach(el=>el.classList.add('visible'));
    });
  } else {
    grids.forEach(grid=>gridObserver.observe(grid));
  }

  requestAnimationFrame(() => {
    document.documentElement.classList.add('reveal-ready');
    if(!supportsIO || prefersReducedMotion){
      document.querySelectorAll('.reveal, .reveal-fast, .reveal-stagger, .stagger-item').forEach(el=>el.classList.add('visible'));
    }
  });
 
  // Экспортируем функцию для динамически подгруженных карточек (load more)
  window.registerRevealTargets = registerRevealTargets;
});

// ===== Force hide cart/profile on mobile (header widgets) - оптимизированная версия =====
document.addEventListener('DOMContentLoaded', function() {
  // Кэшируем элементы и используем CSS классы вместо прямого изменения стилей
  const cartContainer = document.querySelector('.cart-container[data-mobile-hide="true"]');
  const profileContainer = document.querySelector('.user-profile-container[data-mobile-hide="true"]');
  
  if (!cartContainer && !profileContainer) return;
  
  // Используем CSS медиа-запросы вместо JavaScript для скрытия элементов
  function updateMobileVisibility() {
    // Используем requestAnimationFrame для избежания принудительной компоновки
    requestAnimationFrame(() => {
      const isMobile = window.innerWidth <= 991.98;
      
      if (cartContainer) {
        cartContainer.classList.toggle('mobile-hidden', isMobile);
      }
      if (profileContainer) {
        profileContainer.classList.toggle('mobile-hidden', isMobile);
      }
    });
  }
  
  // Инициализация - убеждаемся, что элементы видны на десктопе
  function initDesktopVisibility() {
    const isDesktop = window.innerWidth > 991.98;
    if (isDesktop) {
      if (cartContainer) {
        cartContainer.classList.remove('mobile-hidden');
      }
      if (profileContainer) {
        profileContainer.classList.remove('mobile-hidden');
      }
    }
  }
  
  // Инициализация с задержкой для избежания блокировки рендеринга
  setTimeout(() => {
    initDesktopVisibility();
    updateMobileVisibility();
  }, 0);
  
  // Используем более эффективный обработчик resize
  let resizeTimeout;
  window.addEventListener('resize', function() {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(updateMobileVisibility, 100);
  });
});

// ===== Корзина (AJAX) =====

const panelState = ()=>({
  userShown: !(document.getElementById('user-panel')||{classList:{contains:()=>true}}).classList.contains('d-none'),
  userMobileShown: !(document.getElementById('user-panel-mobile')||{classList:{contains:()=>true}}).classList.contains('d-none'),
  cartShown: !(miniCartPanel()||{classList:{contains:()=>true}}).classList.contains('d-none')
});
function updateCartBadge(count){
  const n = String(count||0);
  const desktop = document.getElementById('cart-count');
  const mobile = document.getElementById('cart-count-mobile');

  requestAnimationFrame(() => {
    if(desktop){
      desktop.textContent = n;
      desktop.classList.add('visible');
    }
    if(mobile){
      mobile.textContent = n;
      mobile.classList.add('visible');
    }
  });
}
window.updateCartBadge = updateCartBadge;

function refreshCartSummary(){
  return fetch('/cart/summary/',{
    headers:{'X-Requested-With':'XMLHttpRequest'},
    cache:'no-store'
  })
    .then(r=>r.ok?r.json():null)
    .then(d=>{ if(d && d.ok && typeof d.count === 'number'){ updateCartBadge(d.count); }})
    .catch(()=>{});
}
window.refreshCartSummary = refreshCartSummary;

// Функция для обновления счетчика избранного
function updateFavoritesBadge(count){
  const n = String(count||0);
  const desktop = DOMCache.get('favorites-count');
  const mobile = DOMCache.get('favorites-count-mobile');
  const mini = DOMCache.get('favorites-count-mini');
  const favoritesWrapper = DOMCache.query('.favorites-icon-wrapper');
  const mobileIcon = DOMCache.query('a[href*="favorites"] .bottom-nav-icon');
  
  // Используем requestAnimationFrame для избежания принудительной компоновки
  requestAnimationFrame(() => {
    // Обновляем десктопный счетчик
    if(desktop){ 
      desktop.textContent=n; 
      desktop.classList.add('visible');
      
      if(count > 0) {
        // Добавляем класс для анимации когда есть товары
        if(favoritesWrapper) {
          favoritesWrapper.classList.add('has-items');
        }
      } else {
        // Убираем класс когда нет товаров
        if(favoritesWrapper) {
          favoritesWrapper.classList.remove('has-items');
        }
      }
    }
    
    // Обновляем мобильный счетчик
    if(mobile){ 
      mobile.textContent=n; 
      
      if(count > 0) {
        mobile.classList.add('visible');
        if(mobileIcon) {
          mobileIcon.classList.add('has-items');
        }
      } else {
        mobile.classList.remove('visible');
        if(mobileIcon) {
          mobileIcon.classList.remove('has-items');
        }
      }
    }
    
    // Обновляем счетчик в минипрофиле
    if(mini){ 
      mini.textContent=n; 
      
      if(count > 0) {
        mini.classList.add('visible');
      } else {
        mini.classList.remove('visible');
      }
    }
  });
}

// Применение цветов свотчей (включая комбинированные) по data-* атрибутам
function applySwatchColors(root){
  try{
    const scope = root || document;
    const list = scope.querySelectorAll('.cart-item-swatch, .swatch, .order-item-swatch, .color-dot, .featured-color-dot');
    list.forEach(function(el){
      const primary = el.getAttribute('data-primary') || '';
      const secondary = el.getAttribute('data-secondary') || '';
      
      // Используем requestAnimationFrame для избежания принудительной компоновки
      requestAnimationFrame(() => {
        // Устанавливаем CSS-переменные для комбинированных цветов
        if(primary) el.style.setProperty('--primary-color', primary);
        if(secondary && secondary !== 'None'){
          el.style.setProperty('--secondary-color', secondary);
        } else {
          el.style.removeProperty('--secondary-color');
        }
        
        // Устанавливаем прямой background-color для .swatch элементов
        if(el.classList.contains('swatch') && primary) {
          el.style.backgroundColor = primary;
        }
      });
    });
  }catch(_){ }
}

// Мини‑корзина с кэшированием
function miniCartPanel(){ 
  if(window.innerWidth < 576){
    return DOMCache.get('mini-cart-panel-mobile');
  } else {
    return DOMCache.get('mini-cart-panel');
  }
}
// Небольшая защита от мгновенного закрытия при переключении панелей
let uiGuardUntil = 0;
let suppressGlobalCloseUntil = 0;
let suppressNextDocPointerdownUntil = 0; // блокируем ближайший pointerdown от документа (клик по тогглеру)
function openMiniCart(opts={}){
  const { skipRefresh=false } = opts;
  const id=nextEvt();
  const panel=miniCartPanel(); if(!panel) return;
  // Оп‑токен: любое новое действие отменяет старые таймауты/слушатели
  panel._opId = (panel._opId||0)+1; const opId = panel._opId;
  if(panel._hideTimeout){ clearTimeout(panel._hideTimeout); panel._hideTimeout = null; }
  panel.classList.remove('hiding');
  // Закрываем открытый мини‑профиль (desktop/mobile), если он был открыт
  [document.getElementById('user-panel'), document.getElementById('user-panel-mobile')]
    .forEach(up=>{ if(up && !up.classList.contains('d-none')){ up.classList.remove('show'); setTimeout(()=>up.classList.add('d-none'), 200); }});
  panel.classList.remove('d-none','hiding');
  // Мобильный полноэкранный режим
  if(window.innerWidth < 576){
    panel.classList.add('position-fixed','top-0','start-0','vw-100','vh-100','rounded-0');
    panel.style.right = '';
    panel.style.top = '0';
  }else{
    panel.classList.remove('position-fixed','top-0','start-0','vw-100','vh-100','rounded-0');
    panel.style.right = '0';
    panel.style.top = 'calc(100% + 8px)';
  }
  const markOpened = () => {
    panel.classList.add('show');
    uiGuardUntil = Date.now() + 220;
    suppressGlobalCloseUntil = Date.now() + 180;
  };
  if('requestAnimationFrame' in window){
    requestAnimationFrame(markOpened);
  } else {
    markOpened();
  }
  if(!skipRefresh) refreshMiniCart();
}
function closeMiniCart(reason){
  const id=nextEvt();
  const panel=miniCartPanel(); if(!panel) return;
  panel._opId = (panel._opId||0)+1; const opId = panel._opId;
  panel.classList.remove('show');
  panel.classList.add('hiding');
  const hideAfter= setTimeout(()=>{
    if(opId !== panel._opId) return; // Уже было другое действие
    panel.classList.add('d-none');
    panel.classList.remove('hiding');
  }, 260);
  panel._hideTimeout = hideAfter;
  // если есть transitionend — ускорим скрытие
  panel.addEventListener('transitionend', function onTrEnd(e){
    if(e.target!==panel) return;
    panel.removeEventListener('transitionend', onTrEnd);
    if(opId !== panel._opId) return; // Не актуально
    clearTimeout(hideAfter);
    panel.classList.add('d-none');
    panel.classList.remove('hiding');
  });
}
function toggleMiniCart(){
  const panel=miniCartPanel(); if(!panel) return;
  if(panel.classList.contains('d-none') || !panel.classList.contains('show')) openMiniCart(); else closeMiniCart();
}

function getCheckoutAnalyticsPayload(){
  const el = document.getElementById('checkout-payload');
  if(!el) return null;
  let contents = [];
  let ids = [];
  try { contents = JSON.parse(el.dataset.contents || '[]'); } catch(_){ contents = []; }
  try { ids = JSON.parse(el.dataset.ids || '[]'); } catch(_){ ids = []; }
  const value = parseFloat(el.dataset.value || '0');
  const currency = el.dataset.currency || 'UAH';
  const numItems = parseInt(el.dataset.numItems || String(contents.length) || '0', 10) || contents.length;
  return { contents, content_ids: ids, value, currency, num_items: numItems };
}

function getMonoCheckoutStatus(button){
  if(!button) return null;
  const explicit = button.getAttribute('data-mono-status');
  if(explicit){
    try { return document.querySelector(explicit); } catch(_) { return null; }
  }
  const scope = button.closest('[data-mono-status-scope]') || button.closest('.vstack') || button.parentElement;
  if(scope){
    const el = scope.querySelector('[data-mono-checkout-status]');
    if(el) return el;
  }
  return null;
}

function setMonoCheckoutStatus(statusEl, type, message){
  if(!statusEl) return;
  statusEl.textContent = message || '';
  statusEl.classList.remove('error','success','text-danger','text-success');
  if(type === 'error'){
    statusEl.classList.remove('text-secondary');
    statusEl.classList.add('error','text-danger');
  } else if(type === 'success'){
    statusEl.classList.remove('text-secondary');
    statusEl.classList.add('success','text-success');
  } else {
    if(!statusEl.classList.contains('text-secondary')) statusEl.classList.add('text-secondary');
  }
}

function toggleMonoCheckoutLoading(button, isLoading){
  if(!button) return;
  if(isLoading){
    button.setAttribute('aria-busy','true');
    button.disabled = true;
    button.classList.add('loading');
  } else {
    button.removeAttribute('aria-busy');
    button.disabled = false;
    button.classList.remove('loading');
  }
}

function collectMonoCsrf(){
  const meta = document.querySelector('meta[name="csrf-token"]');
  if(meta && meta.getAttribute){
    const token = meta.getAttribute('content');
    if(token) return token;
  }
  const input = document.querySelector('[name="csrfmiddlewaretoken"]');
  if(input && 'value' in input && input.value){
    return input.value;
  }
  if(typeof getCookie === 'function'){
    return getCookie('csrftoken');
  }
  return '';
}

function resolveMonoProductContext(button){
  const context = {
    productId: null,
    size: '',
    qty: 1,
    colorVariantId: null
  };
  if(!button) return context;

  context.productId = button.getAttribute('data-product-id');

  const rootSelector = button.getAttribute('data-product-root');
  let root = null;
  if(rootSelector){
    try { root = document.querySelector(rootSelector); } catch(_) { root = null; }
  }
  if(!root) root = button.closest('[data-product-container]');
  const find = (selector)=> root ? root.querySelector(selector) : document.querySelector(selector);

  const checkedSize = find('input[name="size"]:checked');
  if(checkedSize) context.size = checkedSize.value;
  if(!context.size){
    const sizeInput = find('input[name="size"]');
    if(sizeInput) context.size = sizeInput.value;
  }
  context.size = (context.size || '').toString().trim();

  const qtyInput = find('#qty');
  if(qtyInput){
    const parsed = parseInt(qtyInput.value, 10);
    if(Number.isFinite(parsed) && parsed > 0) context.qty = parsed;
  }

  const colorActive = find('#color-picker .color-swatch.active') || document.querySelector('#color-picker .color-swatch.active');
  if(colorActive) context.colorVariantId = colorActive.getAttribute('data-variant');

  return context;
}

function addProductToCartForMono(button){
  const context = resolveMonoProductContext(button);
  const productId = context.productId;
  if(!productId) return Promise.resolve();

  const body = new URLSearchParams();
  body.append('product_id', String(productId));
  body.append('size', (context.size || 'S').toUpperCase());
  body.append('qty', String(context.qty));
  if(context.colorVariantId) body.append('color_variant_id', context.colorVariantId);

  const csrfToken = collectMonoCsrf();

  return fetch('/cart/add/', {
    method: 'POST',
    headers: {
      'X-CSRFToken': csrfToken || '',
      'X-Requested-With': 'XMLHttpRequest',
      'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
    },
    body
  })
    .then(r => {
      if(!r.ok) throw new Error('Не вдалося додати товар до кошика. Спробуйте ще раз.');
      return r.json();
    })
    .then(data => {
      if(!(data && data.ok)){
        const message = data && data.error ? data.error : 'Не вдалося додати товар до кошика. Спробуйте ще раз.';
        throw new Error(message);
      }
      try{ if(typeof data.count === 'number' && window.updateCartBadge) window.updateCartBadge(data.count); }catch(_){ }
      try{ if(window.refreshMiniCart) window.refreshMiniCart(); }catch(_){ }
      try{ if(window.refreshCartSummary) window.refreshCartSummary(); }catch(_){ }
      return data;
    });
}

function requestMonoCheckout(){
  const csrfToken = collectMonoCsrf();
  // Collect guest form fields if present (for unauthenticated users)
  const guestForm = document.getElementById('guest-form');
  let payload = {};
  const getAnyVal = (name)=>{
    const fromForm = guestForm && guestForm.querySelector(`[name="${name}"]`);
    if(fromForm && 'value' in fromForm) return (fromForm.value||'').trim();
    const anywhere = document.querySelector(`[name="${name}"]`);
    return anywhere && 'value' in anywhere ? (anywhere.value||'').trim() : '';
  };
  if(guestForm || document.querySelector('[name="full_name"]') || document.querySelector('[name="phone"]')){
    payload = {
      full_name: getAnyVal('full_name'),
      phone: getAnyVal('phone'),
      city: getAnyVal('city'),
      np_office: getAnyVal('np_office'),
      pay_type: getAnyVal('pay_type') || 'full'
    };
  }
  return fetch('/cart/monobank/quick/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken || '',
      'X-Requested-With': 'XMLHttpRequest'
    },
    credentials: 'same-origin',
    body: JSON.stringify(payload)
  }).then(response => response.json().then(data => ({data, status: response.status, ok: response.ok})).catch(() => ({data: null, status: response.status, ok: false})));
}

function requestMonoCheckoutSingleProduct(button){
  const csrfToken = collectMonoCsrf();
  const context = resolveMonoProductContext(button);

  if(!context.productId){
    return Promise.resolve({ data: { success: false, error: 'Товар недоступний.' }, status: 400, ok: false });
  }

  const payload = {
    product_id: context.productId,
    size: (context.size || 'S').toUpperCase(),
    qty: context.qty,
    single_product: true
  };
  if(context.colorVariantId) payload.color_variant_id = context.colorVariantId;
  // Include guest fields if present
  const guestForm = document.getElementById('guest-form');
  const getAnyVal = (name)=>{
    const fromForm = guestForm && guestForm.querySelector(`[name="${name}"]`);
    if(fromForm && 'value' in fromForm) return (fromForm.value||'').trim();
    const anywhere = document.querySelector(`[name="${name}"]`);
    return anywhere && 'value' in anywhere ? (anywhere.value||'').trim() : '';
  };
  if(guestForm || document.querySelector('[name="full_name"]') || document.querySelector('[name="phone"]')){
    payload.full_name = getAnyVal('full_name');
    payload.phone = getAnyVal('phone');
    payload.city = getAnyVal('city');
    payload.np_office = getAnyVal('np_office');
    payload.pay_type = getAnyVal('pay_type') || 'full';
  }

  return fetch('/cart/monobank/quick/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken || '',
      'X-Requested-With': 'XMLHttpRequest'
    },
    credentials: 'same-origin',
    body: JSON.stringify(payload)
  }).then(response => response.json().then(data => ({data, status: response.status, ok: response.ok})).catch(() => ({data: null, status: response.status, ok: false})));
}

function startMonoCheckout(button, statusEl, options){
  const opts = options || {};
  setMonoCheckoutStatus(statusEl, '', '');
  toggleMonoCheckoutLoading(button, true);

  const triggerType = button.getAttribute('data-mono-checkout-trigger');
  const isSingleProduct = triggerType === 'product';

  let requestPromise;
  if(isSingleProduct) {
    // Для кнопки в детальном товаре создаем заказ на один товар
    requestPromise = requestMonoCheckoutSingleProduct(button);
  } else {
    // Для миникорзины используем корзину
    const ensureProduct = opts.ensureProduct ? addProductToCartForMono(button) : Promise.resolve();
    requestPromise = ensureProduct.then(() => requestMonoCheckout());
  }

  return requestPromise
    .then(result => {
      const data = result.data || {};
      if(result.ok && data.success && data.redirect_url){
        setMonoCheckoutStatus(statusEl, 'success', 'Відкриваємо mono checkout…');
        const analytics = getCheckoutAnalyticsPayload();
        try{
          if(window.trackEvent && analytics){
            window.trackEvent('StartPayment', {
              value: analytics.value,
              currency: analytics.currency,
              num_items: analytics.num_items,
              payment_method: 'monobank',
              content_ids: analytics.content_ids
            });
          }
        }catch(_){ }
        window.location.href = data.redirect_url;
        return;
      }
      let message = (data && data.error) ? data.error : 'Не вдалося створити платіж. Спробуйте ще раз.';
      if(result.status === 401){
        message = 'Увійдіть, щоб скористатися mono checkout.';
      }
      setMonoCheckoutStatus(statusEl, 'error', message);
      throw new Error(message);
    })
    .catch(err => {
      if(err && err.message){
        setMonoCheckoutStatus(statusEl, 'error', err.message);
      }
    })
    .finally(() => {
      toggleMonoCheckoutLoading(button, false);
    });
}

function bindMonoCheckout(scope){
  const root = scope || document;
  const buttons = root.querySelectorAll('[data-mono-checkout-trigger]');

  buttons.forEach((button)=>{
    if(!button || button.dataset.monoCheckoutBound === '1') return;
    button.dataset.monoCheckoutBound = '1';
    const statusEl = getMonoCheckoutStatus(button);
    const triggerType = button.getAttribute('data-mono-checkout-trigger');
    button.addEventListener('click', (event)=>{
      event.preventDefault();
      if(button.disabled) return;
      const options = { ensureProduct: triggerType === 'product' };
      startMonoCheckout(button, statusEl, options);
      const analytics = getCheckoutAnalyticsPayload();
      if(analytics){
        try{
          if(window.trackEvent){
            window.trackEvent('InitiateCheckout', {
              value: analytics.value,
              currency: analytics.currency,
              num_items: analytics.num_items,
              payment_method: 'monobank',
              content_ids: analytics.content_ids,
              contents: analytics.contents
            });
          }
        }catch(_){ }
      }
    });
  });
}

// Monobank Pay (эквайринг) функции
function requestMonobankPay(){
  const csrfToken = collectMonoCsrf();
  // Collect guest form fields if present
  const guestForm = document.getElementById('guest-form');
  let payload = {};
  const getAnyVal = (name)=>{
    const fromForm = guestForm && guestForm.querySelector(`[name="${name}"]`);
    if(fromForm && 'value' in fromForm) return (fromForm.value||'').trim();
    const anywhere = document.querySelector(`[name="${name}"]`);
    return anywhere && 'value' in anywhere ? (anywhere.value||'').trim() : '';
  };
  if(guestForm || document.querySelector('[name="full_name"]') || document.querySelector('[name="phone"]')){
    payload = {
      full_name: getAnyVal('full_name'),
      phone: getAnyVal('phone'),
      city: getAnyVal('city'),
      np_office: getAnyVal('np_office'),
      pay_type: getAnyVal('pay_type') || 'full'
    };
  }
  return fetch('/cart/monobank/create-invoice/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken || '',
      'X-Requested-With': 'XMLHttpRequest'
    },
    credentials: 'same-origin',
    body: JSON.stringify(payload)
  }).then(response => response.json().then(data => ({data, status: response.status, ok: response.ok})).catch(() => ({data: null, status: response.status, ok: false})));
}

function startMonobankPay(button, statusEl){
  setMonoCheckoutStatus(statusEl, '', '');
  toggleMonoCheckoutLoading(button, true);

  return requestMonobankPay()
    .then(result => {
      const data = result.data || {};
      if(result.ok && data.success && data.invoice_url){
        setMonoCheckoutStatus(statusEl, 'success', 'Відкриваємо платіжну сторінку…');
        const analytics = getCheckoutAnalyticsPayload();
        try{
          if(window.trackEvent && analytics){
            window.trackEvent('StartPayment', {
              value: analytics.value,
              currency: analytics.currency,
              num_items: analytics.num_items,
              payment_method: 'monobank_pay',
              content_ids: analytics.content_ids
            });
          }
        }catch(_){ }
        window.location.href = data.invoice_url;
        return;
      }
      let message = (data && data.error) ? data.error : 'Не вдалося створити платіж. Спробуйте ще раз.';
      if(result.status === 401){
        message = 'Увійдіть, щоб скористатися онлайн оплатою.';
      }
      setMonoCheckoutStatus(statusEl, 'error', message);
      throw new Error(message);
    })
    .catch(err => {
      if(err && err.message){
        setMonoCheckoutStatus(statusEl, 'error', err.message);
      }
    })
    .finally(() => {
      toggleMonoCheckoutLoading(button, false);
    });
}

function bindMonobankPay(scope){
  const root = scope || document;
  root.querySelectorAll('[data-monobank-pay-trigger]').forEach((button)=>{
    if(!button || button.dataset.monobankPayBound === '1') return;
    button.dataset.monobankPayBound = '1';
    const statusEl = getMonoCheckoutStatus(button);
    button.addEventListener('click', (event)=>{
      event.preventDefault();
      if(button.disabled) return;
      startMonobankPay(button, statusEl);
      const analytics = getCheckoutAnalyticsPayload();
      if(analytics){
        try{
          if(window.trackEvent){
            window.trackEvent('InitiateCheckout', {
              value: analytics.value,
              currency: analytics.currency,
              num_items: analytics.num_items,
              payment_method: 'monobank_pay',
              content_ids: analytics.content_ids,
              contents: analytics.contents
            });
          }
        }catch(_){ }
      }
    });
  });
}


let miniCartFetchController = null;
let miniCartFetchSeq = 0;

function refreshMiniCart(){
  const panel=miniCartPanel(); if(!panel) return Promise.resolve();
  const content = panel.querySelector('#mini-cart-content') || panel.querySelector('#mini-cart-content-mobile') || panel;
  content.innerHTML = "<div class='text-secondary small'>Завантаження…</div>";

  if(typeof AbortController !== 'undefined'){
    if(miniCartFetchController){
      try{ miniCartFetchController.abort(); }catch(_){}
    }
    miniCartFetchController = new AbortController();
  } else {
    miniCartFetchController = null;
  }

  const currentSeq = ++miniCartFetchSeq;
  const controller = miniCartFetchController;

  return fetch('/cart/mini/',{
    headers:{'X-Requested-With':'XMLHttpRequest'},
    cache:'no-store',
    signal: controller ? controller.signal : undefined
  })
    .then(r=>r.text())
    .then(html=>{
      if(currentSeq !== miniCartFetchSeq) return;
      content.innerHTML = html;
      try{ applySwatchColors(content); }catch(_){ }
      try{ bindMonoCheckout(content); }catch(_){ }
    })
    .catch(err=>{
      if(controller && err && err.name === 'AbortError') return;
      if(currentSeq !== miniCartFetchSeq) return;
      content.innerHTML="<div class='text-danger small'>Не вдалося завантажити кошик</div>";
    })
    .finally(()=>{
      if(controller && miniCartFetchController === controller){
        miniCartFetchController = null;
      }
    });
}
window.refreshMiniCart = refreshMiniCart;
window.openMiniCart = openMiniCart;

// Обновляем сводку при загрузке
document.addEventListener('DOMContentLoaded',()=>{
  try{ bindMonoCheckout(document); }catch(_){ }
  try{ bindMonobankPay(document); }catch(_){ }
  // Отложим, чтобы не мешать первому рендеру
  scheduleIdle(()=>{
    refreshCartSummary();

    // Загружаем счетчик избранного для незарегистрированных пользователей
    fetch('/favorites/count/',{headers:{'X-Requested-With':'XMLHttpRequest'}})
      .then(r=>r.ok?r.json():null)
      .then(d=>{ 
        if(d&&d.count !== undefined){ 
          updateFavoritesBadge(d.count); 
        }
      })
      .catch(()=>{});
  });

  // Применим цвета для свотчей на текущей странице
  scheduleIdle(function(){ try{ applySwatchColors(document); }catch(_){ } });

  // Перемещаем галерею товара в левую колонку и синхронизируем миниатюры
  scheduleIdle(function(){
    const galleryBlock = document.querySelector('.product-gallery-block');
    const carouselEl = document.getElementById('productCarousel');
    if(!(galleryBlock && carouselEl)) return;

    // Функция: есть ли у элемента класс вида col-*
    const hasColClass = (el)=>{
      if(!el || !el.classList) return false;
      return Array.from(el.classList).some(c=>c.startsWith('col-'));
    };

    // 1) Найдём ближайшую к галерее колонку Bootstrap и её левую "соседнюю" колонку
    let currentCol = galleryBlock.closest('*');
    while(currentCol && !hasColClass(currentCol)) currentCol = currentCol.parentElement;

    let leftCol = null;
    if(currentCol && currentCol.parentElement){
      // Ищем предыдущий элемент-колонку в пределах той же строки
      let prev = currentCol.previousElementSibling;
      while(prev && !hasColClass(prev)) prev = prev.previousElementSibling;
      if(prev && hasColClass(prev)) leftCol = prev;
    }

    // Если нашли левую колонку — вставим туда галерею и удалим старое изображение
    if(leftCol){
      const oldImgWrap = leftCol.querySelector('.ratio, img');
      // Вставим галерею в начало левой колонки
      leftCol.insertBefore(galleryBlock, leftCol.firstChild);
      if(oldImgWrap) oldImgWrap.remove();
      // Удалим возможные старые полоски миниатюр в этой колонке (не входящие в нашу галерею)
      Array.from(leftCol.children)
        .filter(el => el !== galleryBlock && !galleryBlock.contains(el) && el.querySelectorAll && el.querySelectorAll('img').length >= 2)
        .forEach(el => el.remove());
    }else{
      // 2) Альтернативная цель: конкретные селекторы
      const tryLeft = document.querySelector('.row .col-12.col-md-5') || document.querySelector('.row .col-md-6');
      if(tryLeft){
        const old = tryLeft.querySelector('.ratio, img');
        tryLeft.insertBefore(galleryBlock, tryLeft.firstChild);
        if(old) old.remove();
        // Удалим возможные старые полоски миниатюр (дубликаты) в колонке
        Array.from(tryLeft.children)
          .filter(el => el !== galleryBlock && !galleryBlock.contains(el) && el.querySelectorAll && el.querySelectorAll('img').length >= 2)
          .forEach(el => el.remove());
      }else{
        // 3) Фолбэк: заменить контейнер #mainImage, если он есть
        const mainImg = document.getElementById('mainImage');
        let targetHost = null;
        if(mainImg){
          targetHost = mainImg.closest('.ratio') ? mainImg.closest('.ratio').parentElement : mainImg.parentElement;
        }
        if(targetHost && targetHost.parentElement){
          targetHost.parentElement.replaceChild(galleryBlock, targetHost);
        }
      }
    }

    // Синхронизация активной миниатюры (подсветка рамкой)
    const thumbButtons = Array.from(document.querySelectorAll('.thumb[data-bs-target="#productCarousel"]'));
    const setActiveThumb = (idx)=>{
      thumbButtons.forEach(b=>{
        const to = parseInt(b.getAttribute('data-bs-slide-to')||'-1',10);
        b.classList.toggle('active', to===idx);
      });
    };
    setActiveThumb(0);
    try{
      carouselEl.addEventListener('slid.bs.carousel', (ev)=>{
        if(typeof ev.to === 'number'){ setActiveThumb(ev.to); }
      });
    }catch(_){}
    thumbButtons.forEach(b=>{
      b.addEventListener('click', ()=>{
        const to = parseInt(b.getAttribute('data-bs-slide-to')||'-1',10);
        if(to>=0) setActiveThumb(to);
      });
    });
  });

  // Переміщення блоку «Кольори»: спочатку ПЕРЕД кнопками «Опис/Розмірна сітка», потім фолбеки
  scheduleIdle(function(){
    const card = document.getElementById('color-picker-card');
    if(!card) return;
    if(card.dataset.placed === '1') return;

    const placeBefore = (node)=>{
      if(node && node.parentElement){
        node.parentElement.insertBefore(card, node);
        card.dataset.placed = '1';
        return true;
      }
      return false;
    };
    const placeAfter = (node)=>{
      if(node && node.parentElement){
        if(node.nextSibling) node.parentElement.insertBefore(card, node.nextSibling);
        else node.parentElement.appendChild(card);
        card.dataset.placed = '1';
        return true;
      }
      return false;
    };

    // A) ПЕРВОЕ: ищем строку с кнопками (id, по .toggle-chip, по тексту)
    let togglesRow = document.getElementById('desc-size-toggles');

    if(!togglesRow){
      const chips = Array.from(document.querySelectorAll('.toggle-chip'));
      if(chips.length){
        // общий контейнер для чипов
        let cont = chips[0];
        while(cont && cont.parentElement && cont.tagName!=='DIV'){ cont = cont.parentElement; }
        togglesRow = cont || chips[0].parentElement;
      }
    }
    if(!togglesRow){
      const btns = Array.from(document.querySelectorAll('button, a, .btn')).filter(el=>{
        const t=(el.textContent||'').trim().toLowerCase();
        return t.includes('опис') || t.includes('розмірна сітка') || t.includes('розмірна') || t.includes('size');
      });
      if(btns.length){
        let cont = btns[0];
        while(cont && cont.parentElement && cont.tagName!=='DIV'){ cont = cont.parentElement; }
        togglesRow = cont || btns[0].parentElement;
      }
    }
    if(togglesRow && placeBefore(togglesRow)) return;

    // B) ВТОРОЕ: если строка кнопок не найдена — ищем контроль размера и ставим ПОСЛЕ него
    const sizeCtrl = document.querySelector('[data-size-picker]') ||
                     document.querySelector('select[name="size"]') ||
                     document.querySelector('select[name*="size" i]') ||
                     document.querySelector('[name="size"]');
    if(sizeCtrl && placeAfter(sizeCtrl)) return;

    // C) ФОЛБЕК: перед панелями опису/сітки
    const panels = document.querySelector('.panel-wrap');
    if(panels && placeBefore(panels)) return;

    // D) DOM может обновляться — наблюдаем и вставляем как только появится строка кнопок
    const observer = new MutationObserver(()=>{
      if(card.dataset.placed==='1'){ observer.disconnect(); return; }
      const row = document.getElementById('desc-size-toggles') ||
                  (document.querySelector('.toggle-chip') && document.querySelector('.toggle-chip').closest('div'));
      if(row && placeBefore(row)){ observer.disconnect(); }
    });
    observer.observe(document.body, {childList:true, subtree:true});
  });

  // Переносимо блоки з «Кольори» у «Новинках» всередину самої карточки (щоб анімація була єдиною)
  (function(){
    const dotsList = Array.from(document.querySelectorAll('.product-card-dots'));
    dotsList.forEach(dots=>{
      // Находим ближайшую карточку (попередній сусід включає card)
      let card = dots.previousElementSibling;
      if(card && !card.classList.contains('card')) card = card.closest('.card');
      if(card){
        card.style.position = card.style.position || 'relative';
        card.appendChild(dots);
      }
    });
  });

  // Тогглер мини‑корзины (и по id, и по data-атрибуту)
  const bindCartToggle = (el)=>{
    if(!el) return;
    if(el.dataset.uiBoundCart==='1') return;
    el.dataset.uiBoundCart = '1';
    el.addEventListener('pointerdown', (e)=>{ suppressNextDocPointerdownUntil = Date.now()+250; }, {passive:true});
    el.addEventListener('click', (e)=>{ e.preventDefault(); e.stopPropagation(); toggleMiniCart(); });
  };
  bindCartToggle(document.getElementById('cart-toggle'));
  bindCartToggle(document.getElementById('cart-toggle-mobile'));
  document.querySelectorAll('[data-cart-toggle]').forEach(bindCartToggle);

  // Пользовательская панель (десктоп)
  const userToggle = document.getElementById('user-toggle');
  const userPanel = document.getElementById('user-panel');
  if(userToggle && userPanel){
    const openUser=()=>{ const id=nextEvt(); userPanel._opId = (userPanel._opId||0)+1; const opId=userPanel._opId; if(userPanel._hideTimeout){ clearTimeout(userPanel._hideTimeout); userPanel._hideTimeout=null; } userPanel.classList.remove('hiding'); userPanel.classList.remove('d-none'); userPanel.removeAttribute('inert'); userPanel.setAttribute('aria-hidden','false'); void userPanel.offsetHeight; userPanel.classList.add('show'); };
    const closeUser=(reason)=>{ const id=nextEvt(); userPanel._opId = (userPanel._opId||0)+1; const opId=userPanel._opId; userPanel.classList.remove('show'); userPanel.classList.add('hiding'); const t=setTimeout(()=>{ if(opId!==userPanel._opId) return; userPanel.classList.add('d-none'); userPanel.classList.remove('hiding'); userPanel.setAttribute('inert',''); userPanel.setAttribute('aria-hidden','true'); },220); userPanel._hideTimeout=t; userPanel.addEventListener('transitionend', function onEnd(e){ if(e.target!==userPanel) return; userPanel.removeEventListener('transitionend', onEnd); if(opId!==userPanel._opId) return; clearTimeout(t); userPanel.classList.add('d-none'); userPanel.classList.remove('hiding'); userPanel.setAttribute('inert',''); userPanel.setAttribute('aria-hidden','true'); }); };
    if(!userToggle.dataset.uiBoundUser){
      userToggle.dataset.uiBoundUser = '1';
      userToggle.addEventListener('pointerdown',(e)=>{ suppressNextDocPointerdownUntil = Date.now()+250; }, {passive:true});
      userToggle.addEventListener('click',(e)=>{ const id=nextEvt(); e.preventDefault(); e.stopPropagation(); if(Date.now() < uiGuardUntil){ return;} const cartOpen = miniCartPanel() && !miniCartPanel().classList.contains('d-none'); if(cartOpen) closeMiniCart('userToggle'); if(userPanel.classList.contains('d-none') || !userPanel.classList.contains('show')){ openUser(); } else { closeUser('userToggle'); } suppressGlobalCloseUntil = Date.now() + 220; });
    }
    document.addEventListener('pointerdown',(e)=>{ const id=nextEvt(); const tgt = e.target; const state = panelState(); const supNext = Date.now() < suppressNextDocPointerdownUntil; const supGlob = Date.now() < suppressGlobalCloseUntil; const outside = !userPanel.contains(tgt) && !userToggle.contains(tgt); if(supNext || supGlob) return; if(userPanel.classList.contains('d-none')) return; if(outside){ closeUser('docOutside'); }}, {passive:true});
    const uc = document.querySelector('[data-user-close]'); if(uc){ uc.addEventListener('click',(e)=>{ e.preventDefault(); closeUser();}); }
    document.addEventListener('keydown',(e)=>{ if(e.key==='Escape') closeUser(); });
  }

  // Пользовательская панель (мобильная)
  const userToggleMobile = document.getElementById('user-toggle-mobile');
  const userPanelMobile = document.getElementById('user-panel-mobile');
  if(userToggleMobile && userPanelMobile){
    const openUserMobile=()=>{ const id=nextEvt(); userPanelMobile._opId=(userPanelMobile._opId||0)+1; const opId=userPanelMobile._opId; if(userPanelMobile._hideTimeout){ clearTimeout(userPanelMobile._hideTimeout); userPanelMobile._hideTimeout=null; } userPanelMobile.classList.remove('hiding'); userPanelMobile.classList.remove('d-none'); userPanelMobile.removeAttribute('inert'); userPanelMobile.setAttribute('aria-hidden','false'); void userPanelMobile.offsetHeight; userPanelMobile.classList.add('show'); };
    const closeUserMobile=(reason)=>{ const id=nextEvt(); userPanelMobile._opId=(userPanelMobile._opId||0)+1; const opId=userPanelMobile._opId; userPanelMobile.classList.remove('show'); userPanelMobile.classList.add('hiding'); const t=setTimeout(()=>{ if(opId!==userPanelMobile._opId) return; userPanelMobile.classList.add('d-none'); userPanelMobile.classList.remove('hiding'); userPanelMobile.setAttribute('inert',''); userPanelMobile.setAttribute('aria-hidden','true'); },220); userPanelMobile._hideTimeout=t; userPanelMobile.addEventListener('transitionend', function onEnd(e){ if(e.target!==userPanelMobile) return; userPanelMobile.removeEventListener('transitionend', onEnd); if(opId!==userPanelMobile._opId) return; clearTimeout(t); userPanelMobile.classList.add('d-none'); userPanelMobile.classList.remove('hiding'); userPanelMobile.setAttribute('inert',''); userPanelMobile.setAttribute('aria-hidden','true'); }); };
    if(!userToggleMobile.dataset.uiBoundUser){
      userToggleMobile.dataset.uiBoundUser = '1';
      userToggleMobile.addEventListener('pointerdown',(e)=>{ suppressNextDocPointerdownUntil = Date.now()+250; }, {passive:true});
      userToggleMobile.addEventListener('click',(e)=>{ const id=nextEvt(); e.preventDefault(); e.stopPropagation(); if(Date.now() < uiGuardUntil){ return;} const cartOpen = miniCartPanel() && !miniCartPanel().classList.contains('d-none'); if(cartOpen) closeMiniCart('userToggleMobile'); if(userPanelMobile.classList.contains('d-none') || !userPanelMobile.classList.contains('show')){ openUserMobile(); } else { closeUserMobile('userToggleMobile'); } suppressGlobalCloseUntil = Date.now() + 220; });
    }
    document.addEventListener('pointerdown',(e)=>{ const id=nextEvt(); const tgt=e.target; const state=panelState(); const supNext= Date.now() < suppressNextDocPointerdownUntil; const supGlob= Date.now() < suppressGlobalCloseUntil; const outside = !userPanelMobile.contains(tgt) && !userToggleMobile.contains(tgt); if(supNext || supGlob) return; if(userPanelMobile.classList.contains('d-none')) return; if(outside){ closeUserMobile('docOutside'); }}, {passive:true});
    const ucMobile = userPanelMobile.querySelector('[data-user-close-mobile]'); if(ucMobile){ ucMobile.addEventListener('click',(e)=>{ e.preventDefault(); closeUserMobile();}); }
    document.addEventListener('keydown',(e)=>{ if(e.key==='Escape') closeUserMobile(); });
  }

  // Кнопка закрытия мини‑кошика
  const hookClose = ()=> {
    const c = document.querySelector('[data-cart-close]');
    const cMobile = document.querySelector('[data-cart-close-mobile]');
    if(c){ c.addEventListener('click', (e)=>{ e.preventDefault(); closeMiniCart(); }); }
    if(cMobile){ cMobile.addEventListener('click', (e)=>{ e.preventDefault(); closeMiniCart(); }); }
  };
  hookClose();

  // Закрытие по клику снаружи
  document.addEventListener('pointerdown',(e)=>{
    const id=nextEvt();
    const supNext = Date.now() < suppressNextDocPointerdownUntil;
    if(supNext){ return; }
    const supGuard = Date.now() < uiGuardUntil;
    const supGlob = Date.now() < suppressGlobalCloseUntil;
    const panel=miniCartPanel();
    const toggle=window.innerWidth < 576 ? 
      document.getElementById('cart-toggle-mobile') : 
      document.getElementById('cart-toggle') || document.querySelector('[data-cart-toggle]');
    if(!panel) return;
    if(panel.classList.contains('d-none')) return;
    const tgt = e.target;
    const outside = !panel.contains(tgt) && (!toggle || !toggle.contains(tgt));
    if(supGuard || supGlob) return;
    if(outside){
      closeMiniCart('docOutside');
    }
  }, {passive:true});
  // Закрытие по ESC
  document.addEventListener('keydown',(e)=>{ if(e.key==='Escape') closeMiniCart(); });

  // Адаптация при ресайзе
  window.addEventListener('resize', debounce(()=>{
    const panel=miniCartPanel();
    if(panel && !panel.classList.contains('d-none')){
      // пересчитать позиционирование, сохраняя анимационные классы
      const wasShown = panel.classList.contains('show');
      if(wasShown) panel.classList.remove('show');
      // режим позиционирования
      if(window.innerWidth < 576){
        panel.classList.add('position-fixed','top-0','start-0','vw-100','vh-100','rounded-0');
        panel.style.right = '';
        panel.style.top = '0';
      }else{
        panel.classList.remove('position-fixed','top-0','start-0','vw-100','vh-100','rounded-0');
        panel.style.right = '0';
        panel.style.top = 'calc(100% + 8px)';
      }
      if(wasShown){
        if('requestAnimationFrame' in window){
          requestAnimationFrame(()=> panel.classList.add('show'));
        } else {
          panel.classList.add('show');
        }
      }
    }
  }, 150));

  // ===== Мобильное нижнее меню: скрытие/показ по скроллу, фокусу и свайпу =====
  (function(){
    const bottomNav = document.querySelector('.bottom-nav');
    if(!bottomNav) return;

    let lastScrollY = PerformanceOptimizer.getScrollY();
    let hidden = false;
    let hintShown = sessionStorage.getItem('bottom-nav-hint') === '1';
    let touchStartY = null;
    let touchStartX = null;
    let touchMoved = false;

    const setHidden = (v)=>{
      if(hidden === v) return;
      hidden = v;
      // Используем batch operations для предотвращения reflow
      PerformanceOptimizer.batchDOMOperations([
        () => bottomNav.classList.toggle('bottom-nav--hidden', hidden)
      ]);
    };

    const maybeShowHint = ()=>{
      if(hintShown) return;
      if(prefersReducedMotion || PERF_LITE) { hintShown = true; return; }
      bottomNav.classList.add('hint-wiggle');
      setTimeout(()=> bottomNav.classList.remove('hint-wiggle'), 950);
      sessionStorage.setItem('bottom-nav-hint','1');
      hintShown = true;
    };

    // Оптимизированная обработка скролла с использованием PerformanceOptimizer
    PerformanceOptimizer.onScrollChange = (currentY, lastY) => {
      const dy = currentY - lastY;
      const threshold = 6;
      if(dy > threshold) setHidden(true);
      else if(dy < -threshold) setHidden(false);
    };
    
    // Инициализируем оптимизированный скролл
    PerformanceOptimizer.initScrollOptimization();

    // Фокус в полях ввода — скрыть; блюр — показать
    document.addEventListener('focusin', (e)=>{
      if(e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable)){
        setHidden(true);
      }
    });
    document.addEventListener('focusout', (e)=>{
      if(e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable)){
        setHidden(false);
        maybeShowHint();
      }
    });

    // Свайпы по самому нижнему меню и по странице: вниз — скрыть, вверх — показать
    const onTouchStart = (e)=>{
      const t = e.touches ? e.touches[0] : e;
      touchStartY = t.clientY;
      touchStartX = t.clientX;
      touchMoved = false;
    };
    const onTouchMove = (e)=>{
      touchMoved = true;
    };
    const onTouchEnd = (e)=>{
      if(touchStartY == null) return;
      const t = (e.changedTouches && e.changedTouches[0]) || e;
      const dy = (t.clientY - touchStartY) || 0;
      const dx = (t.clientX - touchStartX) || 0;
      const absY = Math.abs(dy), absX = Math.abs(dx);
      // вертикальный жест с минимальным порогом и явным преобладанием вертикали
      if(absY > 20 && absY > absX * 1.4){
        if(dy > 0) setHidden(true); else setHidden(false);
        maybeShowHint();
      }
      touchStartY = touchStartX = null;
      touchMoved = false;
    };
    // Навешиваем и на меню, и глобально (на случай свайпов с контента)
    bottomNav.addEventListener('touchstart', onTouchStart, {passive:true});
    bottomNav.addEventListener('touchmove', onTouchMove, {passive:true});
    bottomNav.addEventListener('touchend', onTouchEnd, {passive:true});
    document.addEventListener('touchstart', onTouchStart, {passive:true});
    document.addEventListener('touchmove', onTouchMove, {passive:true});
    document.addEventListener('touchend', onTouchEnd, {passive:true});

    // Первичная ненавязчивая подсказка — один раз за сессию
    setTimeout(()=>{ maybeShowHint(); }, 800);
  })();
});

// Runtime diagnostics removed for production

// ===== Авто-оптимизация тяжёлых эффектов без изменения вида =====
document.addEventListener('DOMContentLoaded', function(){
  if(!(PERF_LITE || prefersReducedMotion)) return;
  scheduleIdle(()=>{
    const candidateSelectors = [
      '.hero.bg-hero', '.bottom-nav', '#mini-cart-panel-mobile', '#user-panel-mobile',
      '.featured-bg-unified', '.categories-bg-unified', '.card.product',
      '[class*="particles" i]', '[class*="spark" i]', '[class*="glow" i]'
    ];
    const unique = new Set();
    const candidates = [];
    candidateSelectors.forEach(sel=>{
      document.querySelectorAll(sel).forEach(el=>{
        if(!el || unique.has(el)) return; unique.add(el); candidates.push(el);
      });
    });

    const heavyMeta = [];
    const metaMap = new Map();
    candidates.forEach(el=>{
      try{
        const cs = DOMCache.getComputedStyle(el);
        const hasBackdrop = (cs.backdropFilter && cs.backdropFilter!=='none') || (cs.webkitBackdropFilter && cs.webkitBackdropFilter!=='none');
        const hasBlur = (cs.filter||'').includes('blur');
        const hasBigShadow = (cs.boxShadow||'').includes('px');
        const isAnimatedInf = (cs.animationIterationCount||'').includes('infinite');
        if(hasBackdrop || hasBlur || hasBigShadow || isAnimatedInf){
          const meta = { el, hasBackdrop, hasInfiniteAnim: isAnimatedInf };
          heavyMeta.push(meta);
          metaMap.set(el, meta);
        }
      }catch(_){ }
    });

    if(!heavyMeta.length) return;

    let relaxTimer = null;
    let relaxed = false;
    function relaxHeavy(){
      if(relaxed) return; relaxed = true;
      heavyMeta.forEach(({el, hasBackdrop, hasInfiniteAnim})=>{
        try{
          if(hasBackdrop){
            el.style.setProperty('backdrop-filter','blur(6px) saturate(110%)','important');
            el.style.setProperty('-webkit-backdrop-filter','blur(6px) saturate(110%)','important');
          }
          if(hasInfiniteAnim){
            el.style.setProperty('animation-play-state','paused','important');
          }
        }catch(_){ }
      });
    }
    function restoreHeavy(){
      if(!relaxed) return; relaxed = false;
      heavyMeta.forEach(({el})=>{
        try{
          el.style.removeProperty('backdrop-filter');
          el.style.removeProperty('-webkit-backdrop-filter');
          el.style.removeProperty('animation-play-state');
        }catch(_){ }
      });
    }
    function onScroll(){
      relaxHeavy();
      if(relaxTimer) clearTimeout(relaxTimer);
      relaxTimer = setTimeout(restoreHeavy, 350);
    }
    window.addEventListener('scroll', onScroll, {passive:true});

    if('IntersectionObserver' in window){
      const io = new IntersectionObserver(entries=>{
        PerformanceOptimizer.batchDOMOperations(
          entries.map(entry => () => {
            const meta = metaMap.get(entry.target);
            if(!meta || !meta.hasInfiniteAnim) return;
            try{
              entry.target.style.setProperty('animation-play-state', entry.isIntersecting ? 'running' : 'paused','important');
            }catch(_){ }
          })
        );
      },{threshold:0.05});
      heavyMeta.forEach(({el})=>{ try{ io.observe(el); }catch(_){ } });
    }
  });
});


// Делегирование клика "добавить в корзину"
document.addEventListener('click', (e)=>{
  const btn = e.target.closest('[data-add-to-cart]');
  if(!btn) return;
    // Если на кнопке есть inline-обработчик (AddToCart), не дублируем запрос
    if(btn.hasAttribute('onclick')) return;
  e.preventDefault();
  const productId = btn.getAttribute('data-add-to-cart');
  const sizeInput = document.querySelector('input[name="size"]:checked');
  const size = sizeInput ? sizeInput.value : '';
  
  // Получаем выбранный цвет
  let colorVariantId = null;
  const activeColorSwatch = document.querySelector('#color-picker .color-swatch.active');
  if(activeColorSwatch) {
    colorVariantId = activeColorSwatch.getAttribute('data-variant');
  }
  
  const body = new URLSearchParams({product_id: productId, size: size});
  if(colorVariantId) {
    body.append('color_variant_id', colorVariantId);
  }
  
  // Открываем мини-корзину сразу, чтобы пользователь видел текущее состояние
  try{ openMiniCart({skipRefresh:true}); }catch(_){ }

  fetch('/cart/add/',{
    method:'POST',
    headers:{
      'X-CSRFToken': getCookie('csrftoken'),
      'X-Requested-With':'XMLHttpRequest',
      'Content-Type':'application/x-www-form-urlencoded;charset=UTF-8'
    },
    body
  })
  .then(r=>r.json())
  .then(d=>{
    if(d && d.ok){
      if(typeof d.count === 'number'){ updateCartBadge(d.count); }
      const miniUpdate = refreshMiniCart();
      miniUpdate
        .then(()=>{ openMiniCart({skipRefresh:true}); })
        .catch(()=>{ openMiniCart({skipRefresh:true}); })
        .finally(()=>{ refreshCartSummary(); });
      try{ if(window.fbq){ fbq('track','AddToCart',{content_ids:[String(productId)], content_type:'product'}); } }catch(_){ }
      // Небольшой визуальный отклик
      btn.classList.add('btn-success');
      setTimeout(()=>btn.classList.remove('btn-success'),400);
      // Унифицированный трекинг AddToCart
      try{
        if(window.trackEvent){
          window.trackEvent('AddToCart', {
            content_ids: [String(productId)],
            content_type: 'product',
            value: d && d.total ? Number(d.total) : undefined,
            currency: 'UAH'
          });
        }
      }catch(_){ }
    } else {
      btn.classList.add('btn-danger');
      setTimeout(()=>btn.classList.remove('btn-danger'),600);
    }
  })
  .catch(()=>{
    btn.classList.add('btn-danger');
    setTimeout(()=>btn.classList.remove('btn-danger'),600);
  });
});

// ===== Функциональность скрытия блока "Рекомендовано" =====
document.addEventListener('DOMContentLoaded', function() {
  const featuredToggle = document.getElementById('featuredToggle') || document.getElementById('featured-toggle');
  const featuredContent = document.getElementById('featured-content');
  if (!featuredToggle || !featuredContent) return;

  const getState = ()=>{
    const collapsedKey = localStorage.getItem('featuredCollapsed');
    const hiddenKey = localStorage.getItem('featured-hidden');
    if(collapsedKey !== null) return collapsedKey === 'true';
    if(hiddenKey !== null) return hiddenKey === 'true';
    return false;
  };
  const setState = (collapsed)=>{
    localStorage.setItem('featuredCollapsed', collapsed ? 'true' : 'false');
    localStorage.setItem('featured-hidden', collapsed ? 'true' : 'false');
  };
  const applyState = (collapsed)=>{
    featuredContent.style.display = collapsed ? 'none' : 'block';
    featuredContent.classList.toggle('collapsed', collapsed);
    featuredToggle.classList.toggle('collapsed', collapsed);
    const hint = featuredToggle.querySelector('.toggle-hint-text') || featuredToggle.querySelector('.toggle-text');
    if(hint) hint.textContent = collapsed ? 'Показати' : 'Сховати';
    const icon = featuredToggle.querySelector('.toggle-icon svg');
    if(icon) icon.style.transform = collapsed ? 'rotate(180deg)' : 'rotate(0deg)';
    featuredToggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
  };

  applyState(getState());
  featuredToggle.addEventListener('click', function() {
    featuredToggle.classList.add('pulsing');
    setTimeout(() => featuredToggle.classList.remove('pulsing'), 600);
    const collapsedNext = featuredContent.style.display !== 'none';
    applyState(collapsedNext);
    setState(collapsedNext);
  });
});

// ===== Выравнивание карточек по высоте (общая инициализация) =====
document.addEventListener('DOMContentLoaded', function(){
  const rows = document.querySelectorAll('.row[data-stagger-grid]');
  if(!rows.length) return;
  const equalizeMq = window.matchMedia('(min-width: 768px)');
  let eqScheduled = false;
  function equalizeCardHeights(){
    if(eqScheduled) return;
    eqScheduled = true;
    const run = ()=>{
      rows.forEach(row=>{
        const cards = row.querySelectorAll('.card.product');
        if(!cards.length) return;
        if(!equalizeMq.matches){
          if(row.dataset.eqHeight){ delete row.dataset.eqHeight; }
          cards.forEach(card=>{
            card.style.height='';
            card.style.minHeight='';
            card.style.maxHeight='';
          });
          return;
        }
        const rowDisplay = window.getComputedStyle(row).display;
        if(rowDisplay === 'grid'){
          if(row.dataset.eqHeight){ delete row.dataset.eqHeight; }
          cards.forEach(card=>{
            card.style.height='';
            card.style.minHeight='';
            card.style.maxHeight='';
          });
          return;
        }
        let maxHeight = 0;
        cards.forEach(card=>{
          const h = card.getBoundingClientRect().height;
          if(h > maxHeight) maxHeight = h;
        });
        const target = String(Math.ceil(maxHeight));
        if(row.dataset.eqHeight === target) return;
        row.dataset.eqHeight = target;
        const px = target + 'px';
        cards.forEach(card=>{
          card.style.minHeight = px;
          card.style.maxHeight = '';
          card.style.height = '';
        });
      });
      eqScheduled = false;
    };
    if('requestAnimationFrame' in window){ requestAnimationFrame(run); }
    else { setTimeout(run, 0); }
  }
  window.equalizeCardHeights = equalizeCardHeights;
  equalizeCardHeights();
  window.addEventListener('load', equalizeCardHeights);
  const debouncedEqualize = debounce(equalizeCardHeights, 160);
  window.addEventListener('resize', debouncedEqualize);
  const mqHandler = ()=> debouncedEqualize();
  if(equalizeMq.addEventListener){ equalizeMq.addEventListener('change', mqHandler); }
  else if(equalizeMq.addListener){ equalizeMq.addListener(mqHandler); }
});

// ====== PRODUCT DETAIL: цвета и галерея ======
document.addEventListener('DOMContentLoaded', function(){
  const variantTag = document.getElementById('variant-data');
  const colorPicker = document.getElementById('color-picker');
  const carousel = document.getElementById('productCarousel');
  if(!variantTag || !colorPicker || !carousel) return;
  let variants=[]; try{ variants=JSON.parse(variantTag.textContent||'[]'); }catch(_){ variants=[]; }
  const inner = carousel.querySelector('.carousel-inner');
  const indicators = carousel.querySelector('.carousel-indicators');
  const thumbs = document.getElementById('product-thumbs');
  function rebuild(images){ if(!(inner&&indicators&&thumbs)) return; inner.innerHTML=''; indicators.innerHTML=''; thumbs.innerHTML=''; const mainImg = document.getElementById('mainImage'); const fallbackSrc = mainImg ? mainImg.src : ''; const list=(images&&images.length)?images:[fallbackSrc]; list.forEach((url,idx)=>{ const item=document.createElement('div'); item.className='carousel-item'+(idx===0?' active':''); item.innerHTML='<img src="'+url+'" class="d-block w-100 h-100 object-fit-contain" alt="Фото товару">'; inner.appendChild(item); const ind=document.createElement('button'); ind.type='button'; ind.setAttribute('data-bs-target','#productCarousel'); ind.setAttribute('data-bs-slide-to', String(idx)); if(idx===0){ ind.className='active'; ind.setAttribute('aria-current','true'); } indicators.appendChild(ind); const th=document.createElement('button'); th.type='button'; th.className='btn p-0 thumb'; th.setAttribute('data-bs-target','#productCarousel'); th.setAttribute('data-bs-slide-to', String(idx)); th.innerHTML='<img src="'+url+'" class="rounded-3 object-fit-cover" style="width:72px;height:72px;" alt="Мініатюра">'; thumbs.appendChild(th); }); }
  function onColorClick(btn){ const id=parseInt(btn.getAttribute('data-variant')||'-1',10); const v=variants.find(x=>x.id===id); if(!v) return; colorPicker.querySelectorAll('.color-swatch').forEach(b=>b.classList.remove('active')); btn.classList.add('active'); rebuild(v.images||[]); }
  if(variants.length){ const def=variants.find(v=>v.is_default)||variants[0]; rebuild(def&&def.images?def.images:[]); }
  colorPicker.querySelectorAll('.color-swatch').forEach(b=> b.addEventListener('click', ()=> onColorClick(b)) );
  // Points info modal binding
  const pointsInfoModal = document.getElementById('pointsInfoModal');
  if(pointsInfoModal){ pointsInfoModal.addEventListener('show.bs.modal', function(event){ const button=event.relatedTarget; if(!button) return; const title=button.getAttribute('data-product-title'); const points=button.getAttribute('data-points-amount'); const t=document.getElementById('modalProductTitle'); const p=document.getElementById('modalPointsAmount'); if(t) t.textContent=title||''; if(p) p.textContent=points||'0'; }); }
});

// ====== CONTACTS: показать телефон ======
document.addEventListener('DOMContentLoaded', function(){
  const btn=document.getElementById('show-phone-btn'); const phone=document.getElementById('phone-number'); if(btn&&phone){ btn.addEventListener('click', ()=>{ phone.style.display='inline-block'; btn.style.display='none'; }); }
});

// ===== ФУНКЦИИ ДЛЯ ИЗБРАННЫХ ТОВАРОВ =====

// Функция для переключения избранного
function toggleFavorite(productId, button) {
  if (!button) return;
  
  // Показываем индикатор загрузки
  button.classList.add('loading');
  
  fetch(`/favorites/toggle/${productId}/`, {
    method: 'POST',
    headers: {
      'X-CSRFToken': getCookie('csrftoken'),
      'Content-Type': 'application/json',
    },
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      // Обновляем состояние кнопки
      if (data.is_favorite) {
        button.classList.add('is-favorite');
        try{ if(window.trackEvent){ window.trackEvent('AddToWishlist', {content_ids:[String(productId)], content_type:'product'}); } }catch(_){ }
      } else {
        button.classList.remove('is-favorite');
        try{ if(window.trackEvent){ window.trackEvent('RemoveFromWishlist', {content_ids:[String(productId)], content_type:'product'}); } }catch(_){ }
      }
      
      // Обновляем счетчик избранного
      if (data.favorites_count !== undefined) {
        updateFavoritesBadge(data.favorites_count);
      }
      
      // Показываем уведомление
      showNotification(data.message, 'success');
    } else {
      showNotification(data.message || 'Помилка', 'error');
    }
  })
  .catch(error => {
    console.error('Error:', error);
          showNotification('Помилка з\'єднання', 'error');
  })
  .finally(() => {
    // Восстанавливаем кнопку
    button.classList.remove('loading');
  });
}

// Функция для проверки статуса избранного
function checkFavoriteStatus(productId, button) {
  if (!button) return;
  
  fetch(`/favorites/check/${productId}/`)
  .then(response => response.json())
  .then(data => {
    if (data.is_favorite) {
      button.classList.add('is-favorite');
    } else {
      button.classList.remove('is-favorite');
    }
  })
  .catch(error => {
    console.error('Error checking favorite status:', error);
  });
}

// Функция для показа уведомлений
function showNotification(message, type = 'info') {
  // Создаем элемент уведомления
  const notification = document.createElement('div');
  notification.className = `notification notification-${type}`;
  notification.innerHTML = `
    <div class="notification-content">
      <span class="notification-message">${message}</span>
      <button class="notification-close" onclick="this.parentElement.parentElement.remove();">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
          <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
        </svg>
      </button>
    </div>
  `;
  
  // Добавляем в body
  document.body.appendChild(notification);
  
  // Показываем с анимацией
  setTimeout(() => {
    notification.classList.add('show');
  }, 100);
  
  // Автоматически скрываем через 3 секунды
  setTimeout(() => {
    notification.classList.remove('show');
    setTimeout(() => {
      if (notification.parentElement) {
        notification.remove();
      }
    }, 300);
  }, 3000);
}

// Инициализация статуса избранного для всех кнопок при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
  const favoriteButtons = document.querySelectorAll('.favorite-btn');
  if(!favoriteButtons.length) return;
  // Ленивая проверка статуса избранного — только при появлении в вьюпорте
  if('IntersectionObserver' in window){
    const io = new IntersectionObserver(entries=>{
      entries.forEach(entry=>{
        if(!entry.isIntersecting) return;
        const button = entry.target;
        const productId = button.getAttribute('data-product-id');
        if (productId) { checkFavoriteStatus(productId, button); }
        io.unobserve(button);
      });
    }, {root:null, rootMargin:'100px 0px', threshold:0.01});
    favoriteButtons.forEach(btn=> io.observe(btn));
  } else {
    // Фолбэк: проверяем сразу
    favoriteButtons.forEach(button => {
      const productId = button.getAttribute('data-product-id');
      if (productId) { checkFavoriteStatus(productId, button); }
    });
  }
});

// ===== ФУНКЦИОНАЛЬНОСТЬ СВОРАЧИВАНИЯ КАТЕГОРИЙ =====
document.addEventListener('DOMContentLoaded', function() {
  const categoriesToggle = document.getElementById('categoriesToggle');
  const categoriesContainer = document.getElementById('categoriesContainer');
  const toggleText = categoriesToggle?.querySelector('.toggle-text');
  
  if (!categoriesToggle || !categoriesContainer || !toggleText) return;
  
  // Проверяем сохраненное состояние
  const isCollapsed = localStorage.getItem('categories-collapsed') === 'true';
  
  if (isCollapsed) {
    categoriesContainer.classList.add('collapsed');
    categoriesToggle.classList.add('collapsed');
    toggleText.textContent = 'Развернуть';
  }
  
  categoriesToggle.addEventListener('click', function() {
    const isCollapsed = categoriesContainer.classList.contains('collapsed');
    
    // Добавляем эффект пульсации кнопки
    categoriesToggle.classList.add('pulsing');
    setTimeout(() => categoriesToggle.classList.remove('pulsing'), 600);
    
    if (isCollapsed) {
      // Разворачиваем блок
      categoriesContainer.classList.remove('collapsed');
      categoriesToggle.classList.remove('collapsed');
      toggleText.textContent = 'Свернуть';
      localStorage.setItem('categories-collapsed', 'false');
      
      // Анимация появления
      categoriesContainer.style.display = 'block';
      void categoriesContainer.offsetHeight; // Форсируем reflow
      categoriesContainer.classList.add('expanding');
      
      // Убираем класс анимации после завершения
      setTimeout(() => {
        categoriesContainer.classList.remove('expanding');
      }, 800);
      
    } else {
      // Сворачиваем блок
      categoriesContainer.classList.add('collapsing');
      categoriesToggle.classList.add('collapsed');
      toggleText.textContent = 'Развернуть';
      localStorage.setItem('categories-collapsed', 'true');
      
      // Анимация скрытия
      setTimeout(() => {
        categoriesContainer.classList.remove('collapsing');
        categoriesContainer.classList.add('collapsed');
        categoriesContainer.style.display = 'none';
      }, 800);
    }
  });
});

// Поиск в шапке
document.addEventListener('DOMContentLoaded', function(){
  const headerSearch = document.querySelector('form[role="search"] input[name="q"]');
  if(headerSearch){
    headerSearch.addEventListener('search', function(){
      const term = (headerSearch.value||'').trim();
      if(term){ try{ if(window.trackEvent){ window.trackEvent('Search', {search_string: term}); } }catch(_){ } }
    });
    headerSearch.form && headerSearch.form.addEventListener('submit', function(){
      const term = (headerSearch.value||'').trim();
      if(term){ try{ if(window.trackEvent){ window.trackEvent('Search', {search_string: term}); } }catch(_){ } }
    });
  }
});

// Трекинг выбора отделения НП (поле np_office в корзине/чекауте)
document.addEventListener('input', function(e){
  const el = e.target;
  if(!el || el.name !== 'np_office') return;
  const val = (el.value||'').trim();
  if(val && val.length >= 3){
    try{ if(window.trackEvent){ window.trackEvent('FindLocation', {query: val}); } }catch(_){ }
  }
});

// ViewContent на листингах — по клику на любую область карточки
document.addEventListener('click', function(e){
  try{
    const card = e.target.closest && e.target.closest('.card.product');
    if(!card) return;
    const pid = card.getAttribute('data-product-id');
    const title = card.getAttribute('data-product-title');
    if(pid && window.trackEvent){
      window.trackEvent('ViewContent', {content_ids:[String(pid)], content_type:'product', content_name: title});
    }
  }catch(_){ }
});

// Цветовые точки, корзина и пагинация подгружаются по требованию, чтобы сократить работу в главном потоке
document.addEventListener('DOMContentLoaded', () => {
  scheduleIdle(() => {
    if(document.querySelector('.product-card-wrap') || document.getElementById('productCarousel')){
      import('./modules/product-media.js')
        .then(({ initProductMedia }) => initProductMedia())
        .catch(() => {});
    }
    if(document.querySelector('.cart-page-container') || document.getElementById('promo-code-input')){
      import('./modules/cart.js')
        .then(({ initCartInteractions }) => initCartInteractions())
        .catch(() => {});
    }
    if(document.getElementById('load-more-btn') || document.getElementById('products-container')){
      import('./modules/homepage.js')
        .then(({ initHomepagePagination }) => initHomepagePagination())
        .catch(() => {});
    }
  });
});
