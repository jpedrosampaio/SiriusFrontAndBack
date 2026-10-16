const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../src/lib/native-notice.js'), 'utf8').replace('export async function', 'async function');
function fixture(registration, constructorFails = false, timers) {
  const calls = [];
  const context = vm.createContext({ navigator: { serviceWorker: { async getRegistration() { return registration; } } },
    Notification: class { constructor() { if (constructorFails) throw new TypeError('Use SW'); calls.push(this); } close() { this.closed = true; } },
    setTimeout: timers?.setTimeout || setTimeout, clearTimeout: timers?.clearTimeout || clearTimeout });
  vm.runInContext(source, context);
  return { show: context.presentNativeNotice, calls };
}
const options = { tag: 'owned', data: { presentation_token: 'first' } };
test('mobile uses an existing service worker even when the constructor is unsupported', async () => {
  let shown = 0, closed = 0;
  const h = fixture({ async showNotification() { shown++; }, async getNotifications() { return [
    { data: { presentation_token: 'first' }, close() { closed++; } },
    { data: { presentation_token: 'second' }, close() { throw Error('must preserve newer notice'); } } ]; } }, true);
  const result = await h.show('Notice', options, () => true, () => {});
  assert.equal(result.outcome, 'accepted'); assert.equal(shown, 1); assert.equal(h.calls.length, 0);
  await result.close(); assert.equal(closed, 1);
});
test('known API rejection can fall back; failure of both APIs remains retryable, never accepted', async () => {
  const registration = { async showNotification() { throw Error('Unavailable'); } };
  const desktop = fixture(registration);
  assert.equal((await desktop.show('Notice', options, () => true, () => {})).outcome, 'accepted');
  assert.equal(desktop.calls.length, 1);
  assert.equal((await fixture(registration, true).show('Notice', options, () => true, () => {})).outcome, 'failed');
});
test('an ambiguous SW timeout does not fall back and late acceptance after logout closes only the old token', async () => {
  let resolve, current = true, closed = 0;
  const h = fixture({ showNotification() { return new Promise(r => { resolve = r; }); },
    async getNotifications() { return [{ data: options.data, close() { closed++; } }]; } }, false,
    { setTimeout(fn, delay) { return setTimeout(fn, delay === 5000 ? 1 : delay); }, clearTimeout });
  assert.equal((await h.show('Notice', options, () => current, () => {})).outcome, 'uncertain');
  assert.equal(h.calls.length, 0); current = false; resolve(); await new Promise(r => setImmediate(r));
  assert.equal(closed, 1);
});
test('account invalidation before presentation prevents either native API from being used', async () => {
  const h = fixture({ async showNotification() { throw Error('must not call'); } });
  assert.equal((await h.show('Notice', options, () => false, () => {})).outcome, 'uncertain');
  assert.equal(h.calls.length, 0);
});
