// Анимации появления
const io=new IntersectionObserver(e=>{e.forEach(t=>{if(t.isIntersecting){t.target.classList.add('visible');io.unobserve(t.target)}})},{threshold:.12});
document.addEventListener('DOMContentLoaded',()=>{
  // Обычные лёгкие появления
  document.querySelectorAll('.reveal, .reveal-fast').forEach(el=>io.observe(el));
  
  // Стаггер-анимация карточек в гриде — добавляем .visible по очереди
  const gridObserver = new IntersectionObserver(entries=>{
    entries.forEach(entry=>{
      if(!entry.isIntersecting) return;
      const grid = entry.target;
      const items = Array.from(grid.querySelectorAll('.stagger-item'));
      // Сортировка сверху-вниз, слева-направо
      const ordered = items
        .map(el=>({el,rect:el.getBoundingClientRect()}))
        .sort((a,b)=> (a.rect.top - b.rect.top) || (a.rect.left - b.rect.left))
        .map(x=>x.el);

      const step = 190; // шаг задержки между карточками (мс) — заметно по очереди
      ordered.forEach((el,i)=>{
        el.style.setProperty('--d', (i*step)+'ms'); // дублируем задержку в CSS (на всякий)
        setTimeout(()=>{ 
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
              }, dotIndex * 60); // Быстрая анимация точек
            });
          }
        }, i*step);
      });

      gridObserver.unobserve(grid);
    });
  },{threshold:.2, rootMargin:'0px 0px -10% 0px'});
  document.querySelectorAll('[data-stagger-grid]').forEach(grid=>gridObserver.observe(grid));
});

// ===== Корзина (AJAX) =====
// Временный дебаггер UI: включается локально через localStorage `ui-debug` = '1'
const UI_DEBUG = true; // временно всегда включено для локального дебага
const dlog = (...args)=>{ try{ console.log('[UI]', ...args);}catch(_){} };
let uiEventSeq = 0;
const nextEvt = ()=> (++uiEventSeq);
const nowTs = ()=> Date.now();
const panelState = ()=>({
  userShown: !(document.getElementById('user-panel')||{classList:{contains:()=>true}}).classList.contains('d-none'),
  userMobileShown: !(document.getElementById('user-panel-mobile')||{classList:{contains:()=>true}}).classList.contains('d-none'),
  cartShown: !(miniCartPanel()||{classList:{contains:()=>true}}).classList.contains('d-none')
});
function getCookie(name){
  const m=document.cookie.match('(^|;)\\s*'+name+'\\s*=\\s*([^;]+)');
  return m?decodeURIComponent(m.pop()):'';
}
function updateCartBadge(count){
  const n = String(count||0);
  const desktop=document.getElementById('cart-count');
  const mobile=document.getElementById('cart-count-mobile');
  if(desktop){ desktop.textContent=n; desktop.style.display='inline-block'; }
  if(mobile){ mobile.textContent=n; mobile.style.display='inline-block'; }
}

// Мини‑корзина
function miniCartPanel(){ 
  if(window.innerWidth < 576){
    return document.getElementById('mini-cart-panel-mobile');
  } else {
    return document.getElementById('mini-cart-panel');
  }
}
// Небольшая защита от мгновенного закрытия при переключении панелей
let uiGuardUntil = 0;
let suppressGlobalCloseUntil = 0;
let suppressNextDocPointerdownUntil = 0; // блокируем ближайший pointerdown от документа (клик по тогглеру)
function openMiniCart(){
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
  // Ре-флоу для анимации
  void panel.offsetHeight;
  panel.classList.add('show');
  uiGuardUntil = Date.now() + 220;
  suppressGlobalCloseUntil = Date.now() + 180;
  dlog('openMiniCart', {id, uiGuardUntil, suppressGlobalCloseUntil, state: panelState()});
  refreshMiniCart();
}
function closeMiniCart(reason){
  const id=nextEvt();
  const panel=miniCartPanel(); if(!panel) return;
  panel._opId = (panel._opId||0)+1; const opId = panel._opId;
  dlog('closeMiniCart', {id, reason: reason||'', now: nowTs(), state: panelState()});
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
    dlog('closeMiniCart:transitionend', {id});
  });
}
function toggleMiniCart(){
  const panel=miniCartPanel(); if(!panel) return;
  if(panel.classList.contains('d-none') || !panel.classList.contains('show')) openMiniCart(); else closeMiniCart();
}
function refreshMiniCart(){
  const panel=miniCartPanel(); if(!panel) return;
  const content = panel.querySelector('#mini-cart-content') || panel.querySelector('#mini-cart-content-mobile') || panel;
  content.innerHTML = "<div class='text-secondary small'>Завантаження…</div>";
  fetch('/cart/mini/',{headers:{'X-Requested-With':'XMLHttpRequest'}})
    .then(r=>r.text())
    .then(html=>{ content.innerHTML = html; })
    .catch(()=>{ content.innerHTML="<div class='text-danger small'>Не вдалося завантажити кошик</div>"; });
}

// Обновляем сводку при загрузке
document.addEventListener('DOMContentLoaded',()=>{
  fetch('/cart/summary/',{headers:{'X-Requested-With':'XMLHttpRequest'}})
    .then(r=>r.ok?r.json():null)
    .then(d=>{ if(d&&d.ok){ updateCartBadge(d.count); }})
    .catch(()=>{});

  // Перемещаем галерею товара в левую колонку и синхронизируем миниатюры
  (function(){
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
  })();

  // Переміщення блоку «Кольори»: спочатку ПЕРЕД кнопками «Опис/Розмірна сітка», потім фолбеки
  (function(){
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
  })();

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
  })();

  // Тогглер мини‑корзины (и по id, и по data-атрибуту)
  const bindCartToggle = (el)=>{
    if(!el) return;
    if(el.dataset.uiBoundCart==='1') return;
    el.dataset.uiBoundCart = '1';
    el.addEventListener('pointerdown', (e)=>{ suppressNextDocPointerdownUntil = Date.now()+250; dlog('cart toggle pointerdown'); });
    el.addEventListener('click', (e)=>{ e.preventDefault(); e.stopPropagation(); dlog('cart toggle click'); toggleMiniCart(); });
  };
  bindCartToggle(document.getElementById('cart-toggle'));
  bindCartToggle(document.getElementById('cart-toggle-mobile'));
  document.querySelectorAll('[data-cart-toggle]').forEach(bindCartToggle);

  // Пользовательская панель (десктоп)
  const userToggle = document.getElementById('user-toggle');
  const userPanel = document.getElementById('user-panel');
  if(userToggle && userPanel){
    const openUser=()=>{ const id=nextEvt(); userPanel._opId = (userPanel._opId||0)+1; const opId=userPanel._opId; if(userPanel._hideTimeout){ clearTimeout(userPanel._hideTimeout); userPanel._hideTimeout=null; } userPanel.classList.remove('hiding'); userPanel.classList.remove('d-none'); void userPanel.offsetHeight; userPanel.classList.add('show'); dlog('openUser', {id, state: panelState()}); };
    const closeUser=(reason)=>{ const id=nextEvt(); userPanel._opId = (userPanel._opId||0)+1; const opId=userPanel._opId; dlog('closeUser', {id, reason:reason||'', now:nowTs(), state: panelState()}); userPanel.classList.remove('show'); userPanel.classList.add('hiding'); const t=setTimeout(()=>{ if(opId!==userPanel._opId) return; userPanel.classList.add('d-none'); userPanel.classList.remove('hiding'); },220); userPanel._hideTimeout=t; userPanel.addEventListener('transitionend', function onEnd(e){ if(e.target!==userPanel) return; userPanel.removeEventListener('transitionend', onEnd); if(opId!==userPanel._opId) return; clearTimeout(t); userPanel.classList.add('d-none'); userPanel.classList.remove('hiding'); dlog('closeUser:transitionend', {id}); }); };
    if(!userToggle.dataset.uiBoundUser){
      userToggle.dataset.uiBoundUser = '1';
      userToggle.addEventListener('pointerdown',(e)=>{ suppressNextDocPointerdownUntil = Date.now()+250; dlog('user toggle pointerdown'); });
      userToggle.addEventListener('click',(e)=>{ const id=nextEvt(); e.preventDefault(); e.stopPropagation(); dlog('userToggle:click', {id, now:nowTs(), uiGuardUntil, suppressNextDocPointerdownUntil, suppressGlobalCloseUntil, state: panelState()}); if(Date.now() < uiGuardUntil){ dlog('userToggle ignored by uiGuard', {id}); return;} const cartOpen = miniCartPanel() && !miniCartPanel().classList.contains('d-none'); if(cartOpen) closeMiniCart('userToggle'); if(userPanel.classList.contains('d-none') || !userPanel.classList.contains('show')){ openUser(); } else { closeUser('userToggle'); } suppressGlobalCloseUntil = Date.now() + 220; dlog('set suppressGlobalCloseUntil', {id, suppressGlobalCloseUntil}); });
    }
    document.addEventListener('pointerdown',(e)=>{ const id=nextEvt(); const tgt = e.target; const state = panelState(); const supNext = Date.now() < suppressNextDocPointerdownUntil; const supGlob = Date.now() < suppressGlobalCloseUntil; const outside = !userPanel.contains(tgt) && !userToggle.contains(tgt); dlog('doc pointerdown(userPanel)', {id, supNext, supGlob, outside, target: tgt && (tgt.tagName||'') , state}); if(supNext || supGlob) return; if(userPanel.classList.contains('d-none')) return; if(outside){ closeUser('docOutside'); }});
    const uc = document.querySelector('[data-user-close]'); if(uc){ uc.addEventListener('click',(e)=>{ e.preventDefault(); closeUser();}); }
    document.addEventListener('keydown',(e)=>{ if(e.key==='Escape') closeUser(); });
  }

  // Пользовательская панель (мобильная)
  const userToggleMobile = document.getElementById('user-toggle-mobile');
  const userPanelMobile = document.getElementById('user-panel-mobile');
  if(userToggleMobile && userPanelMobile){
    const openUserMobile=()=>{ const id=nextEvt(); userPanelMobile._opId=(userPanelMobile._opId||0)+1; const opId=userPanelMobile._opId; if(userPanelMobile._hideTimeout){ clearTimeout(userPanelMobile._hideTimeout); userPanelMobile._hideTimeout=null; } userPanelMobile.classList.remove('hiding'); userPanelMobile.classList.remove('d-none'); void userPanelMobile.offsetHeight; userPanelMobile.classList.add('show'); dlog('openUserMobile', {id, state: panelState()}); };
    const closeUserMobile=(reason)=>{ const id=nextEvt(); userPanelMobile._opId=(userPanelMobile._opId||0)+1; const opId=userPanelMobile._opId; dlog('closeUserMobile', {id, reason:reason||'', now:nowTs(), state: panelState()}); userPanelMobile.classList.remove('show'); userPanelMobile.classList.add('hiding'); const t=setTimeout(()=>{ if(opId!==userPanelMobile._opId) return; userPanelMobile.classList.add('d-none'); userPanelMobile.classList.remove('hiding'); },220); userPanelMobile._hideTimeout=t; userPanelMobile.addEventListener('transitionend', function onEnd(e){ if(e.target!==userPanelMobile) return; userPanelMobile.removeEventListener('transitionend', onEnd); if(opId!==userPanelMobile._opId) return; clearTimeout(t); userPanelMobile.classList.add('d-none'); userPanelMobile.classList.remove('hiding'); dlog('closeUserMobile:transitionend', {id}); }); };
    if(!userToggleMobile.dataset.uiBoundUser){
      userToggleMobile.dataset.uiBoundUser = '1';
      userToggleMobile.addEventListener('pointerdown',(e)=>{ suppressNextDocPointerdownUntil = Date.now()+250; dlog('user toggle mobile pointerdown'); });
      userToggleMobile.addEventListener('click',(e)=>{ const id=nextEvt(); e.preventDefault(); e.stopPropagation(); dlog('userToggleMobile:click', {id, now:nowTs(), uiGuardUntil, suppressNextDocPointerdownUntil, suppressGlobalCloseUntil, state: panelState()}); if(Date.now() < uiGuardUntil){ dlog('userToggleMobile ignored by uiGuard', {id}); return;} const cartOpen = miniCartPanel() && !miniCartPanel().classList.contains('d-none'); if(cartOpen) closeMiniCart('userToggleMobile'); if(userPanelMobile.classList.contains('d-none') || !userPanelMobile.classList.contains('show')){ openUserMobile(); } else { closeUserMobile('userToggleMobile'); } suppressGlobalCloseUntil = Date.now() + 220; dlog('set suppressGlobalCloseUntil (mobile)', {id, suppressGlobalCloseUntil}); });
    }
    document.addEventListener('pointerdown',(e)=>{ const id=nextEvt(); const tgt=e.target; const state=panelState(); const supNext= Date.now() < suppressNextDocPointerdownUntil; const supGlob= Date.now() < suppressGlobalCloseUntil; const outside = !userPanelMobile.contains(tgt) && !userToggleMobile.contains(tgt); dlog('doc pointerdown(userPanelMobile)', {id, supNext, supGlob, outside, target: tgt && (tgt.tagName||''), state}); if(supNext || supGlob) return; if(userPanelMobile.classList.contains('d-none')) return; if(outside){ closeUserMobile('docOutside'); }});
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
    if(supNext){ dlog('doc pointerdown suppressed (cart)', {id}); return; }
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
    dlog('doc pointerdown(cart)', {id, supGuard, supGlob, outside, target: tgt && (tgt.tagName||''), state: panelState()});
    if(supGuard || supGlob) return;
    if(outside){
      closeMiniCart('docOutside');
    }
  });
  // Закрытие по ESC
  document.addEventListener('keydown',(e)=>{ if(e.key==='Escape') closeMiniCart(); });

  // Адаптация при ресайзе
  window.addEventListener('resize', ()=>{
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
      void panel.offsetHeight;
      if(wasShown) panel.classList.add('show');
    }
  });

  // ===== Мобильное нижнее меню: скрытие/показ по скроллу, фокусу и свайпу =====
  (function(){
    const bottomNav = document.querySelector('.bottom-nav');
    if(!bottomNav) return;

    let lastScrollY = window.scrollY || 0;
    let hidden = false;
    let hintShown = sessionStorage.getItem('bottom-nav-hint') === '1';
    let touchStartY = null;
    let touchStartX = null;
    let touchMoved = false;

    const setHidden = (v)=>{
      if(hidden === v) return;
      hidden = v;
      bottomNav.classList.toggle('bottom-nav--hidden', hidden);
    };

    const maybeShowHint = ()=>{
      if(hintShown) return;
      bottomNav.classList.add('hint-wiggle');
      setTimeout(()=> bottomNav.classList.remove('hint-wiggle'), 950);
      sessionStorage.setItem('bottom-nav-hint','1');
      hintShown = true;
    };

    // Скролл: вниз — скрыть, вверх — показать (с небольшим трешхолдом)
    let scrollTicking = false;
    window.addEventListener('scroll', ()=>{
      if(scrollTicking) return;
      scrollTicking = true;
      requestAnimationFrame(()=>{
        const y = window.scrollY || 0;
        const dy = y - lastScrollY;
        const threshold = 6;
        if(dy > threshold) setHidden(true);
        else if(dy < -threshold) setHidden(false);
        lastScrollY = y;
        scrollTicking = false;
      });
    }, {passive:true});

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
      updateCartBadge(d.count);
      refreshMiniCart(); // сразу обновим мини‑корзину
      openMiniCart();    // и откроем её
      openMiniCart();    // и откроем её для подтверждения действия
      // Небольшой визуальный отклик
      btn.classList.add('btn-success');
      setTimeout(()=>btn.classList.remove('btn-success'),400);
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
  const featuredToggle = document.getElementById('featured-toggle');
  const featuredContent = document.getElementById('featured-content');
  const featuredSection = document.getElementById('featured-section');
  
  if (!featuredToggle || !featuredContent || !featuredSection) return;
  
  // Проверяем сохраненное состояние
  const isHidden = localStorage.getItem('featured-hidden') === 'true';
  
  if (isHidden) {
    featuredContent.classList.add('collapsed');
    featuredToggle.classList.add('collapsed');
    featuredToggle.querySelector('.toggle-hint-text').textContent = 'Показати';
  }
  
  featuredToggle.addEventListener('click', function() {
    const isCollapsed = featuredContent.classList.contains('collapsed');
    
    // Добавляем эффект пульсации заголовка-кнопки
    featuredToggle.classList.add('pulsing');
    setTimeout(() => featuredToggle.classList.remove('pulsing'), 800);
    
    if (isCollapsed) {
      // Показываем блок
      featuredContent.classList.remove('collapsed');
      featuredToggle.classList.remove('collapsed');
      featuredToggle.querySelector('.toggle-hint-text').textContent = 'Сховати';
      localStorage.setItem('featured-hidden', 'false');
      
      // Анимация появления
      featuredContent.style.display = 'block';
      void featuredContent.offsetHeight; // Форсируем reflow
      featuredContent.classList.add('expanding');
      
      // Убираем класс анимации после завершения
      setTimeout(() => {
        featuredContent.classList.remove('expanding');
      }, 800);
      
    } else {
      // Скрываем блок
      featuredContent.classList.add('collapsing');
      featuredToggle.classList.add('collapsed');
      featuredToggle.querySelector('.toggle-hint-text').textContent = 'Показати';
      localStorage.setItem('featured-hidden', 'true');
      
      // Анимация скрытия
      setTimeout(() => {
        featuredContent.classList.remove('collapsing');
        featuredContent.classList.add('collapsed');
        featuredContent.style.display = 'none';
      }, 800);
    }
  });
});

// ===== ФУНКЦИИ ДЛЯ ИЗБРАННЫХ ТОВАРОВ =====
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

// Функция для переключения избранного
function toggleFavorite(productId, button) {
  if (!button) return;
  
  // Показываем индикатор загрузки
  button.style.pointerEvents = 'none';
  button.style.opacity = '0.7';
  
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
      } else {
        button.classList.remove('is-favorite');
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
    button.style.pointerEvents = 'auto';
    button.style.opacity = '1';
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
  favoriteButtons.forEach(button => {
    const productId = button.getAttribute('data-product-id');
    if (productId) {
      checkFavoriteStatus(productId, button);
    }
  });
});