const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const source = fs.readFileSync(require('node:path').join(__dirname, '../src/lib/daily-workout-queue.js'), 'utf8');
const helpers = import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const tick = () => new Promise(resolve => setImmediate(resolve));
test('three rapid clicks project immediately and write serially; middle failure rolls back only itself', async () => {
  const { createDailyWorkoutQueue } = await helpers;
  let state, n = 0;
  const calls = [], pending = [], errors = [];
  const queue = createDailyWorkoutQueue({ uuid: () => String(++n), publish: (_, value) => state = value,
    failed: e => errors.push(e), write: (_, index, key) => { calls.push({ index, key }); return new Promise((resolve, reject) => pending.push({resolve, reject})); } });
  queue.enqueue('p',0); queue.enqueue('p',1); queue.enqueue('p',2);
  assert.deepEqual(state.exercises_status, {0:true,1:true,2:true}); assert.equal(calls.length,1);
  pending[0].resolve({exercises_status:{0:true}}); await tick();
  assert.deepEqual(state.exercises_status,{0:true,1:true,2:true}); assert.equal(calls.length,2);
  pending[1].reject({response:{status:409}}); await tick();
  assert.deepEqual(state.exercises_status,{0:true,2:true}); assert.equal(calls.length,3);
  pending[2].resolve({exercises_status:{0:true,2:true}}); await tick();
  assert.deepEqual(calls.map(c=>c.index),[0,1,2]); assert.equal(new Set(calls.map(c=>c.key)).size,3);
  assert.equal(errors.length,1); assert.equal(queue.busy('p'),false);
});
test('ambiguous response pauses later writes; retry reuses receipt key and preserves both clicks', async () => {
  const { createDailyWorkoutQueue } = await helpers;
  let state, retry, n=0;
  const calls=[], pending=[];
  const queue=createDailyWorkoutQueue({uuid:()=>String(++n),publish:(_,v)=>state=v,failed:(_,r)=>retry=r,
    write:(_,index,key)=>{calls.push({index,key});return new Promise((resolve,reject)=>pending.push({resolve,reject}));}});
  queue.enqueue('p',0);queue.enqueue('p',1);
  pending[0].reject(new Error('network'));await tick();
  assert.equal(calls.length,1);assert.deepEqual(state.exercises_status,{0:true,1:true});
  retry();pending[1].resolve({exercises_status:{0:true}});await tick();
  assert.equal(calls[0].key,calls[1].key);assert.equal(calls[2].index,1);
  pending[2].resolve({exercises_status:{0:true,1:true}});await tick();
  assert.deepEqual(state.exercises_status,{0:true,1:true});assert.equal(queue.busy('p'),false);
});
test('two touches on same exercise retain both toggles; independent plans progress in parallel', async () => {
  const { createDailyWorkoutQueue }=await helpers;
  const writes=[],state={};let i=0;
  const queue=createDailyWorkoutQueue({uuid:()=>String(++i),publish:(id,v)=>state[id]=v,failed:()=>{},write:(id,index,key)=>new Promise(resolve=>writes.push({id,index,key,resolve}))});
  queue.enqueue('a',0);queue.enqueue('a',0);queue.enqueue('b',1);
  assert.deepEqual(state.a.exercises_status,{});assert.equal(writes.length,2);
  writes[0].resolve({exercises_status:{0:true}});await tick();
  writes[2].resolve({exercises_status:{}});writes[1].resolve({exercises_status:{1:true}});await tick();
  assert.deepEqual(state.a.exercises_status,{});assert.deepEqual(state.b.exercises_status,{1:true});
});
