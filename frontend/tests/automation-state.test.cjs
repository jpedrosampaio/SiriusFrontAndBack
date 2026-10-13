const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../src/lib/automation-state.js'),'utf8');
const load=()=>import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
test('unknown delivery is never labeled confirmed',async()=>{
  const {deliveryLabels}=await load();assert.equal(deliveryLabels.uncertain,'Entrega não confirmada');
  assert.notEqual(deliveryLabels.available,deliveryLabels.delivered);
});
test('receipt intents distinguish explicit risk confirmation and resources',async()=>{
  const {receiptIntent}=await load();assert.notEqual(receiptIntent('retry','a',false),receiptIntent('retry','a',true));
  assert.notEqual(receiptIntent('read','a'),receiptIntent('read','b'));
});
