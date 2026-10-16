const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../public/service-worker.js'), 'utf8');

function harness(network = async () => new Response('online')) {
  const listeners = {};
  const stores = new Map();
  const calls = { reads: 0, writes: 0, fetch: [], claimed: false, skipped: false };
  function key(request) { return typeof request === 'string' ? request : request.url; }
  const caches = {
    async keys() { return [...stores.keys()]; },
    async delete(name) { return stores.delete(name); },
    async open(name) {
      if (!stores.has(name)) stores.set(name, new Map());
      const store = stores.get(name);
      return {
        async addAll(urls) {
          const responses = await Promise.all(urls.map(url => network(url)));
          if (responses.some(response => !response.ok)) throw new TypeError('Precache failed');
          for (let index = 0; index < urls.length; index++) store.set(urls[index], responses[index].clone());
        },
        async match(request) {
          calls.reads++;
          return store.get(key(request))?.clone();
        },
        async put(request, response) { calls.writes++; store.set(key(request), response.clone()); }
      };
    },
    async match(request) {
      calls.reads++;
      for (const store of stores.values()) {
        const response = store.get(key(request));
        if (response) return response.clone();
      }
    }
  };
  vm.runInNewContext(source, {
    self: {
      location: { origin: 'https://app.test' },
      addEventListener(name, fn) { listeners[name] = fn; },
      async skipWaiting() { calls.skipped = true; },
      clients: { async claim() { calls.claimed = true; }, async openWindow(url) { calls.opened = url; } }
    },
    caches, URL, Response, console,
    fetch: async (request, options) => {
      calls.fetch.push({ request, options });
      return network(request, options);
    }
  });
  return {
    stores, calls,
    async dispatch(name, request) {
      const pending = [];
      let response;
      listeners[name]({
        request, ...(name === 'notificationclick' ? request : {}),
        waitUntil(promise) { pending.push(promise); },
        respondWith(promise) { response = promise; }
      });
      const result = await response;
      await Promise.all(pending);
      return result;
    }
  };
}
function request(url, options = {}) {
  return { url, method: options.method || 'GET', mode: options.mode || 'cors',
           headers: new Headers(options.headers) };
}
const offline = async () => { throw new TypeError('Network unavailable'); };

test('native click opens only the central and close action never navigates', async () => {
  const h = harness(); let closed = 0;
  await h.dispatch('notificationclick', { notification: { data: { url: 'https://untrusted.test' }, close() { closed++; } } });
  assert.equal(h.calls.opened, '/notifications'); assert.equal(closed, 1);
  delete h.calls.opened;
  await h.dispatch('notificationclick', { action: 'close', notification: { close() { closed++; } } });
  assert.equal(h.calls.opened, undefined); assert.equal(closed, 2);
});

test('activation purges all old Sirius private/static caches but preserves unrelated caches', async () => {
  const h = harness();
  for (const name of ['sirius-api-v1', 'sirius-api-v2', 'sirius-cache-v2',
                       'sirius-cache-v3', 'sirius-cache-v4', 'unrelated-cache']) h.stores.set(name, new Map());
  await h.dispatch('activate');
  assert.deepEqual([...h.stores.keys()].sort(), ['sirius-cache-v4', 'unrelated-cache']);
  assert.equal(h.calls.claimed, true);
});

test('installed v3 shell is replaced before subsequent offline navigation, retaining unrelated data', async () => {
  let online = true;
  const h = harness(async request => {
    if (!online) return offline();
    const url = new URL(typeof request === 'string' ? request : request.url, 'https://app.test');
    if (url.pathname === '/asset-manifest.json') return new Response(JSON.stringify({ entrypoints: ['static/js/main.new.js', 'static/css/main.new.css'] }));
    if (url.pathname.endsWith('.js')) return new Response('new boot JavaScript');
    if (url.pathname.endsWith('.css')) return new Response('new boot stylesheet');
    return new Response('clean zoom-enabled shell');
  });
  h.stores.set('sirius-cache-v3', new Map([['/index.html', new Response('legacy telemetry shell')]]));
  h.stores.set('unrelated-cache', new Map([['personal draft', new Response('preserved')]]));
  await h.dispatch('install');
  await h.dispatch('activate');
  online = false;
  const response = await h.dispatch('fetch', request('https://app.test/tasks', { mode: 'navigate' }));
  assert.equal(await response.text(), 'clean zoom-enabled shell');
  for (const [asset, contents] of [['/static/js/main.new.js', 'new boot JavaScript'], ['/static/css/main.new.css', 'new boot stylesheet']]) {
    const bundle = await h.dispatch('fetch', request('https://app.test' + asset));
    assert.equal(bundle.status, 200); assert.equal(await bundle.text(), contents);
  }
  assert.equal(h.stores.has('sirius-cache-v3'), false);
  assert.equal(await h.stores.get('unrelated-cache').get('personal draft').text(), 'preserved');
  assert.equal(h.calls.claimed, true);
  assert.equal(h.calls.skipped, true);
});

test('failed essential bundle prevents activation and leaves the installed old shell available', async () => {
  const h = harness(async request => {
    const url = new URL(typeof request === 'string' ? request : request.url, 'https://app.test');
    if (url.pathname === '/asset-manifest.json') return new Response(JSON.stringify({ entrypoints: ['static/js/missing.js'] }));
    if (url.pathname.endsWith('.js')) return new Response('Unavailable', { status: 503 });
    return new Response('new shell');
  });
  h.stores.set('sirius-cache-v3', new Map([['/index.html', new Response('installed old shell')]]));
  await assert.rejects(h.dispatch('install'), /Precache failed/);
  assert.equal(h.calls.skipped, false); assert.equal(h.calls.claimed, false);
  assert.equal(await h.stores.get('sirius-cache-v3').get('/index.html').text(), 'installed old shell');
});

test('precache rejects private, external and excessive manifest entrypoints before fetching assets', async () => {
  for (const entrypoints of [['/api/auth/me'], ['https://external.test/static/main.js'], Array(33).fill('static/js/main.js')]) {
    const h = harness(async () => new Response(JSON.stringify({ entrypoints })));
    await assert.rejects(h.dispatch('install'), /Invalid shell/);
    assert.equal(h.calls.fetch.length, 1); assert.equal(h.calls.writes, 0);
    assert.equal(h.calls.skipped, false);
  }
});

test('offline account switch cannot return a previous account API response', async () => {
  for (const origin of ['https://app.test', 'https://backend.test']) {
    const url = origin + '/api/auth/me';
    const h = harness(offline);
    h.stores.set('sirius-api-v1', new Map([[url, new Response('private data from Alice')]]));
    const response = await h.dispatch('fetch', request(url, {
      headers: { Authorization: 'Bearer bob' }
    }));
    assert.equal(response.status, 503);
    assert.equal((await response.json()).offline, true);
    assert.equal(h.calls.reads, 0);
    assert.equal(h.calls.writes, 0);
    assert.equal(h.calls.fetch[0].options.cache, 'no-store');
  }
});

test('API responses never enter CacheStorage, including cookie-authenticated requests', async () => {
  const h = harness(async () => new Response('private'));
  const response = await h.dispatch('fetch', request('https://backend.test/api/tasks'));
  assert.equal(await response.text(), 'private');
  assert.equal(h.calls.writes, 0);
  assert.equal(h.calls.reads, 0);
  assert.equal(h.calls.fetch[0].options.cache, 'no-store');
});

test('server authentication failures pass through instead of returning cached data', async () => {
  const h = harness(async () => new Response('Unauthorized', { status: 401 }));
  const response = await h.dispatch('fetch', request('https://backend.test/api/auth/me'));
  assert.equal(response.status, 401);
  assert.equal(h.calls.reads, 0);
});

test('Authorization outside /api also bypasses caches', async () => {
  const h = harness(offline);
  const response = await h.dispatch('fetch', request('https://app.test/static/private.json', {
    headers: { Authorization: 'Bearer bob' }
  }));
  assert.equal(response.status, 503);
  assert.equal(h.calls.reads, 0);
});

test('static assets continue to work offline', async () => {
  const h = harness(offline);
  const url = 'https://app.test/static/js/main.hash.js';
  h.stores.set('sirius-cache-v4', new Map([[url, new Response('cached bundle')]]));
  const response = await h.dispatch('fetch', request(url));
  assert.equal(await response.text(), 'cached bundle');
  assert.equal(h.calls.fetch.length, 0);
});

test('online navigation fetches fresh HTML instead of an old cached entry', async () => {
  const h = harness(async () => new Response('fresh shell'));
  h.stores.set('sirius-cache-v4', new Map([['/index.html', new Response('old shell')]]));
  const response = await h.dispatch('fetch', request('https://app.test/', { mode: 'navigate' }));
  assert.equal(await response.text(), 'fresh shell');
  assert.equal(h.calls.fetch[0].options.cache, 'no-cache');
});

test('offline navigation retains shell fallback', async () => {
  const h = harness(offline);
  h.stores.set('sirius-cache-v4', new Map([['/index.html', new Response('app shell')]]));
  const response = await h.dispatch('fetch', request('https://app.test/tasks', { mode: 'navigate' }));
  assert.equal(await response.text(), 'app shell');
});

test('third-party resources and mutations are not intercepted', async () => {
  const h = harness();
  assert.equal(await h.dispatch('fetch', request('https://cdn.test/library.js')), undefined);
  assert.equal(await h.dispatch('fetch', request('https://backend.test/api/tasks', { method: 'POST' })), undefined);
  assert.equal(h.calls.fetch.length, 0);
});
