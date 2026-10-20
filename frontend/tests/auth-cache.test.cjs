const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../src/lib/api.js'), 'utf8')
  .replace(/^import .*;$/gm, '').replace(/^export \{.*\};$/gm, '').replace(/^export default .*;$/gm, '').replace(/^export /gm, '');

test('route and page share one request; a late response cannot repopulate cache after account change', async () => {
  const pending = [], storage = new Map();
  const context = vm.createContext({
    axios: { get() { return new Promise(resolve => pending.push(resolve)); }, interceptors: { request: { use() {} }, response: { use() {} } } },
    process: { env: {} }, OFFLINE_MODE: false, OFFLINE_USER: {}, OFFLINE_DEMO_DATA: {}, getApiErrorMessage() {},
    localStorage: { getItem: key => storage.get(key), setItem: (k, v) => storage.set(k, v), removeItem: k => storage.delete(k) },
    window: { addEventListener() {}, dispatchEvent() {} }, Event,
  });
  vm.runInContext(source, context);
  const route = vm.runInContext('getCurrentUser()', context);
  const page = vm.runInContext('getCurrentUser()', context);
  assert.equal(route, page); assert.equal(pending.length, 1);
  vm.runInContext('setToken("another-account")', context);
  pending[0]({ data: { user_id: 'old' } });
  await assert.rejects(route, error => error.code === 'ERR_CANCELED');
  const next = vm.runInContext('getCurrentUser()', context);
  assert.equal(pending.length, 2);
  pending[1]({ data: { user_id: 'new' } }); await next;
  assert.equal((await vm.runInContext('getCurrentUser()', context)).data.user_id, 'new');
  assert.equal(pending.length, 2);
});

function client() {
  const pending = [], storage = new Map(), saved = new Map(), listeners = new Map();
  let requestHook, successHook, errorHook;
  const window = { location: { pathname: '/dashboard', href: '' },
    sessionStorage: { removeItem(key) { saved.delete(key); } },
    addEventListener(name, fn) { listeners.set(name, [...(listeners.get(name) || []), fn]); },
    dispatchEvent(event) { for (const fn of listeners.get(event.type) || []) fn(event); },
  };
  const axios = {
    get(url, config = {}) {
      const stamped = requestHook({ method: 'get', headers: {}, url, ...config });
      return new Promise((resolve, reject) => pending.push({
        resolve: data => resolve({ data, config: stamped }),
        reject: status => reject({ response: { status }, config: stamped }),
      })).then(successHook, errorHook);
    },
    interceptors: { request: { use(fn) { requestHook = fn; } }, response: { use(ok, error) { successHook = ok; errorHook = error; } } },
  };
  const context = vm.createContext({ axios, process: { env: {} }, OFFLINE_MODE: false, OFFLINE_USER: {}, OFFLINE_DEMO_DATA: {},
    getApiErrorMessage() { return ''; }, localStorage: { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) }, window, Event });
  vm.runInContext(source, context);
  return { run: expression => vm.runInContext(expression, context), pending, storage, saved, window, listeners, axios,
    request: config => requestHook({ headers: {}, ...config }), success: response => successHook(response) };
}

test('late domain data and old 401 are discarded without clearing the new account', async () => {
  const c = client(); c.run('setToken("alice-test-only")');
  const data = c.axios.get('/api/finance/transactions');
  const expired = c.axios.get('/api/auth/me');
  const rejected = Promise.all([assert.rejects(data, e => e.code === 'ERR_CANCELED'), assert.rejects(expired, e => e.code === 'ERR_CANCELED')]);
  c.run('setToken("bob-test-only")');
  c.pending[0].resolve([{ amount: '999.99', owner: 'alice' }]); c.pending[1].reject(401);
  await rejected;
  assert.equal(c.storage.get('sirius_session_token'), 'bob-test-only');
  assert.equal(c.window.location.href, '');
  const current = c.run('getCurrentUser()'); c.pending[2].resolve({ user_id: 'bob' });
  assert.equal((await current).data.user_id, 'bob');
});

test('storage account changes and logout reject pending profile consumers', async () => {
  const c = client(); c.run('setToken("alice-test-only")');
  const first = c.run('getCurrentUser()'); const rejected = assert.rejects(first, e => e.code === 'ERR_CANCELED');
  c.saved.set('sirius-conversation', 'alice-private-conversation');
  c.storage.set('sirius_session_token', 'bob-test-only');
  c.window.dispatchEvent({ type: 'storage', key: 'sirius_session_token' });
  assert.equal(c.saved.has('sirius-conversation'), false);
  c.pending[0].resolve({ user_id: 'alice' }); await rejected;
  const second = c.run('getCurrentUser()'); const loggedOut = assert.rejects(second, e => e.code === 'ERR_CANCELED');
  c.run('clearToken()'); c.pending[1].resolve({ user_id: 'bob' }); await loggedOut;
  assert.equal(c.storage.has('sirius_session_token'), false);
});

test('same-account mutations keep concurrent reads valid, while current 401 still expires the session', async () => {
  const c = client(); c.run('setToken("alice-test-only")');
  const reading = c.axios.get('/api/finance/transactions');
  const change = c.request({ url: '/api/tasks', method: 'post' });
  c.success({ data: { task_id: 'owned' }, config: change });
  c.pending[0].resolve([{ amount: '0.30' }]); assert.equal((await reading).data[0].amount, '0.30');
  const expired = c.axios.get('/api/auth/me'); const rejected = assert.rejects(expired, e => e.response?.status === 401);
  c.pending[1].reject(401); await rejected;
  assert.equal(c.storage.has('sirius_session_token'), false); assert.equal(c.window.location.href, '/login');
});

test('repeated anonymous 401 responses invalidate authentication only once', async () => {
  const c = client(); c.window.location.pathname = '/login';
  let changes = 0; c.window.addEventListener('sirius-auth-changed', () => { changes += 1; });
  for (let index = 0; index < 4; index += 1) {
    const request = c.axios.get('/api/automations/state');
    const rejected = assert.rejects(request, error => error.response?.status === 401);
    c.pending[index].reject(401); await rejected;
  }
  assert.equal(changes, 1, 'Anonymous polling must not feed an auth-change -> immediate poll loop');
  assert.equal(c.window.location.href, '');
  c.run('setToken("new-owner-test-only")');
  c.window.location.pathname = '/dashboard';
  const nextSession = c.axios.get('/api/automations/state');
  const expired = assert.rejects(nextSession, error => error.response?.status === 401);
  c.pending[4].reject(401); await expired;
  assert.equal(changes, 3, 'A new token must retain its own expiry invalidation');
  assert.equal(c.storage.has('sirius_session_token'), false);
  assert.equal(c.window.location.href, '/login');
});

test('successful cookie reauthentication rearms expiry without accepting stale domain data', async () => {
  const c = client(); c.window.location.pathname = '/login';
  let changes = 0; c.window.addEventListener('sirius-auth-changed', () => { changes += 1; });
  const anonymous = c.axios.get('/api/automations/state');
  const rejected = assert.rejects(anonymous, error => error.response?.status === 401);
  c.pending[0].reject(401); await rejected;
  const cookieLogin = c.run('getCurrentUser()');
  c.pending[1].resolve({ user_id: 'cookie-owner' }); await cookieLogin;
  assert.equal(c.storage.has('sirius_session_token'), false, 'Cookie-only authentication stays supported');
  c.saved.set('sirius-conversation', 'cookie-owner-private');
  c.window.location.pathname = '/dashboard';
  const privateRead = c.axios.get('/api/finance/transactions');
  const stale = assert.rejects(privateRead, error => error.code === 'ERR_CANCELED');
  const expired = c.axios.get('/api/automations/state');
  const expiry = assert.rejects(expired, error => error.response?.status === 401);
  c.pending[3].reject(401); await expiry;
  c.pending[2].resolve([{ owner: 'cookie-owner', amount: '10.00' }]); await stale;
  assert.equal(changes, 2);
  assert.equal(c.saved.has('sirius-conversation'), false);
  assert.equal(c.window.location.href, '/login');
});

test('owned cookie notification configuration rearms expiry on a public page', async () => {
  const c = client(); c.window.location.pathname = '/login';
  let changes = 0; c.window.addEventListener('sirius-auth-changed', () => { changes += 1; });
  const anonymous = c.axios.get('/api/automations/state');
  const rejected = assert.rejects(anonymous, error => error.response?.status === 401);
  c.pending[0].reject(401); await rejected;
  const owned = c.axios.get('/api/automations/state');
  c.pending[1].resolve({ user_id: 'cookie-owner', enabled: false }); await owned;
  c.saved.set('sirius-conversation', 'owned-cookie-state');
  const expired = c.axios.get('/api/automations/state');
  const expiry = assert.rejects(expired, error => error.response?.status === 401);
  c.pending[2].reject(401); await expiry;
  assert.equal(changes, 2);
  assert.equal(c.saved.has('sirius-conversation'), false);
});
