// Synthetic API, no production writes or providers. Exercise uncertain acceptance.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const root=path.join(process.cwd(),'build');
const server=http.createServer((req,res)=>{let file=path.join(root,new URL(req.url,'http://localhost').pathname);if(!file.startsWith(root+path.sep)){res.writeHead(403);return res.end();}if(!fs.existsSync(file)||fs.statSync(file).isDirectory())file=path.join(root,'index.html');res.setHeader('Content-Type',({'.js':'application/javascript','.css':'text/css','.html':'text/html'})[path.extname(file)]||'application/octet-stream');fs.createReadStream(file).pipe(res);});
(async()=>{await new Promise(r=>server.listen(4183,'127.0.0.1',r));const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});try{
for(const width of [1440,1024,768,390,320]){
 const context=await browser.newContext({viewport:{width,height:900},serviceWorkers:'block'});await context.addInitScript(()=>localStorage.setItem('sirius_onboarding_complete','true'));
 const errors=[],keys=[];let writes=0,failed=false,confirmed=false,simulations=0;
 const candidate=(id,domain,title,minutes,locked=false)=>({id,domain,title,source_id:id,duration_minutes:minutes,duration_origin:'recorded',date_locked:locked,latest:'2026-10-09',reasons:['Fato registrado'],link:'/tasks'});
 const candidates=[candidate('study','preparation','Revisão constitucional',45,true),candidate('task','tasks','Tarefa prioritária',30),candidate('workout','training','Treino selecionado',45)];
 const facts={preparation:{dated_blocks:1},finance:{recorded_net:'100.01'},training:{completed_today:0,available_plans:[]},nutrition:{water_ml:300},tasks:{},calendar:{commitments:1},habits:{completed_today:1,recorded:2},goals:{items:[]}};
 const state={date:'2026-10-09',timezone:'America/Sao_Paulo',fingerprint:'a'.repeat(64),planning_safe:true,warnings:[],availability:{weekdays:Array.from({length:7},()=>[{start_minute:1080,end_minute:1260}]),duration_estimates:{},training_plan_id:null},domains:Object.entries(facts).map(([domain,facts])=>({domain,facts,candidates:candidates.filter(c=>c.domain===domain),constraints:[],warnings:[]}))};
 const respond=(r,b,status=200)=>r.fulfill({status,contentType:'application/json',body:JSON.stringify(b)});
 await context.route('**/*',async r=>{const u=new URL(r.request().url()),p=u.pathname,m=r.request().method();if(!p.startsWith('/api/'))return u.hostname==='127.0.0.1'?r.continue():r.abort();
  if(p==='/api/auth/me')return respond(r,{user_id:'life-fixture',name:'User',rank:'Recruta'});
  if(p==='/api/calendar/events')return respond(r,{events:[]});
  if(p==='/api/life/state')return respond(r,state);
  if(p==='/api/life/availability'){assert.equal(m,'PUT');assert.ok(r.request().headers()['idempotency-key']);state.availability=r.request().postDataJSON();return respond(r,{availability:state.availability});}
  if(p==='/api/life/simulate'){
   simulations++;const scenario=r.request().postDataJSON();assert.equal(writes,0);
   const selected=candidates.filter(c=>!scenario.exclude.includes(c.id));let cursor=1080;
   const blocks=selected.map(c=>{const start=cursor;cursor+=c.duration_minutes;return {...c,candidate_id:c.id,task_id:c.id,start_minute:start,end_minute:cursor,duration_estimated:false,kind:'flexible_task',reason:'Prioridade por fatos reais'};});
   return respond(r,{state,plan:{scenario,fingerprint:state.fingerprint,blocks,available_minutes:180,planning_safe:true,conflicts:[],unscheduled:[],constraints:[{id:'fixed',title:'Compromisso fixo',start_minute:600,end_minute:660}],warnings:[]}});
  }
  if(p==='/api/life/accept'){
   const body=r.request().postDataJSON(),key=r.request().headers()['idempotency-key'];keys.push(key);assert.ok(key);assert.equal(body.confirmed,true);assert.equal(body.blocks.length,3);
   if(!confirmed){writes++;confirmed=true;}if(!failed){failed=true;return respond(r,{detail:'Synthetic uncertain acceptance'},504);}return respond(r,{event_ids:['e1','e2','e3'],replayed:true});
  }
  return respond(r,[]);
 });
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:4183/calendar');
 const panel=page.getByRole('region',{name:'Planejador global'});await panel.getByRole('heading',{name:'Seu dia integrado'}).waitFor();
 await panel.getByRole('button',{name:'Minha disponibilidade'}).click();await panel.getByRole('button',{name:'Salvar disponibilidade'}).click();await panel.getByRole('status').waitFor();
 await panel.getByText('Candidatos e cenário do dia',{exact:true}).click();assert.equal(await panel.getByRole('checkbox').first().isDisabled(),true);
 await panel.getByRole('button',{name:'Simular meu dia',exact:true}).click();await panel.getByRole('region',{name:'Resultado da simulação'}).waitFor();
 assert.equal(writes,0);assert.equal(simulations,1);await panel.getByText('10:00–11:00 · Compromisso fixo · fixo',{exact:true}).waitFor();
 const confirm=panel.getByRole('button',{name:'Confirmar estes horários na agenda',exact:true});await confirm.click();await panel.getByRole('alert').waitFor();await confirm.click();await panel.getByRole('status').waitFor();
 assert.equal(writes,1);assert.equal(keys.length,2);assert.equal(keys[0],keys[1]);assert.deepEqual(errors,[]);
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
 await panel.getByRole('button',{name:'Fechar disponibilidade',exact:true}).click();await panel.getByRole('heading',{name:'Seu dia integrado',exact:true}).scrollIntoViewIfNeeded();
 fs.mkdirSync('test-results',{recursive:true});await page.screenshot({path:`test-results/life-planner-${width}.png`});console.log(JSON.stringify({width,threeDomains:true,previewReadOnly:true,uncertainAcceptReplay:true,fixedPreserved:true,overflow:false}));await context.close();
}}finally{await browser.close();server.close();}})().catch(e=>{console.error(e);process.exitCode=1;server.close();});
