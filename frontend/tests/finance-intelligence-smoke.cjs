// Synthetic API only. Read-only analysis must never hit a money mutation endpoint.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require('playwright');const root=path.join(process.cwd(),'build');
const server=http.createServer((req,res)=>{let file=path.join(root,new URL(req.url,'http://localhost').pathname);if(!file.startsWith(root+path.sep)){res.writeHead(403);return res.end();}if(!fs.existsSync(file)||fs.statSync(file).isDirectory())file=path.join(root,'index.html');res.setHeader('Content-Type',({'.js':'application/javascript','.css':'text/css','.html':'text/html'})[path.extname(file)]||'application/octet-stream');fs.createReadStream(file).pipe(res);});
(async()=>{await new Promise(r=>server.listen(4184,'127.0.0.1',r));const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});try{
for(const width of [1440,1024,768,390,320]){
 const context=await browser.newContext({viewport:{width,height:900},serviceWorkers:'block'});await context.addInitScript(()=>localStorage.setItem('sirius_onboarding_complete','true'));
 let simulations=0,comparisons=0,stateReads=0,billReads=0;const errors=[],unexpectedWrites=[];
 const row={month:'2026-10-01',recorded_future_income:'0.00',recorded_future_expense:'0.00',estimated_expense:'100.00',scenario_income:'0.00',scenario_expense:'0.00',net_change:'-100.00',cumulative_change:'-100.00',scenario_balance:null};
 const forecast={months:[row],assumptions:['Only known recorded sources'],end:'2027-03-31'};
 const state={as_of:'2026-10-08',timezone:'America/Sao_Paulo',income:'1000.00',expense:'100.10',recorded_net:'899.90',complete:true,fingerprint:'a'.repeat(64),warnings:[],budgets:[],goals:[],debts:[],insights:[],upcoming_bills:[],forecast};
 const respond=(r,b,status=200)=>r.fulfill({status,contentType:'application/json',body:JSON.stringify(b)});
 await context.route('**/*',async r=>{const u=new URL(r.request().url()),p=u.pathname,m=r.request().method();if(!p.startsWith('/api/'))return u.hostname==='127.0.0.1'?r.continue():r.abort();
  if(m!=='GET'&&!['/api/finance/intelligence/simulate','/api/finance/intelligence/compare-debts'].includes(p)){unexpectedWrites.push(p);return respond(r,{detail:'Unexpected write'},500);}
  if(p==='/api/auth/me')return respond(r,{user_id:'finance-fixture',name:'Finance',rank:'Recruta'});
  if(p==='/api/finance/intelligence/state'){stateReads++;return respond(r,state);}
  if(p==='/api/finance/intelligence/simulate'){
   simulations++;const body=r.request().postDataJSON();assert.equal(body.monthly_expense,'500.00');assert.equal(body.opening_balance,'1000.00');assert.equal(body.fingerprint,state.fingerprint);
   if(simulations===1)return respond(r,{detail:'Synthetic retryable analysis failure'},504);
   return respond(r,{read_only:true,baseline:forecast,scenario:{...forecast,months:[{...row,scenario_expense:'500.00',net_change:'-600.00',cumulative_change:'-600.00',scenario_balance:'400.00'}]}});
  }
  if(p==='/api/finance/intelligence/compare-debts'){
   comparisons++;const body=r.request().postDataJSON();assert.equal(body.monthly_payment,'20.00');assert.equal(body.debts[0].principal,'100.10');assert.equal(body.debts[0].monthly_rate_percent,null);
   return respond(r,{read_only:true,results:['snowball','avalanche','custom'].map(strategy=>({strategy,status:'unknown_rates',payoff_months:null,total_interest:null,remaining:'100.10',order:strategy==='avalanche'?null:body.custom_order,timeline:[]}))});
  }
  if(p==='/api/finance/stats')return respond(r,{total_income:1000,total_expense:100.1,balance:899.9,by_category:{}});
  if(p==='/api/finance/trend')return respond(r,{trend:[],summary:{}});
  if(p==='/api/finance/monthly-bills'){billReads++;return respond(r,{bills:[],total:0,total_paid:0,total_pending:0,count:0,paid_count:0});}
  if(p==='/api/projections/summary')return respond(r,{categories_totals:{},fixed_expenses:0,installment_expenses:0,manual_expenses:0,total_projected_expenses:0,estimated_income:0,estimated_balance:0});
  return respond(r,[]);
 });
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:4184/finance');
 const panel=page.getByRole('region',{name:'Inteligência financeira',exact:true});await panel.getByText('R$ 899,90',{exact:true}).waitFor();
 assert.equal(stateReads,1);
 state.recorded_net='799.90';state.expense='200.10';
 await page.evaluate(()=>{window.dispatchEvent(new Event('sirius-data-changed'));window.dispatchEvent(new Event('sirius-data-changed'));});
 await panel.getByText('R$ 799,90',{exact:true}).waitFor();assert.equal(stateReads,2);
 await panel.getByRole('tab',{name:'Cenários',exact:true}).click();await panel.getByLabel('Saldo inicial do cenário',{exact:true}).fill('1000.00');await panel.getByLabel('Despesa mensal hipotética',{exact:true}).fill('500.00');
 await panel.getByRole('button',{name:'Simular fluxo sem gravar'}).click();await panel.getByRole('alert').waitFor();assert.equal(await panel.getByLabel('Despesa mensal hipotética',{exact:true}).inputValue(),'500.00');
 await panel.getByRole('button',{name:'Simular fluxo sem gravar'}).click();await panel.getByRole('region',{name:'Resultado do cenário financeiro'}).waitFor();await panel.getByText('R$ 400,00',{exact:true}).waitFor();
 await panel.getByRole('tab',{name:'Dívidas',exact:true}).click();await panel.getByLabel('Nome',{exact:true}).fill('Declarada');await panel.getByLabel('Principal declarado',{exact:true}).fill('100.10');await panel.getByLabel('Valor mensal disponível no modelo',{exact:true}).fill('20.00');
 await panel.getByRole('button',{name:'Comparar estratégias sem gravar'}).click();await panel.getByRole('region',{name:'Resultado das estratégias de dívida'}).waitFor();assert.equal(await panel.getByText('Taxas incompletas: prazo e juros não calculados',{exact:true}).count(),3);
 assert.deepEqual(unexpectedWrites,[]);assert.deepEqual(errors,[]);assert.equal(simulations,2);assert.equal(comparisons,1);assert.equal(stateReads,2);
 state.recorded_net='699.90';state.expense='300.10';
 await page.getByRole('tab',{name:'Contas do Mês',exact:true}).click();
 await panel.getByText('R$ 699,90',{exact:true}).waitFor().catch(async error=>{console.error({billReads,stateReads,errors});throw error;});assert.equal(stateReads,3);
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
 await panel.getByRole('tab',{name:'Fluxo previsto',exact:true}).click();await panel.getByRole('heading',{name:'Inteligência financeira',exact:true}).scrollIntoViewIfNeeded();fs.mkdirSync('test-results',{recursive:true});await page.screenshot({path:`test-results/finance-intelligence-${width}.png`});
 console.log(JSON.stringify({width,decimalStrings:true,unknownRates:true,readonlyScenarios:true,retryPreservesInputs:true,overflow:false}));await context.close();
}}finally{await browser.close();server.close();}})().catch(e=>{console.error(e);process.exitCode=1;server.close();});
