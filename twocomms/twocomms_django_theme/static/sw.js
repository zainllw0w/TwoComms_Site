// Эффективный Service Worker для TwoComms
const CACHE_VERSION = '2025.09.11.001';
const STATIC_CACHE = `twocomms-static-${CACHE_VERSION}`;
const DYNAMIC_CACHE = `twocomms-dynamic-${CACHE_VERSION}`;
const IMAGE_CACHE = `twocomms-images-${CACHE_VERSION}`;

// Критические ресурсы для кеширования
const CRITICAL_FILES = [
  '/',
  '/static/css/styles.min.css',
  '/static/css/cls-fixes.css',
  '/static/js/main.js',
  '/static/img/logo.svg',
  '/static/img/noise.webp'
];

// Максимальное количество файлов в кеше
const MAX_CACHE_SIZE = 100;
const MAX_IMAGE_CACHE_SIZE = 50;

// Установка Service Worker
self.addEventListener('install', event => {
  console.log('SW: Installing...');
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(cache => {
        console.log('SW: Caching critical files');
        return cache.addAll(CRITICAL_FILES);
      })
      .then(() => {
        console.log('SW: Installation complete');
        return self.skipWaiting();
      })
      .catch(error => {
        console.error('SW: Installation failed', error);
      })
  );
});

// Активация Service Worker
self.addEventListener('activate', event => {
  console.log('SW: Activating...');
  event.waitUntil(
    caches.keys()
      .then(cacheNames => {
        return Promise.all(
          cacheNames.map(cacheName => {
            if (!cacheName.includes(CACHE_VERSION)) {
              console.log('SW: Deleting old cache', cacheName);
              return caches.delete(cacheName);
            }
          })
        );
      })
      .then(() => {
        console.log('SW: Activation complete');
        return self.clients.claim();
      })
  );
});

// Перехват запросов
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Кешируем только GET запросы
  if (request.method !== 'GET') {
    return;
  }

  // Статические файлы - Cache First стратегия
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(handleStaticRequest(request));
    return;
  }

  // Изображения - Cache First с ограничением размера
  if (isImageRequest(request)) {
    event.respondWith(handleImageRequest(request));
    return;
  }

  // HTML страницы - Network First стратегия
  if (request.headers.get('accept').includes('text/html')) {
    event.respondWith(handlePageRequest(request));
    return;
  }

  // API запросы - Network First с кешированием
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(handleApiRequest(request));
    return;
  }
});

// Обработка статических файлов
async function handleStaticRequest(request) {
  try {
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }

    const networkResponse = await fetch(request);
    if (networkResponse.status === 200) {
      const cache = await caches.open(STATIC_CACHE);
      await cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    console.error('SW: Static request failed', error);
    return new Response('Offline', { status: 503 });
  }
}

// Обработка изображений
async function handleImageRequest(request) {
  try {
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }

    const networkResponse = await fetch(request);
    if (networkResponse.status === 200) {
      const cache = await caches.open(IMAGE_CACHE);
      
      // Ограничиваем размер кеша изображений
      const keys = await cache.keys();
      if (keys.length >= MAX_IMAGE_CACHE_SIZE) {
        await cache.delete(keys[0]);
      }
      
      await cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    console.error('SW: Image request failed', error);
    return new Response('Image not available', { status: 503 });
  }
}

// Обработка HTML страниц
async function handlePageRequest(request) {
  try {
    const networkResponse = await fetch(request);
    if (networkResponse.status === 200) {
      const cache = await caches.open(DYNAMIC_CACHE);
      
      // Ограничиваем размер кеша
      const keys = await cache.keys();
      if (keys.length >= MAX_CACHE_SIZE) {
        await cache.delete(keys[0]);
      }
      
      await cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    console.log('SW: Network failed, trying cache');
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    return new Response('Offline', { status: 503 });
  }
}

// Обработка API запросов
async function handleApiRequest(request) {
  try {
    const networkResponse = await fetch(request);
    if (networkResponse.status === 200) {
      const cache = await caches.open(DYNAMIC_CACHE);
      await cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    return new Response('API unavailable', { status: 503 });
  }
}

// Проверка, является ли запрос изображением
function isImageRequest(request) {
  const url = new URL(request.url);
  const pathname = url.pathname.toLowerCase();
  return pathname.match(/\.(jpg|jpeg|png|gif|webp|svg|ico)$/);
}

// Очистка старых кешей
async function cleanupOldCaches() {
  const cacheNames = await caches.keys();
  const currentCaches = [STATIC_CACHE, DYNAMIC_CACHE, IMAGE_CACHE];
  
  for (const cacheName of cacheNames) {
    if (!currentCaches.includes(cacheName)) {
      await caches.delete(cacheName);
    }
  }
}

// Периодическая очистка кеша
setInterval(cleanupOldCaches, 24 * 60 * 60 * 1000); // Каждые 24 часа
