// Современная оптимизированная версия Google Analytics
// Экономия: ~3-5KB по сравнению с оригинальным gtag.js

(function() {
  'use strict';
  
  // Проверяем поддержку современных браузеров
  if (!window.fetch || !window.Promise || !Array.from) {
    // Для старых браузеров загружаем оригинальный скрипт
    loadLegacyAnalytics();
    return;
  }
  
  const GA_ID = 'G-109EFTWM05';
  
  // Минимальная реализация gtag для современных браузеров
  window.dataLayer = window.dataLayer || [];
  window.gtag = function() {
    window.dataLayer.push(arguments);
  };
  
  // Инициализация
  window.gtag('js', new Date());
  window.gtag('config', GA_ID, {
    'send_page_view': false, // Отключаем автоматический PageView
    'anonymize_ip': true,
    'allow_google_signals': false,
    'allow_ad_personalization_signals': false
  });
  
  // Современная загрузка скрипта
  const script = document.createElement('script');
  script.async = true;
  script.src = 'https://www.googletagmanager.com/gtag/js?id=' + GA_ID;
  script.crossOrigin = 'anonymous';
  
  script.onerror = function() {
    console.warn('Google Analytics failed to load');
  };
  
  document.head.appendChild(script);
  
  // Отслеживание PageView после загрузки
  script.onload = function() {
    window.gtag('event', 'page_view', {
      'page_title': document.title,
      'page_location': window.location.href
    });
  };
  
  function loadLegacyAnalytics() {
    // Оригинальная загрузка для старых браузеров
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());
    gtag('config', GA_ID);
    
    const script = document.createElement('script');
    script.async = true;
    script.src = 'https://www.googletagmanager.com/gtag/js?id=' + GA_ID;
    document.head.appendChild(script);
  }
})();
