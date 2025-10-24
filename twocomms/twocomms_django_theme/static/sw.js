/**
 * TwoComms Service Worker
 * Optimized for mobile performance and offline support
 * Version: 2025.10.24.001
 */

const CACHE_VERSION = 'v2-2025-10-24-001';
const CACHE_NAME = `twocomms-${CACHE_VERSION}`;

// Кэш для статических ресурсов (долгосрочный)
const STATIC_CACHE = `${CACHE_NAME}-static`;
// Кэш для изображений (среднесрочный)
const IMAGE_CACHE = `${CACHE_NAME}-images`;
// Кэш для API запросов (краткосрочный)
const API_CACHE = `${CACHE_NAME}-api`;
// Кэш для страниц (среднесрочный)
const PAGE_CACHE = `${CACHE_NAME}-pages`;

// Критические ресурсы для первой загрузки
const CRITICAL_RESOURCES = [
  '/',
  '/static/css/critical.min.css',
  '/static/css/mobile-optimizations.css',
  '/static/js/main.js',
  '/static/img/logo.svg',
  '/static/img/placeholder.jpg',
  '/offline.html' // Добавим fallback страницу
];

// Максимальные размеры кэшей
const MAX_CACHE_SIZE = {
  [STATIC_CACHE]: 50,
  [IMAGE_CACHE]: 100,
  [API_CACHE]: 30,
  [PAGE_CACHE]: 20
};

// Время жизни кэшей (в секундах)
const CACHE_EXPIRY = {
  [STATIC_CACHE]: 7 * 24 * 60 * 60, // 7 дней
  [IMAGE_CACHE]: 3 * 24 * 60 * 60,   // 3 дня
  [API_CACHE]: 5 * 60,                // 5 минут
  [PAGE_CACHE]: 24 * 60 * 60          // 1 день
};

/**
 * Утилита для ограничения размера кэша
 */
async function limitCacheSize(cacheName, maxSize) {
  const cache = await caches.open(cacheName);
  const keys = await cache.keys();
  
  if (keys.length > maxSize) {
    // Удаляем старые записи
    const toDelete = keys.length - maxSize;
    for (let i = 0; i < toDelete; i++) {
      await cache.delete(keys[i]);
    }
  }
}

/**
 * Проверка актуальности кэша
 */
function isCacheExpired(response, cacheName) {
  if (!response) return true;
  
  const cachedTime = response.headers.get('sw-cached-time');
  if (!cachedTime) return true;
  
  const age = Date.now() - parseInt(cachedTime);
  const maxAge = CACHE_EXPIRY[cacheName] * 1000;
  
  return age > maxAge;
}

/**
 * Добавление временной метки к ответу
 */
function addCacheTimestamp(response) {
  const headers = new Headers(response.headers);
  headers.append('sw-cached-time', Date.now().toString());
  
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: headers
  });
}

/**
 * Определение типа запроса и соответствующего кэша
 */
function getCacheNameForRequest(request) {
  const url = new URL(request.url);
  
  // Статические ресурсы
  if (url.pathname.includes('/static/')) {
    if (url.pathname.match(/\.(jpg|jpeg|png|gif|webp|svg)$/)) {
      return IMAGE_CACHE;
    }
    return STATIC_CACHE;
  }
  
  // Медиа файлы
  if (url.pathname.includes('/media/')) {
    return IMAGE_CACHE;
  }
  
  // API запросы
  if (url.pathname.includes('/api/') || url.pathname.includes('/cart/')) {
    return API_CACHE;
  }
  
  // Страницы
  if (request.mode === 'navigate' || request.headers.get('accept').includes('text/html')) {
    return PAGE_CACHE;
  }
  
  return STATIC_CACHE;
}

/**
 * Стратегия: Network First с Fallback на кэш
 * Используется для API и динамического контента
 */
async function networkFirstStrategy(request, cacheName) {
  try {
    const networkResponse = await fetch(request);
    
    if (networkResponse.ok) {
      const cache = await caches.open(cacheName);
      const responseWithTimestamp = addCacheTimestamp(networkResponse.clone());
      cache.put(request, responseWithTimestamp);
      await limitCacheSize(cacheName, MAX_CACHE_SIZE[cacheName]);
    }
    
    return networkResponse;
  } catch (error) {
    // Если сеть недоступна, пытаемся взять из кэша
    const cachedResponse = await caches.match(request);
    
    if (cachedResponse) {
      return cachedResponse;
    }
    
    // Если это HTML страница, возвращаем offline страницу
    if (request.headers.get('accept').includes('text/html')) {
      return caches.match('/offline.html');
    }
    
    throw error;
  }
}

/**
 * Стратегия: Cache First с Fallback на сеть
 * Используется для статических ресурсов
 */
async function cacheFirstStrategy(request, cacheName) {
  const cachedResponse = await caches.match(request);
  
  // Проверяем актуальность кэша
  if (cachedResponse && !isCacheExpired(cachedResponse, cacheName)) {
    return cachedResponse;
  }
  
  try {
    const networkResponse = await fetch(request);
    
    if (networkResponse.ok) {
      const cache = await caches.open(cacheName);
      const responseWithTimestamp = addCacheTimestamp(networkResponse.clone());
      cache.put(request, responseWithTimestamp);
      await limitCacheSize(cacheName, MAX_CACHE_SIZE[cacheName]);
    }
    
    return networkResponse;
  } catch (error) {
    // Если сеть недоступна, возвращаем устаревший кэш
    if (cachedResponse) {
      return cachedResponse;
    }
    
    throw error;
  }
}

/**
 * Стратегия: Stale While Revalidate
 * Возвращаем кэш немедленно, но обновляем в фоне
 */
async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cachedResponse = await cache.match(request);
  
  const fetchPromise = fetch(request).then(async (networkResponse) => {
    if (networkResponse.ok) {
      const responseWithTimestamp = addCacheTimestamp(networkResponse.clone());
      await cache.put(request, responseWithTimestamp);
      await limitCacheSize(cacheName, MAX_CACHE_SIZE[cacheName]);
    }
    return networkResponse;
  }).catch(() => {
    // Игнорируем ошибки обновления
    return cachedResponse;
  });
  
  // Возвращаем кэш немедленно, если есть
  return cachedResponse || fetchPromise;
}

/**
 * Установка Service Worker
 */
self.addEventListener('install', (event) => {
  console.log('[SW] Installing service worker...');
  
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => {
        console.log('[SW] Caching critical resources...');
        // Кэшируем только те ресурсы, которые точно существуют
        return cache.addAll(
          CRITICAL_RESOURCES.filter(url => url !== '/offline.html')
        ).catch(err => {
          console.warn('[SW] Some critical resources failed to cache:', err);
          // Продолжаем установку даже если некоторые ресурсы не закэшировались
        });
      })
      .then(() => self.skipWaiting())
  );
});

/**
 * Активация Service Worker
 */
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating service worker...');
  
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => {
            // Удаляем старые версии кэша
            return name.startsWith('twocomms-') && name !== CACHE_NAME && 
                   !name.startsWith(CACHE_NAME);
          })
          .map((name) => {
            console.log('[SW] Deleting old cache:', name);
            return caches.delete(name);
          })
      );
    })
    .then(() => self.clients.claim())
  );
});

/**
 * Обработка запросов
 */
self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);
  
  // Игнорируем запросы к другим доменам (кроме CDN)
  if (url.origin !== location.origin && 
      !url.origin.includes('cdn.jsdelivr.net') &&
      !url.origin.includes('fonts.googleapis.com')) {
    return;
  }
  
  // Игнорируем POST запросы и другие методы кроме GET
  if (request.method !== 'GET') {
    return;
  }
  
  // Определяем имя кэша для запроса
  const cacheName = getCacheNameForRequest(request);
  
  // Выбираем стратегию кэширования
  let strategy;
  
  if (cacheName === API_CACHE) {
    // Для API - Network First
    strategy = networkFirstStrategy(request, cacheName);
  } else if (cacheName === IMAGE_CACHE || cacheName === STATIC_CACHE) {
    // Для статики и изображений - Cache First
    strategy = cacheFirstStrategy(request, cacheName);
  } else if (cacheName === PAGE_CACHE) {
    // Для страниц - Stale While Revalidate
    strategy = staleWhileRevalidate(request, cacheName);
  } else {
    // По умолчанию - Network First
    strategy = networkFirstStrategy(request, cacheName);
  }
  
  event.respondWith(strategy);
});

/**
 * Обработка сообщений от клиента
 */
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  
  if (event.data && event.data.type === 'CLEAR_CACHE') {
    event.waitUntil(
      caches.keys().then((cacheNames) => {
        return Promise.all(
          cacheNames.map((name) => caches.delete(name))
        );
      })
    );
  }
  
  if (event.data && event.data.type === 'PREFETCH') {
    const urls = event.data.urls || [];
    event.waitUntil(
      caches.open(PAGE_CACHE).then((cache) => {
        return Promise.all(
          urls.map((url) => {
            return fetch(url).then((response) => {
              if (response.ok) {
                const responseWithTimestamp = addCacheTimestamp(response);
                return cache.put(url, responseWithTimestamp);
              }
            }).catch(() => {
              // Игнорируем ошибки prefetch
            });
          })
        );
      })
    );
  }
});

/**
 * Обработка ошибок
 */
self.addEventListener('error', (event) => {
  console.error('[SW] Error:', event.error);
});

self.addEventListener('unhandledrejection', (event) => {
  console.error('[SW] Unhandled rejection:', event.reason);
});

console.log('[SW] Service Worker loaded successfully');

