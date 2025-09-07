/**
 * Service Worker для PWA функциональности
 */
const CACHE_NAME = 'twocomms-v1.0.0';
const STATIC_CACHE = 'twocomms-static-v1.0.0';
const DYNAMIC_CACHE = 'twocomms-dynamic-v1.0.0';

// Файлы для кэширования
const STATIC_FILES = [
    '/',
    '/static/css/styles.css',
    '/static/js/main.js',
    '/static/img/logo.svg',
    '/static/img/favicon.ico',
    '/static/site.webmanifest',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css',
    'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap'
];

// Установка Service Worker
self.addEventListener('install', event => {
    console.log('Service Worker: Installing...');
    
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(cache => {
                console.log('Service Worker: Caching static files');
                return cache.addAll(STATIC_FILES);
            })
            .then(() => {
                console.log('Service Worker: Installation complete');
                return self.skipWaiting();
            })
            .catch(error => {
                console.error('Service Worker: Installation failed', error);
            })
    );
});

// Активация Service Worker
self.addEventListener('activate', event => {
    console.log('Service Worker: Activating...');
    
    event.waitUntil(
        caches.keys()
            .then(cacheNames => {
                return Promise.all(
                    cacheNames.map(cacheName => {
                        if (cacheName !== STATIC_CACHE && cacheName !== DYNAMIC_CACHE) {
                            console.log('Service Worker: Deleting old cache', cacheName);
                            return caches.delete(cacheName);
                        }
                    })
                );
            })
            .then(() => {
                console.log('Service Worker: Activation complete');
                return self.clients.claim();
            })
    );
});

// Перехват запросов
self.addEventListener('fetch', event => {
    const { request } = event;
    const url = new URL(request.url);
    
    // Стратегия кэширования для разных типов запросов
    if (request.method === 'GET') {
        // Статические файлы - Cache First
        if (url.pathname.startsWith('/static/') || 
            url.hostname === 'cdn.jsdelivr.net' || 
            url.hostname === 'fonts.googleapis.com') {
            event.respondWith(cacheFirst(request));
        }
        // API запросы - Network First
        else if (url.pathname.startsWith('/api/')) {
            event.respondWith(networkFirst(request));
        }
        // HTML страницы - Stale While Revalidate
        else if (request.headers.get('accept').includes('text/html')) {
            event.respondWith(staleWhileRevalidate(request));
        }
        // Остальные запросы - Network First
        else {
            event.respondWith(networkFirst(request));
        }
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
        console.log('Network failed, trying cache:', error);
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
        }
        return networkResponse;
    }).catch(() => {
        // Если сеть недоступна, возвращаем кэшированную версию
        return cachedResponse || new Response('Offline', { status: 503 });
    });
    
    return cachedResponse || fetchPromise;
}

// Обработка push уведомлений
self.addEventListener('push', event => {
    console.log('Service Worker: Push received');
    
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
    console.log('Service Worker: Notification click received');
    
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
    console.log('Service Worker: Background sync', event.tag);
    
    if (event.tag === 'background-sync') {
        event.waitUntil(doBackgroundSync());
    }
});

async function doBackgroundSync() {
    // Здесь можно добавить логику для синхронизации данных
    console.log('Service Worker: Performing background sync');
}
