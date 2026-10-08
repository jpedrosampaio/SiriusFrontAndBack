const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const root=path.join(process.cwd(),'build');
const server=http.createServer((req,res)=>{let file=path.join(root,new URL(req.url,'http://localhost').pathname);if(!file.startsWith(root+path.sep)){res.writeHead(403);return res.end();}if(!fs.existsSync(file)||fs.statSync(file).isDirectory())file=path.join(root,'index.html');res.setHeader('Content-Type',({'.js':'application/javascript','.css':'text/css','.html':'text/html'})[path.extname(file)]||'application/octet-stream');fs.createReadStream(file).pipe(res);});
(async()=>{await new Promise(r=>server.listen(4180,'127.0.0.1',r));const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});try{
for(const width of [1440,1024,768,390,320]){
 const context=await browser.newContext({viewport:{width,height:900}});await context.addInitScript(()=>localStorage.setItem('token','synthetic-test'));
 let simulations=0,planWrites=0,fail=true;const errors=[],keys=[];
 const program={program_id:'demo',name:'Preparation',target_date:'2026-12-01'},discipline={notebook_id:'nb0',name:'Portuguese',conteudo_programatico:[{assunto:'Crase',subtopicos:[]}],topicos:[]};
 const settings={start_date:'2026-10-08',end_date:'2026-10-21',availability:[60,60,60,60,60,0,0],block_minutes:50,adaptive:true};
 const scenario=(minutes)=>({minutes,projected_coverage:50,new_topics_assuming_completion:1,protected_minutes:25,unaddressed_due_reviews:[],unaddressed_critical_topics:[],load_guard:{warnings:[{code:'above_recent_pattern',message:'Carga planejada acima do seu padrão recente.'}]},entries:[],entries_count:0});
 const strategy={coverage_partial:true,topicless_disciplines:[{id:'nbLegacy',title:'Legacy'}],settings,scenarios:{A:scenario(300),B:scenario(225),C:scenario(125)},debt:{overdue_reviews:['t1'],critical_unstarted:['t1'],missed_blocks:[{minutes:50}],missed_minutes:50,late_milestones:[]},assumptions:['Simulation never changes your facts.'],notice:'Operational heuristic',candidates:[{id:'t1',topic_id:'t1',scope:'topic',notebook_id:'nb0',topic_key:'0',title:'Crase',discipline:'Portuguese',risk:60,expected_return:.04,impact:1,cost_minutes:50,review_interval_days:3,reasons:['Sem amostra de domínio','Peso registrado a conferir'],risk_components:{coverage:15,mastery_gap:15},evidence_ids:['e1'],urgency_multiplier:1.2},{id:'notebook:nbLegacy',topic_id:null,scope:'discipline',notebook_id:'nbLegacy',topic_key:null,title:'Distribuição por disciplina',discipline:'Legacy',risk:40,expected_return:.01,impact:1,cost_minutes:50,review_interval_days:null,reasons:['Sem assuntos cadastrados'],risk_components:{insufficient_evidence:10},evidence_ids:[],urgency_multiplier:1}]};
 const respond=(r,b,status=200)=>r.fulfill({status,contentType:'application/json',body:JSON.stringify(b)});
 await context.route('**/*',async r=>{const url=new URL(r.request().url()),p=url.pathname,m=r.request().method();if(!p.startsWith('/api/'))return url.hostname==='127.0.0.1'?r.continue():r.abort();
  if(p==='/api/auth/me')return respond(r,{user_id:'fixture',name:'User',rank:'Recruta'});
  if(p.endsWith('/strategy/simulate')){simulations++;assert.equal(m,'POST');const body=r.request().postDataJSON();assert.equal(body.missed_days,7);assert.equal(body.availability[5],240);await new Promise(resolve=>setTimeout(resolve,100));return respond(r,{...strategy,scenarios:{...strategy.scenarios,A:scenario(180)}});}
  if(p.endsWith('/strategy'))return respond(r,strategy);
  if(p.endsWith('/dated-plan')){if(m==='POST'){planWrites++;keys.push(r.request().headers()['idempotency-key']);const body=r.request().postDataJSON();assert.equal(body.adaptive,true);assert.equal(body.recovery,true);if(fail){fail=false;return respond(r,{detail:'Synthetic delivery uncertainty'},504);}return respond(r,{settings:body,entries:[{entry_id:'saved',notebook_id:'nb0',topic_id:'t1',topic_key:'0',date:'2026-10-08',name:'Portuguese · Crase',kind:'Teoria e questões',minutes:50,completed:false,manual:false,fixed:false}]});}return respond(r,{settings:null,entries:[]});}
  if(p.endsWith('/cronograma'))return respond(r,{program,notebooks:[discipline],cronograma:[]});
  if(p.endsWith('/edital-verticalizado'))return respond(r,{disciplinas:[discipline]});
  if(p==='/api/study/programs')return respond(r,[program]);
  if(p==='/api/study/notebooks')return respond(r,[discipline]);
  if(p==='/api/study/areas')return respond(r,[{area_id:'area1',name:'Area'}]);
  if(p.includes('stats')||p.includes('streak')||p.endsWith('/overview'))return respond(r,{});
  return respond(r,[]);
 });
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:4180/studies?program=demo&view=cronograma');
 const section=page.getByRole('region',{name:'Estratégia adaptativa'});await section.getByText('1 disciplinas ainda sem assuntos cadastrados recebem carga provisória por disciplina.',{exact:false}).waitFor();await section.getByText('Plano A · 300 min no período',{exact:true}).waitFor();
 await section.getByRole('button',{name:'C · Emergencial',exact:true}).click();await section.getByText('Plano C · 125 min no período',{exact:true}).waitFor();
 await section.locator('summary').filter({hasText:'Simular disponibilidade e dias perdidos'}).click();await section.getByLabel('Dias iniciais sem estudo',{exact:true}).fill('7');await section.getByLabel('Sáb · min simulados',{exact:true}).fill('240');
 await section.getByRole('button',{name:'Simular sem alterar agenda',exact:true}).evaluate(b=>{b.click();b.click();});await section.getByRole('button',{name:'Simular sem alterar agenda',exact:true}).waitFor();assert.equal(simulations,1);assert.equal(planWrites,0);
 await section.getByRole('button',{name:'A · Ideal',exact:true}).click();await section.getByText('Plano A · 180 min no período',{exact:true}).waitFor();
 await section.locator('summary').filter({hasText:'Como foi calculado'}).first().click();await section.getByText('Evidências: e1',{exact:true}).waitFor();
 fs.mkdirSync('test-results',{recursive:true});await section.getByRole('heading',{name:'Estratégia adaptativa',exact:true}).scrollIntoViewIfNeeded();await page.screenshot({path:`test-results/adaptive-strategy-top-${width}.png`});
 const agenda=page.locator('section').filter({has:page.getByRole('heading',{name:'Agenda com datas',exact:true})}).last();
 await agenda.getByRole('checkbox').filter({hasText:''}).first().check();await agenda.getByLabel(/Recuperar atrasos:/).check();
 const generate=agenda.getByRole('button',{name:'Gerar / reorganizar pendências',exact:true});await generate.evaluate(b=>{b.click();b.click();});await page.getByText('Synthetic delivery uncertainty',{exact:true}).waitFor();await generate.click();await agenda.getByText('Portuguese · Crase',{exact:true}).waitFor();assert.equal(planWrites,2);assert.ok(keys[0]);assert.equal(keys[0],keys[1]);
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);fs.mkdirSync('test-results',{recursive:true});await page.screenshot({path:`test-results/adaptive-strategy-${width}.png`});
 await section.getByRole('button',{name:'Estudar prioridade',exact:true}).first().click();await page.waitForURL(/view=estudar/);assert.ok(page.url().includes('topic=0'));assert.deepEqual(errors,[]);console.log(JSON.stringify({width,simulations,planWrites,overflow:false}));await context.close();
}
}finally{await browser.close();server.close();}})().catch(e=>{console.error(e);process.exitCode=1;server.close();});
