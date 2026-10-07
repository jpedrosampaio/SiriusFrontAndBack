const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../src/lib/assistant-delivery.js'), 'utf8');
const helpers = import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
test('chat delivery errors distinguish session, concurrency, quota, availability and timeout', async () => {
  const { deliveryError } = await helpers;
  const errors = [401, 409, 429, 503, 504].map(status => deliveryError({ response: { status } }));
  assert.equal(new Set(errors).size, 5);
  assert.match(errors[0], /sessão expirou/);
  assert.match(deliveryError({ code: 'ECONNABORTED' }), /demorou/);
  assert.match(deliveryError({}), /conexão/);
  assert.doesNotMatch(deliveryError({ response: { status: 500, data: { detail: 'Traceback SECRET' } } }), /SECRET|Traceback/);
});
test('replay after lost response merges saved IDs exactly once', async () => {
  const { mergeReply } = await helpers;
  const reply = { user_message: { message_id: 'u', content: 'hello' }, ai_message: { message_id: 'a', content: 'reply' } };
  const first = mergeReply([{ message_id: 'before' }, { message_id: 'pending-id' }], reply, 'pending-id');
  const replay = mergeReply([...first, { message_id: 'pending-id' }], reply, 'pending-id');
  assert.deepEqual(replay, first);
});
