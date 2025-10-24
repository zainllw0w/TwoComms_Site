/**
 * Service Worker для PWA функциональности
 * Оптимизирован для максимальной производительности на мобильных устройствах
 */
const CACHE_VERSION = '2.0.0';
const CACHE_NAME = `twocomms-v${CACHE_VERSION}`;
const STATIC_CACHE = `twocomms-static-v${CACHE_VERSION}`;
const DYNAMIC_CACHE = `twocomms-dynamic-v${CACHE_VERSION}`;
const IMAGE_CACHE = `twocomms-images-v${CACHE_VERSION}`;
const FONT_CACHE = `twocomms-fonts-v${CACHE_VERSION}`;

// Максимальный размер кэша (количество элементов)
const MAX_DYNAMIC_CACHE_SIZE = 50;
const MAX_IMAGE_CACHE_SIZE = 100;

// Файлы для кэширования (оптимизированный список для мобильных)
const STATIC_FILES = [
    '/',
    '/static/css/styles.min.css',
    '/static/css/mobile-optimizations.css',
    '/static/css/cls-ultimate.css',
    '/static/js/main.js',
    '/static/img/logo.svg',
    '/static/img/favicon-192x192.png',
    '/static/img/favicon-512x512.png',
    '/static/site.webmanifest'
];

// CDN ресурсы (кэшируем отдельно)
const CDN_RESOURCES = [
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js'
];

// Установка Service Worker
self.addEventListener('install', event => {
    swlog('Installing...');
    
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(cache => {
                swlog('Caching static files');
                return cache.addAll(STATIC_FILES);
            })
            .then(() => {
                swlog('Installation complete');
                return self.skipWaiting();
            })
            .catch(error => {
                console.error('Service Worker: Installation failed', error);
            })
    );
});

// Активация Service Worker
self.addEventListener('activate', event => {
    swlog('Activating...');
    
    event.waitUntil(
        caches.keys()
            .then(cacheNames => {
                return Promise.all(
                    cacheNames.map(cacheName => {
                        if (cacheName !== STATIC_CACHE && cacheName !== DYNAMIC_CACHE) {
                            swlog('Deleting old cache', cacheName);
                            return caches.delete(cacheName);
                        }
                    })
                );
            })
            .then(() => {
                swlog('Activation complete');
                return self.clients.claim();
            })
    );
});

// Очистка старых кэшей
async function cleanupCache(cacheName, maxSize) {
    const cache = await caches.open(cacheName);
    const keys = await cache.keys();
    if (keys.length > maxSize) {
        await cache.delete(keys[0]);
        await cleanupCache(cacheName, maxSize);
    }
}

// Перехват запросов (оптимизированный для мобильных)
self.addEventListener('fetch', event => {
    const { request } = event;
    const url = new URL(request.url);
    
    // Игнорируем не-GET запросы и chrome-extension
    if (request.method !== 'GET' || url.protocol === 'chrome-extension:') {
        return;
    }
    
    // Стратегия кэширования для разных типов запросов
    // Изображения - Cache First с отдельным кэшем
    if (request.destination === 'image' || url.pathname.match(/\.(jpg|jpeg|png|gif|webp|svg|ico)$/i)) {
        event.respondWith(cacheFirstImage(request));
    }
    // Шрифты - Cache First с отдельным кэшем
    else if (request.destination === 'font' || url.pathname.match(/\.(woff|woff2|ttf|eot)$/i)) {
        event.respondWith(cacheFirstFont(request));
    }
        // Статические файлы - Cache First
    else if (url.pathname.startsWith('/static/') || 
            url.hostname === 'cdn.jsdelivr.net' || 
             url.hostname === 'fonts.googleapis.com' ||
             url.hostname === 'cdnjs.cloudflare.com') {
            event.respondWith(cacheFirst(request));
        }
        // API запросы - Network First
        else if (url.pathname.startsWith('/api/')) {
            event.respondWith(networkFirst(request));
        }
    // HTML страницы - Network First с кэш fallback
    else if (request.headers.get('accept')?.includes('text/html')) {
        event.respondWith(networkFirstHTML(request));
    }
});

// Cache First стратегия
async function cacheFirst(request) {
    try {
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
        
        const networkResponse = await fetch(request);
        if (networkResponse.ok) {
            const cache = await caches.open(STATIC_CACHE);
            cache.put(request, networkResponse.clone());
        }
        return networkResponse;
    } catch (error) {
        console.error('Cache First failed:', error);
        return new Response('Offline', { status: 503 });
    }
}

// Network First стратегия
async function networkFirst(request) {
    try {
        const networkResponse = await fetch(request);
        if (networkResponse.ok) {
            const cache = await caches.open(DYNAMIC_CACHE);
            cache.put(request, networkResponse.clone());
        }
        return networkResponse;
    } catch (error) {
        swwarn('Network failed, trying cache:', error);
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
        return new Response('Offline', { status: 503 });
    }
}

// Stale While Revalidate стратегия
async function staleWhileRevalidate(request) {
    const cache = await caches.open(DYNAMIC_CACHE);
    const cachedResponse = await cache.match(request);
    
    const fetchPromise = fetch(request).then(networkResponse => {
        if (networkResponse.ok) {
            cache.put(request, networkResponse.clone());
            cleanupCache(DYNAMIC_CACHE, MAX_DYNAMIC_CACHE_SIZE);
        }
        return networkResponse;
    }).catch(() => {
        return cachedResponse || new Response('Offline', { status: 503 });
    });
    
    return cachedResponse || fetchPromise;
}

// Cache First для изображений (отдельный кэш)
async function cacheFirstImage(request) {
    try {
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
        
        const networkResponse = await fetch(request);
        if (networkResponse.ok) {
            const cache = await caches.open(IMAGE_CACHE);
            cache.put(request, networkResponse.clone());
            cleanupCache(IMAGE_CACHE, MAX_IMAGE_CACHE_SIZE);
        }
        return networkResponse;
    } catch (error) {
        // Возвращаем placeholder для изображений при ошибке
        const cachedResponse = await caches.match(request);
        return cachedResponse || new Response('', { status: 404 });
    }
}

// Cache First для шрифтов (отдельный кэш)
async function cacheFirstFont(request) {
    try {
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
        
        const networkResponse = await fetch(request);
        if (networkResponse.ok) {
            const cache = await caches.open(FONT_CACHE);
            cache.put(request, networkResponse.clone());
        }
        return networkResponse;
    } catch (error) {
        const cachedResponse = await caches.match(request);
        return cachedResponse || new Response('', { status: 404 });
    }
}

// Network First для HTML (с кэш fallback)
async function networkFirstHTML(request) {
    try {
        const networkResponse = await fetch(request);
        if (networkResponse.ok) {
            const cache = await caches.open(DYNAMIC_CACHE);
            cache.put(request, networkResponse.clone());
            cleanupCache(DYNAMIC_CACHE, MAX_DYNAMIC_CACHE_SIZE);
        }
        return networkResponse;
    } catch (error) {
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
        // Offline fallback page
        return caches.match('/') || new Response('Offline', { 
            status: 503,
            statusText: 'Service Unavailable',
            headers: new Headers({
                'Content-Type': 'text/html'
            })
        });
    }
}

// Обработка push уведомлений
self.addEventListener('push', event => {
    swlog('Push received');
    
    const options = {
        body: event.data ? event.data.text() : 'Новое уведомление от TwoComms',
        icon: '/static/img/favicon-192x192.png',
        badge: '/static/img/favicon-32x32.png',
        vibrate: [100, 50, 100],
        data: {
            dateOfArrival: Date.now(),
            primaryKey: 1
        },
        actions: [
            {
                action: 'explore',
                title: 'Перейти в магазин',
                icon: '/static/img/icons/cart.png'
            },
            {
                action: 'close',
                title: 'Закрыть',
                icon: '/static/img/icons/close.png'
            }
        ]
    };
    
    event.waitUntil(
        self.registration.showNotification('TwoComms', options)
    );
});

// Обработка кликов по уведомлениям
self.addEventListener('notificationclick', event => {
    swlog('Notification click received');
    
    event.notification.close();
    
    if (event.action === 'explore') {
        event.waitUntil(
            clients.openWindow('/catalog/')
        );
    } else if (event.action === 'close') {
        // Просто закрываем уведомление
    } else {
        // Клик по телу уведомления
        event.waitUntil(
            clients.openWindow('/')
        );
    }
});

// Синхронизация в фоне
self.addEventListener('sync', event => {
    swlog('Background sync', event.tag);
    
    if (event.tag === 'background-sync') {
        event.waitUntil(doBackgroundSync());
    }
});

async function doBackgroundSync() {
    // Здесь можно добавить логику для синхронизации данных
    swlog('Performing background sync');
}
