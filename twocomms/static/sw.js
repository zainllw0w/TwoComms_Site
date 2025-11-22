// Lightweight no-op Service Worker kept only to silence 404s.
// Version: 2025-11-22-clean
const SW_VERSION = '2025-11-22-clean';

self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(clients.claim());
});

// Guard fetch handler to avoid touching unsupported schemes (e.g., chrome-extension://).
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  if (!url.protocol.startsWith('http')) {
    return;
  }

  if (url.origin !== self.location.origin) {
    return;
  }
  // No respondWith -> let the browser handle normally; we just ensure safe early exits.
});
