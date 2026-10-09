const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../src/lib/finance-money.js'),'utf8').replaceAll('export ','');
const context=vm.createContext({});vm.runInContext(source,context);
test('Decimal money strings retain cents beyond JS safe integer and unknown stays unknown',()=>{
 assert.equal(context.formatBRL('9007199254740993.01'),'R$ 9.007.199.254.740.993,01');
 assert.equal(context.formatBRL('-1000.10'),'-R$ 1.000,10');assert.equal(context.formatBRL('0.1'),'R$ 0,10');
 assert.equal(context.formatBRL(null),'Não informado');assert.equal(context.formatBRL('NaN'),'Valor indisponível');
});
