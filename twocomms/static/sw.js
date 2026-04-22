const SW_VERSION = '2026-04-22-pwa-shell-v3';
const EVENTS_ENDPOINT = '/push/events/';
const OFFLINE_URL = '/static/offline.html';
const APP_SHELL_CACHE = `twc-app-shell-${SW_VERSION}`;
const STATIC_CACHE = `twc-static-${SW_VERSION}`;
const IMAGE_CACHE = `twc-images-${SW_VERSION}`;
const MAX_IMAGE_CACHE_ENTRIES = 64;

const PRECACHE_URLS = [
  OFFLINE_URL,
  '/site.webmanifest',
  '/static/img/favicon-192x192.png',
  '/static/img/favicon-512x512.png',
  '/static/img/favicon-180x180.png',
];

const STATIC_DESTINATIONS = new Set(['script', 'style', 'font', 'worker', 'manifest']);
const IMAGE_DESTINATIONS = new Set(['image']);
const EXCLUDED_NAVIGATION_PREFIXES = [
  '/admin/',
  '/api/',
  '/accounts/',
  '/oauth/',
  '/social/',
  '/orders/',
  '/cart/',
  '/checkout/',
  '/push/',
  '/__debug__/',
];

function postDeliveryEvent(eventType, deliveryToken) {
  if (!deliveryToken) {
    return Promise.resolve();
  }

  return fetch(EVENTS_ENDPOINT, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      event_type: eventType,
      delivery_token: deliveryToken,
      sw_version: SW_VERSION,
    }),
    keepalive: true,
  }).catch(() => undefined);
}

function normalizePayload(event) {
  if (!event.data) {
    return {};
  }

  try {
    return event.data.json() || {};
  } catch (_) {
    try {
      return { body: event.data.text() };
    } catch (_) {
      return {};
    }
  }
}

function buildNotificationOptions(payload) {
  const options = {
    body: payload.body || '',
    icon: payload.icon || '/static/img/favicon-192x192.png',
    badge: payload.badge || payload.icon || '/static/img/favicon-192x192.png',
    image: payload.image || undefined,
    timestamp: payload.timestamp || Date.now(),
    tag: payload.tag || undefined,
    renotify: false,
    requireInteraction: false,
    data: {
      url: payload.url || self.location.origin + '/',
      deliveryToken: payload.deliveryToken || '',
      campaignId: payload.campaignId || null,
    },
  };

  if (!options.image) {
    delete options.image;
  }
  if (!options.tag) {
    delete options.tag;
  }

  return options;
}

async function focusOrOpenWindow(targetUrl) {
  const normalizedUrl = new URL(targetUrl, self.location.origin).toString();
  const windowClients = await self.clients.matchAll({
    type: 'window',
    includeUncontrolled: true,
  });

  for (const client of windowClients) {
    if (!client || !client.url) {
      continue;
    }

    if (client.url === normalizedUrl && 'focus' in client) {
      return client.focus();
    }
  }

  for (const client of windowClients) {
    if (!client || !client.url) {
      continue;
    }

    if (client.url.startsWith(self.location.origin) && 'focus' in client) {
      if ('navigate' in client) {
        try {
          await client.navigate(normalizedUrl);
        } catch (_) {
          // Fall back to focusing the current tab if navigate fails.
        }
      }
      return client.focus();
    }
  }

  if (self.clients.openWindow) {
    return self.clients.openWindow(normalizedUrl);
  }

  return undefined;
}

function isSameOrigin(url) {
  return url.origin === self.location.origin;
}

function isExcludedNavigation(url) {
  return EXCLUDED_NAVIGATION_PREFIXES.some((prefix) => url.pathname.startsWith(prefix));
}

function isNavigationRequest(request) {
  if (request.mode === 'navigate') {
    return true;
  }
  const accept = request.headers.get('accept') || '';
  return request.method === 'GET' && accept.includes('text/html');
}

function shouldCacheStaticAsset(request, url) {
  if (request.method !== 'GET') {
    return false;
  }
  if (!isSameOrigin(url)) {
    return false;
  }
  if (url.pathname === '/site.webmanifest') {
    return request.destination === 'manifest';
  }
  if (!url.pathname.startsWith('/static/')) {
    return false;
  }
  if (url.pathname === '/sw.js' || url.pathname.endsWith('/sw.js')) {
    return false;
  }
  return STATIC_DESTINATIONS.has(request.destination);
}

function shouldCacheImage(request, url) {
  if (request.method !== 'GET') {
    return false;
  }
  if (!isSameOrigin(url)) {
    return false;
  }
  const isStaticImage = url.pathname.startsWith('/static/') || url.pathname.startsWith('/media/');
  return isStaticImage && IMAGE_DESTINATIONS.has(request.destination);
}

async function trimCache(cacheName, maxEntries) {
  const cache = await caches.open(cacheName);
  const keys = await cache.keys();
  if (keys.length <= maxEntries) {
    return;
  }

  const overflow = keys.length - maxEntries;
  for (let index = 0; index < overflow; index += 1) {
    await cache.delete(keys[index]);
  }
}

async function networkFirstNavigation(event) {
  const cache = await caches.open(APP_SHELL_CACHE);

  try {
    const preloadResponse = await event.preloadResponse;
    if (preloadResponse) {
      return preloadResponse;
    }

    return await fetch(event.request);
  } catch (_) {
    const cachedOffline = await cache.match(OFFLINE_URL, { ignoreSearch: true });
    if (cachedOffline) {
      return cachedOffline;
    }
    return Response.error();
  }
}

async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cachedResponse = await cache.match(request, { ignoreSearch: false });

  const networkPromise = fetch(request)
    .then((response) => {
      if (response && response.ok) {
        cache.put(request, response.clone()).catch(() => undefined);
      }
      return response;
    })
    .catch(() => undefined);

  if (cachedResponse) {
    networkPromise.catch(() => undefined);
    return cachedResponse;
  }

  const networkResponse = await networkPromise;
  if (networkResponse) {
    return networkResponse;
  }

  return Response.error();
}

async function cacheImages(request) {
  const response = await staleWhileRevalidate(request, IMAGE_CACHE);
  trimCache(IMAGE_CACHE, MAX_IMAGE_CACHE_ENTRIES).catch(() => undefined);
  return response;
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(APP_SHELL_CACHE)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .catch(() => undefined)
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const cacheNames = await caches.keys();
    await Promise.all(
      cacheNames
        .filter((cacheName) => cacheName.startsWith('twc-') && ![
          APP_SHELL_CACHE,
          STATIC_CACHE,
          IMAGE_CACHE,
        ].includes(cacheName))
        .map((cacheName) => caches.delete(cacheName))
    );

    if (self.registration.navigationPreload) {
      try {
        await self.registration.navigationPreload.enable();
      } catch (_) {
        // Ignore unsupported browsers.
      }
    }

    await self.clients.claim();
  })());
});

self.addEventListener('push', (event) => {
  const payload = normalizePayload(event);
  const title = payload.title || 'TwoComms';
  const options = buildNotificationOptions(payload);

  event.waitUntil(
    self.registration.showNotification(title, options).then(() => (
      postDeliveryEvent('displayed', options.data.deliveryToken)
    ))
  );
});

self.addEventListener('notificationclick', (event) => {
  const data = (event.notification && event.notification.data) || {};
  const targetUrl = data.url || self.location.origin + '/';
  const deliveryToken = data.deliveryToken || '';

  event.notification.close();

  event.waitUntil(
    Promise.all([
      postDeliveryEvent('clicked', deliveryToken),
      focusOrOpenWindow(targetUrl),
    ])
  );
});

self.addEventListener('notificationclose', (event) => {
  const data = (event.notification && event.notification.data) || {};
  event.waitUntil(postDeliveryEvent('closed', data.deliveryToken || ''));
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  if (!url.protocol.startsWith('http')) {
    return;
  }

  if (!isSameOrigin(url)) {
    return;
  }

  if (request.method !== 'GET') {
    return;
  }

  if (isNavigationRequest(request)) {
    if (isExcludedNavigation(url)) {
      return;
    }

    event.respondWith(networkFirstNavigation(event));
    return;
  }

  if (shouldCacheStaticAsset(request, url)) {
    event.respondWith(staleWhileRevalidate(request, STATIC_CACHE));
    return;
  }

  if (shouldCacheImage(request, url)) {
    event.respondWith(cacheImages(request));
  }
});
