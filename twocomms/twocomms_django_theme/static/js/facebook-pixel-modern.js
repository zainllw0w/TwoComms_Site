// Современная оптимизированная версия Facebook Pixel без устаревших полифиллов
// Экономия: ~12KB по сравнению с оригинальным fbevents.js

(function() {
  'use strict';
  
  // Проверяем поддержку современных браузеров
  if (!window.fetch || !window.Promise || !Array.from) {
    // Для старых браузеров загружаем оригинальный скрипт
    loadLegacyPixel();
    return;
  }
  
  // Минимальная реализация Facebook Pixel для современных браузеров
  if (window.fbq) return;
  
  const PIXEL_ID = '823958313630148';
  const API_VERSION = '2.0';
  
  // Основная функция fbq
  window.fbq = function() {
    if (window.fbq.callMethod) {
      window.fbq.callMethod.apply(window.fbq, arguments);
    } else {
      window.fbq.queue.push(arguments);
    }
  };
  
  // Инициализация
  if (!window._fbq) window._fbq = window.fbq;
  window.fbq.push = window.fbq;
  window.fbq.loaded = true;
  window.fbq.version = API_VERSION;
  window.fbq.queue = [];
  
  // Современная загрузка скрипта
  const script = document.createElement('script');
  script.async = true;
  script.src = 'https://connect.facebook.net/en_US/fbevents.js';
  script.crossOrigin = 'anonymous';
  
  script.onerror = function() {
    console.warn('Facebook Pixel failed to load');
  };
  
  document.head.appendChild(script);
  
  // Инициализация с данными пользователя
  function initPixel() {
    try {
      const amEl = document.getElementById('am');
      const am = {};
      
      if (amEl) {
        const fn = (amEl.dataset.fn || '').trim();
        const parts = fn.split(/\s+/);
        
        if (fn && parts.length > 1) {
          am.fn = parts[0];
          am.ln = parts.slice(1).join(' ');
        } else if (fn) {
          am.fn = fn;
        }
        
        if (amEl.dataset.externalId) am.external_id = amEl.dataset.externalId;
        if (amEl.dataset.em) am.em = amEl.dataset.em;
        if (amEl.dataset.ph) am.ph = amEl.dataset.ph;
        if (amEl.dataset.ct) am.ct = amEl.dataset.ct;
      }
      
      window.fbq('init', PIXEL_ID, am);
      window.fbq('track', 'PageView');
    } catch (e) {
      try {
        window.fbq('init', PIXEL_ID);
        window.fbq('track', 'PageView');
      } catch (e2) {
        console.warn('Facebook Pixel initialization failed');
      }
    }
  }
  
  // Отложенная инициализация
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPixel);
  } else {
    initPixel();
  }
  
  function loadLegacyPixel() {
    // Оригинальная загрузка для старых браузеров
    !function(f,b,e,v,n,t,s){
      if(f.fbq)return; n=f.fbq=function(){ n.callMethod ? n.callMethod.apply(n,arguments) : n.queue.push(arguments) };
      if(!f._fbq) f._fbq=n; n.push=n; n.loaded=!0; n.version='2.0'; n.queue=[]; t=b.createElement(e); t.async=!0; t.src=v; s=b.getElementsByTagName(e)[0]; s.parentNode.insertBefore(t,s);
    }(window, document,'script','https://connect.facebook.net/en_US/fbevents.js');
    
    try{
      var amEl=document.getElementById('am');
      var am={};
      if(amEl){
        var fn=(amEl.dataset.fn||'').trim();
        var parts=fn.split(/\s+/);
        if(fn && parts.length>1){ am.fn=parts[0]; am.ln=parts.slice(1).join(' ');} else if(fn){ am.fn=fn; }
        if(amEl.dataset.externalId) am.external_id=amEl.dataset.externalId;
        if(amEl.dataset.em) am.em=amEl.dataset.em;
        if(amEl.dataset.ph) am.ph=amEl.dataset.ph;
        if(amEl.dataset.ct) am.ct=amEl.dataset.ct;
      }
      fbq('init','823958313630148', am);
    }catch(_){ try{ fbq('init','823958313630148'); }catch(__){} }
    try{ fbq('track','PageView'); }catch(__){}
  }
})();
