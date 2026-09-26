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
  pending[0]({ data: { user_id: 'old' } }); await route;
  const next = vm.runInContext('getCurrentUser()', context);
  assert.equal(pending.length, 2);
  pending[1]({ data: { user_id: 'new' } }); await next;
  assert.equal((await vm.runInContext('getCurrentUser()', context)).data.user_id, 'new');
  assert.equal(pending.length, 2);
});
