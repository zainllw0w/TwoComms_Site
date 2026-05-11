/* Service worker for storage.twocomms.shop (PWA). */
const SW_VERSION = '2026-05-11-warehouse-v1';
const CACHE_STATIC = 'wh-static-' + SW_VERSION;
const OFFLINE_URL = '/static/warehouse/offline.html';

const PRECACHE = [
    '/static/warehouse/css/warehouse.css',
    '/static/warehouse/js/warehouse.js',
    '/static/warehouse/manifest.json',
    OFFLINE_URL,
];

self.addEventListener('install', function (event) {
    event.waitUntil(
        caches.open(CACHE_STATIC).then(function (cache) {
            return cache.addAll(PRECACHE).catch(function () { /* ignore */ });
        }).then(function () { return self.skipWaiting(); })
    );
});

self.addEventListener('activate', function (event) {
    event.waitUntil(
        caches.keys().then(function (keys) {
            return Promise.all(keys.filter(function (k) {
                return k.indexOf('wh-') === 0 && k !== CACHE_STATIC;
            }).map(function (k) { return caches.delete(k); }));
        }).then(function () { return self.clients.claim(); })
    );
});

self.addEventListener('fetch', function (event) {
    const req = event.request;
    if (req.method !== 'GET') return;

    const url = new URL(req.url);
    if (url.origin !== self.location.origin) return;

    // Cache-first for static
    if (url.pathname.startsWith('/static/warehouse/')) {
        event.respondWith(
            caches.match(req).then(function (cached) {
                if (cached) return cached;
                return fetch(req).then(function (resp) {
                    if (resp.ok) {
                        const copy = resp.clone();
                        caches.open(CACHE_STATIC).then(function (cache) { cache.put(req, copy); });
                    }
                    return resp;
                });
            })
        );
        return;
    }

    // Network-first for navigations with offline fallback
    if (req.mode === 'navigate') {
        event.respondWith(
            fetch(req).catch(function () {
                return caches.match(OFFLINE_URL);
            })
        );
    }
});
