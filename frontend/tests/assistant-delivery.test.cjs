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
  const long = mergeReply(Array.from({length: 250}, (_, i) => ({message_id: String(i)})), reply, 'pending-id');
  assert.equal(long.length, 200);
  assert.deepEqual(long.slice(-2), [reply.user_message, reply.ai_message]);
});
test('late hydration preserves POST messages and known conversations without duplicates', async () => {
  const { mergeHistory, mergeConversations } = await helpers;
  const latest = [{ message_id: 'new-u', request_id: 'receipt' }, { message_id: 'new-a' }];
  const merged = mergeHistory([{ message_id: 'old' }], latest);
  assert.deepEqual(merged.map(m=>m.message_id), ['old','new-u','new-a']);
  assert.deepEqual(mergeHistory(merged,latest),merged);
  assert.deepEqual(mergeHistory(merged,[{message_id:'pending-receipt',request_id:'receipt'}]),merged);
  const list = mergeConversations([{conversation_id:'primary',title:'fallback'}],[{conversation_id:'other',title:'Known'},{conversation_id:'primary',title:'Actual title'}]);
  assert.deepEqual(list.map(c=>c.conversation_id),['primary','other']);
  assert.equal(list[0].title,'Actual title');
  assert.equal(mergeConversations(Array.from({length:35},(_,i)=>({conversation_id:String(i)})),[]).length,30);
});
