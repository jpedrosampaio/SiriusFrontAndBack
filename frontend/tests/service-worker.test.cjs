const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../public/service-worker.js'), 'utf8');

function harness(network = async () => new Response('online')) {
  const listeners = {};
  const stores = new Map();
  const calls = { reads: 0, writes: 0, fetch: [], claimed: false };
  function key(request) { return typeof request === 'string' ? request : request.url; }
  const caches = {
    async keys() { return [...stores.keys()]; },
    async delete(name) { return stores.delete(name); },
    async open(name) {
      if (!stores.has(name)) stores.set(name, new Map());
      const store = stores.get(name);
      return {
        async addAll() {},
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
      async skipWaiting() {},
      clients: { async claim() { calls.claimed = true; } }
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
        request,
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

test('activation purges all old Sirius private/static caches but preserves unrelated caches', async () => {
  const h = harness();
  for (const name of ['sirius-api-v1', 'sirius-api-v2', 'sirius-cache-v2',
                       'sirius-cache-v3', 'unrelated-cache']) h.stores.set(name, new Map());
  await h.dispatch('activate');
  assert.deepEqual([...h.stores.keys()].sort(), ['sirius-cache-v3', 'unrelated-cache']);
  assert.equal(h.calls.claimed, true);
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
  h.stores.set('sirius-cache-v3', new Map([[url, new Response('cached bundle')]]));
  const response = await h.dispatch('fetch', request(url));
  assert.equal(await response.text(), 'cached bundle');
  assert.equal(h.calls.fetch.length, 0);
});

test('online navigation fetches fresh HTML instead of an old cached entry', async () => {
  const h = harness(async () => new Response('fresh shell'));
  h.stores.set('sirius-cache-v3', new Map([['/index.html', new Response('old shell')]]));
  const response = await h.dispatch('fetch', request('https://app.test/', { mode: 'navigate' }));
  assert.equal(await response.text(), 'fresh shell');
  assert.equal(h.calls.fetch[0].options.cache, 'no-cache');
});

test('offline navigation retains shell fallback', async () => {
  const h = harness(offline);
  h.stores.set('sirius-cache-v3', new Map([['/index.html', new Response('app shell')]]));
  const response = await h.dispatch('fetch', request('https://app.test/tasks', { mode: 'navigate' }));
  assert.equal(await response.text(), 'app shell');
});

test('third-party resources and mutations are not intercepted', async () => {
  const h = harness();
  assert.equal(await h.dispatch('fetch', request('https://cdn.test/library.js')), undefined);
  assert.equal(await h.dispatch('fetch', request('https://backend.test/api/tasks', { method: 'POST' })), undefined);
  assert.equal(h.calls.fetch.length, 0);
});
