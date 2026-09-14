const CACHE_NAME = 'sirius-cache-v3';
const STATIC_ASSETS = ['/', '/index.html', '/manifest.json'];

// Cache only the application shell/assets, never authenticated API responses.
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((names) => Promise.all(
      names.filter((name) =>
        name.startsWith('sirius-api-') ||
        (name.startsWith('sirius-cache-') && name !== CACHE_NAME)
      ).map((name) => caches.delete(name))
    )).then(() => self.clients.claim())
  );
});

function offlineResponse() {
  return new Response(
    JSON.stringify({ error: 'Você está offline', offline: true }),
    { status: 503, headers: { 'Content-Type': 'application/json' } }
  );
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);
  if (request.method !== 'GET') return;

  // Do not read/write CacheStorage or the browser HTTP cache for private requests.
  if (/^\/api(?:\/|$)/.test(url.pathname) || request.headers.has('Authorization')) {
    event.respondWith(fetch(request, { cache: 'no-store' }).catch(offlineResponse));
    return;
  }

  // Third-party resources are not stored by this service worker.
  if (url.origin !== self.location.origin) return;

  // Refresh HTML online, keeping only the app shell as an offline fallback.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request, { cache: 'no-cache' }).catch(async () => {
        const cache = await caches.open(CACHE_NAME);
        return (await cache.match('/index.html')) || offlineResponse();
      })
    );
    return;
  }

  const isStatic = url.pathname.startsWith('/static/') ||
    url.pathname.startsWith('/icons/') || url.pathname === '/manifest.json';
  if (!isStatic) return;

  event.respondWith((async () => {
    const cache = await caches.open(CACHE_NAME);
    const cached = await cache.match(request);
    if (cached) return cached;
    try {
      const response = await fetch(request);
      if (response.status === 200) {
        const write = cache.put(request, response.clone()).catch(() => {});
        event.waitUntil(write);
      }
      return response;
    } catch {
      return new Response('Offline', { status: 503 });
    }
  })());
});

// Push notifications
self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : {};
  const options = {
    body: data.body || 'Nova notificação do Sirius',
    icon: '/icons/icon-192x192.png',
    badge: '/icons/icon-72x72.png',
    vibrate: [100, 50, 100],
    tag: data.tag || 'sirius-notification',
    data: { url: data.url || '/', dateOfArrival: Date.now() },
    actions: [
      { action: 'open', title: 'Abrir' },
      { action: 'close', title: 'Fechar' }
    ]
  };
  event.waitUntil(self.registration.showNotification(data.title || 'Sirius', options));
});

// Notification click
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = event.notification.data?.url || '/';
  event.waitUntil(self.clients.openWindow(url));
});
