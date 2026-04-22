const SW_VERSION = '2026-04-22-push-v2';
const EVENTS_ENDPOINT = '/push/events/';

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

self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
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
  const url = new URL(event.request.url);

  if (!url.protocol.startsWith('http')) {
    return;
  }

  if (url.origin !== self.location.origin) {
    return;
  }
});
