const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../src/lib/module-requests.js'), 'utf8');
const context = vm.createContext({});
vm.runInContext(source.slice(source.indexOf('export function'), source.indexOf('const requests =')).replace('export function', 'function'), context);
test('module cache coalesces reads, invalidates mutations and rejects stale cache writes', async () => {
  let calls = 0, resolve;
  context.client = { get: () => { calls++; return new Promise(r => { resolve = r; }); }, post: async () => ({}) };
  const api = vm.runInContext('createModuleRequests(client)', context);
  const a = api.get('/studies'), b = api.get('/studies');
  assert.equal(a, b); assert.equal(calls, 1);
  api.invalidate(); resolve({ data: 'old account' }); await a;
  const c = api.get('/studies'); assert.equal(calls, 2); resolve({ data: 'new account' }); await c;
  await api.get('/studies'); assert.equal(calls, 2);
  await api.post('/studies', {});
  const d = api.get('/studies'); assert.equal(calls, 3); resolve({ data: 'new' }); await d;
});
