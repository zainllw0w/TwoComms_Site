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
function miniCartPanel(){ return document.getElementById('mini-cart-panel'); }
function openMiniCart(){
  const panel=miniCartPanel(); if(!panel) return;
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
  refreshMiniCart();
}
function closeMiniCart(){
  const panel=miniCartPanel(); if(!panel) return;
  panel.classList.remove('show');
  panel.classList.add('hiding');
  const hideAfter= setTimeout(()=>{
    panel.classList.add('d-none');
    panel.classList.remove('hiding');
  }, 260);
  // если есть transitionend — ускорим скрытие
  panel.addEventListener('transitionend', function onTrEnd(e){
    if(e.target!==panel) return;
    panel.removeEventListener('transitionend', onTrEnd);
    clearTimeout(hideAfter);
    panel.classList.add('d-none');
    panel.classList.remove('hiding');
  });
}
function toggleMiniCart(){
  const panel=miniCartPanel(); if(!panel) return;
  if(panel.classList.contains('d-none') || !panel.classList.contains('show')) openMiniCart(); else closeMiniCart();
}
function refreshMiniCart(){
  const panel=miniCartPanel(); if(!panel) return;
  const content = panel.querySelector('#mini-cart-content') || panel;
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
  const hookToggle = (el)=> el && el.addEventListener('click', (e)=>{ e.preventDefault(); toggleMiniCart(); });
  hookToggle(document.getElementById('cart-toggle'));
  document.querySelectorAll('[data-cart-toggle]').forEach(hookToggle);

  // Пользовательская панель
  const userToggle = document.getElementById('user-toggle');
  const userPanel = document.getElementById('user-panel');
  if(userToggle && userPanel){
    const openUser=()=>{ userPanel.classList.remove('d-none'); void userPanel.offsetHeight; userPanel.classList.add('show'); };
    const closeUser=()=>{ userPanel.classList.remove('show'); const t=setTimeout(()=>userPanel.classList.add('d-none'),220); userPanel.addEventListener('transitionend', function onEnd(e){ if(e.target!==userPanel) return; userPanel.removeEventListener('transitionend', onEnd); clearTimeout(t); userPanel.classList.add('d-none'); }); };
    userToggle.addEventListener('click',(e)=>{ e.preventDefault(); if(userPanel.classList.contains('d-none') || !userPanel.classList.contains('show')) openUser(); else closeUser(); });
    document.addEventListener('click',(e)=>{ if(userPanel.classList.contains('d-none')) return; if(!userPanel.contains(e.target) && !userToggle.contains(e.target)){ closeUser(); }});
    const uc = document.querySelector('[data-user-close]'); if(uc){ uc.addEventListener('click',(e)=>{ e.preventDefault(); closeUser();}); }
    document.addEventListener('keydown',(e)=>{ if(e.key==='Escape') closeUser(); });
  }

  // Кнопка закрытия мини‑кошика
  const hookClose = ()=> {
    const c = document.querySelector('[data-cart-close]');
    if(c){ c.addEventListener('click', (e)=>{ e.preventDefault(); closeMiniCart(); }); }
  };
  hookClose();

  // Закрытие по клику снаружи
  document.addEventListener('click',(e)=>{
    const panel=miniCartPanel();
    const toggle=document.getElementById('cart-toggle') || document.querySelector('[data-cart-toggle]');
    if(!panel) return;
    if(panel.classList.contains('d-none')) return;
    if(!panel.contains(e.target) && (!toggle || !toggle.contains(e.target))){
      closeMiniCart();
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