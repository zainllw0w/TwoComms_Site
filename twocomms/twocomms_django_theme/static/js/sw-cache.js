/**
 * Современный Service Worker для эффективного кеширования TwoComms
 * Реализует Cache-First, Network-First и Stale-While-Revalidate стратегии
 */

const CACHE_NAME = 'twocomms-v1.0.0';
const STATIC_CACHE = 'twocomms-static-v1.0.0';
const DYNAMIC_CACHE = 'twocomms-dynamic-v1.0.0';
const IMAGE_CACHE = 'twocomms-images-v1.0.0';

// Ресурсы для предварительного кеширования
const PRECACHE_URLS = [
    '/',
    '/static/css/styles.min.css',
    '/static/css/cls-fixes.css',
    '/static/js/main.js',
    '/static/img/logo.svg',
    '/static/img/noise.webp',
    '/static/img/google.svg'
];

// Стратегии кеширования для разных типов ресурсов
const CACHE_STRATEGIES = {
    // Статические ресурсы - Cache First (1 год)
    static: {
        pattern: /\.(css|js|woff|woff2|ttf|eot|svg|ico)$/,
        strategy: 'cache-first',
        cacheName: STATIC_CACHE,
        maxAge: 31536000, // 1 год
        maxEntries: 100
    },
    
    // Изображения - Cache First с ограничением (1 год)
    images: {
        pattern: /\.(jpg|jpeg|png|gif|webp|avif)$/,
        strategy: 'cache-first',
        cacheName: IMAGE_CACHE,
        maxAge: 31536000, // 1 год
        maxEntries: 200
    },
    
    // HTML страницы - Stale While Revalidate (1 час)
    html: {
        pattern: /\.html$|\/$/,
        strategy: 'stale-while-revalidate',
        cacheName: DYNAMIC_CACHE,
        maxAge: 3600, // 1 час
        maxEntries: 50
    },
    
    // API запросы - Network First (5 минут)
    api: {
        pattern: /\/api\//,
        strategy: 'network-first',
        cacheName: DYNAMIC_CACHE,
        maxAge: 300, // 5 минут
        maxEntries: 30
    },
    
    // Медиа файлы - Cache First (30 дней)
    media: {
        pattern: /\/media\//,
        strategy: 'cache-first',
        cacheName: IMAGE_CACHE,
        maxAge: 2592000, // 30 дней
        maxEntries: 100
    }
};

// Установка Service Worker
self.addEventListener('install', event => {
    console.log('Service Worker: Installing...');
    
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(cache => {
                console.log('Service Worker: Precaching static resources');
                return cache.addAll(PRECACHE_URLS);
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
                        if (cacheName !== STATIC_CACHE && 
                            cacheName !== DYNAMIC_CACHE && 
                            cacheName !== IMAGE_CACHE) {
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

// Обработка запросов
self.addEventListener('fetch', event => {
    const request = event.request;
    const url = new URL(request.url);
    
    // Пропускаем не-GET запросы
    if (request.method !== 'GET') {
        return;
    }
    
    // Пропускаем запросы к внешним доменам (кроме наших CDN)
    if (url.origin !== location.origin && 
        !url.hostname.includes('twocomms.shop') &&
        !url.hostname.includes('connect.facebook.net') &&
        !url.hostname.includes('scripts.clarity.ms')) {
        return;
    }
    
    // Определяем стратегию кеширования
    const strategy = getCacheStrategy(request.url);
    
    if (strategy) {
        event.respondWith(handleRequest(request, strategy));
    }
});

// Определение стратегии кеширования
function getCacheStrategy(url) {
    for (const [name, config] of Object.entries(CACHE_STRATEGIES)) {
        if (config.pattern.test(url)) {
            return config;
        }
    }
    return null;
}

// Обработка запроса с выбранной стратегией
async function handleRequest(request, strategy) {
    const cache = await caches.open(strategy.cacheName);
    
    switch (strategy.strategy) {
        case 'cache-first':
            return cacheFirst(request, cache, strategy);
        case 'network-first':
            return networkFirst(request, cache, strategy);
        case 'stale-while-revalidate':
            return staleWhileRevalidate(request, cache, strategy);
        default:
            return fetch(request);
    }
}

// Cache First стратегия
async function cacheFirst(request, cache, strategy) {
    try {
        const cachedResponse = await cache.match(request);
        
        if (cachedResponse) {
            // Проверяем возраст кеша
            const cacheTime = cachedResponse.headers.get('sw-cache-time');
            if (cacheTime && (Date.now() - parseInt(cacheTime)) < strategy.maxAge * 1000) {
                return cachedResponse;
            }
        }
        
        const networkResponse = await fetch(request);
        
        if (networkResponse.ok) {
            const responseToCache = networkResponse.clone();
            responseToCache.headers.set('sw-cache-time', Date.now().toString());
            await cache.put(request, responseToCache);
            await cleanupCache(cache, strategy.maxEntries);
        }
        
        return networkResponse;
    } catch (error) {
        console.error('Cache First failed:', error);
        const cachedResponse = await cache.match(request);
        return cachedResponse || new Response('Offline', { status: 503 });
    }
}

// Network First стратегия
async function networkFirst(request, cache, strategy) {
    try {
        const networkResponse = await fetch(request);
        
        if (networkResponse.ok) {
            const responseToCache = networkResponse.clone();
            responseToCache.headers.set('sw-cache-time', Date.now().toString());
            await cache.put(request, responseToCache);
            await cleanupCache(cache, strategy.maxEntries);
        }
        
        return networkResponse;
    } catch (error) {
        console.error('Network First failed:', error);
        const cachedResponse = await cache.match(request);
        return cachedResponse || new Response('Offline', { status: 503 });
    }
}

// Stale While Revalidate стратегия
async function staleWhileRevalidate(request, cache, strategy) {
    const cachedResponse = await cache.match(request);
    
    const fetchPromise = fetch(request).then(networkResponse => {
        if (networkResponse.ok) {
            const responseToCache = networkResponse.clone();
            responseToCache.headers.set('sw-cache-time', Date.now().toString());
            cache.put(request, responseToCache);
            await cleanupCache(cache, strategy.maxEntries);
        }
        return networkResponse;
    }).catch(error => {
        console.error('Stale While Revalidate network failed:', error);
        return null;
    });
    
    return cachedResponse || await fetchPromise || new Response('Offline', { status: 503 });
}

// Очистка кеша при превышении лимита
async function cleanupCache(cache, maxEntries) {
    const keys = await cache.keys();
    if (keys.length > maxEntries) {
        const keysToDelete = keys.slice(0, keys.length - maxEntries);
        await Promise.all(keysToDelete.map(key => cache.delete(key)));
    }
}

// Обработка сообщений от основного потока
self.addEventListener('message', event => {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
    
    if (event.data && event.data.type === 'CLEAR_CACHE') {
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => caches.delete(cacheName))
            );
        }).then(() => {
            event.ports[0].postMessage({ success: true });
        });
    }
});

// Периодическая очистка устаревших записей
setInterval(async () => {
    const cacheNames = await caches.keys();
    
    for (const cacheName of cacheNames) {
        const cache = await caches.open(cacheName);
        const keys = await cache.keys();
        
        for (const key of keys) {
            const response = await cache.match(key);
            const cacheTime = response.headers.get('sw-cache-time');
            
            if (cacheTime) {
                const age = Date.now() - parseInt(cacheTime);
                const maxAge = 31536000 * 1000; // 1 год в миллисекундах
                
                if (age > maxAge) {
                    await cache.delete(key);
                }
            }
        }
    }
}, 24 * 60 * 60 * 1000); // Проверяем раз в день
