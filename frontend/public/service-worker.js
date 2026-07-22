const CACHE_NAME = 'sirius-cache-v2';
const API_CACHE = 'sirius-api-v1';

const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json'
];

// API routes to cache for offline
const CACHEABLE_API = [
  '/api/auth/me',
  '/api/stats/dashboard',
  '/api/tasks',
  '/api/habits',
  '/api/goals',
  '/api/streaks/global',
  '/api/achievements/full',
  '/api/dashboard/weekly-summary',
  '/api/dashboard/daily-summary',
  '/api/stats/analytics'
];

// Install
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[SW] Caching static assets');
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

// Activate and clean old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((names) => {
      return Promise.all(
        names.map((name) => {
          if (name !== CACHE_NAME && name !== API_CACHE) {
            console.log('[SW] Deleting old cache:', name);
            return caches.delete(name);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Fetch strategy
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  if (request.method !== 'GET') return;

  // API calls: Network-first with cache fallback (stale-while-revalidate)
  if (url.pathname.startsWith('/api')) {
    const isCacheable = CACHEABLE_API.some(path => url.pathname.startsWith(path));
    
    if (isCacheable) {
      event.respondWith(
        fetch(request)
          .then((response) => {
            if (response && response.status === 200) {
              const clone = response.clone();
              caches.open(API_CACHE).then((cache) => {
                cache.put(request, clone);
              });
            }
            return response;
          })
          .catch(async () => {
            const cached = await caches.match(request);
            if (cached) {
              console.log('[SW] Serving cached API:', url.pathname);
              return cached;
            }
            return new Response(
              JSON.stringify({ error: 'Você está offline', offline: true }),
              { 
                status: 503,
                headers: { 'Content-Type': 'application/json' }
              }
            );
          })
      );
      return;
    }
    
    // Non-cacheable API: network only with offline error
    event.respondWith(
      fetch(request).catch(() => {
        return new Response(
          JSON.stringify({ error: 'Você está offline', offline: true }),
          { 
            status: 503,
            headers: { 'Content-Type': 'application/json' }
          }
        );
      })
    );
    return;
  }

  // Static assets: Cache-first with network fallback
  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;
      
      return fetch(request).then((response) => {
        if (!response || response.status !== 200) return response;
        
        // Cache JS, CSS, images, fonts
        const contentType = response.headers.get('content-type') || '';
        const shouldCache = contentType.includes('javascript') || 
                           contentType.includes('css') || 
                           contentType.includes('image') ||
                           contentType.includes('font');
        
        if (shouldCache) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(request, clone);
          });
        }
        
        return response;
      }).catch(() => {
        // If offline and requesting a page, serve index.html
        if (request.mode === 'navigate') {
          return caches.match('/index.html');
        }
        return new Response('Offline', { status: 503 });
      });
    })
  );
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
