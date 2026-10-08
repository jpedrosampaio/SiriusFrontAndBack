const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const root=path.join(process.cwd(),'build');
const server=http.createServer((req,res)=>{let file=path.join(root,new URL(req.url,'http://localhost').pathname);if(!file.startsWith(root+path.sep)){res.writeHead(403);return res.end();}if(!fs.existsSync(file)||fs.statSync(file).isDirectory())file=path.join(root,'index.html');res.setHeader('Content-Type',({'.js':'application/javascript','.css':'text/css','.html':'text/html'})[path.extname(file)]||'application/octet-stream');fs.createReadStream(file).pipe(res);});
(async()=>{await new Promise(r=>server.listen(4179,'127.0.0.1',r));const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});try{
for(const width of [1440,1024,768,390,320]){
 const context=await browser.newContext({viewport:{width,height:844},serviceWorkers:'block'});await context.addInitScript(()=>localStorage.setItem('sirius_onboarding_complete','true'));
 const keys=[],labKeys=[],errors=[];let fail=true,labFail=true,suggestions=[];
 const program={program_id:'demo',area_id:'area1',name:'Preparation',source_type:'manual'};
 const discipline={notebook_id:'nb0',area_id:'area1',program_id:'demo',name:'Portuguese',conteudo_programatico:[{assunto:'Crase',subtopicos:[]}],topicos:[]};
 const respond=(r,b,status=200)=>r.fulfill({status,contentType:'application/json',body:JSON.stringify(b)});
 await context.route('**/*',async r=>{const url=new URL(r.request().url()),p=url.pathname,m=r.request().method();if(!p.startsWith('/api/'))return url.hostname==='127.0.0.1'?r.continue():r.abort();
  if(p==='/api/auth/me')return respond(r,{user_id:'fixture',name:'User',rank:'Recruta'});
  if(p==='/api/study/v2/performance')return respond(r,{summary:{score:50,samples:4},topics:[],errors:[],trend:[],error_causes:{}});
  if(p==='/api/study/simulados/generate'){const body=r.request().postDataJSON();assert.equal(body.laboratory,true);assert.equal(body.context_source,'syllabus');assert.equal(body.difficulty,'dificil');assert.equal(body.topic_key,'0');labKeys.push(r.request().headers()['idempotency-key']);if(labFail){labFail=false;return respond(r,{detail:'Synthetic lab response loss'},504);}return respond(r,{simulado:{simulado_id:'generated'}});}
  if(p==='/api/study/simulados/generated/session')return respond(r,{session_id:'fixture-session',revision:0,status:'active',answers:[],current_question:0,marked:[],elapsed_seconds:0});
  if(p==='/api/study/simulados/generated')return respond(r,{simulado_id:'generated',title:'Generated practice',questions:[{question_text:'Crase practice question',origin:'ai_generated',options:['A) First','B) Second'],type:'multipla_escolha'}]});
  if(p.endsWith('/question-intelligence/analyze')){keys.push(r.request().headers()['idempotency-key']);suggestions=[{insight_id:'s1',question_count:3,reason:'memory',terms:['crase'],attempt_ids:['a1','a2','a3'],computed_at:'2026-10-08T10:00:00Z',notice:'Suggestion: confirm the shared concept.'}];if(fail){fail=false;return respond(r,{detail:'Synthetic response loss'},504);}return respond(r,{suggestions,facts_changed:false});}
  if(p.endsWith('/question-intelligence/s1')&&m==='PATCH'){assert.equal(r.request().postDataJSON().status,'dismissed');assert.ok(r.request().headers()['idempotency-key']);suggestions=[];return respond(r,{facts_changed:false});}
  if(p.endsWith('/question-intelligence'))return respond(r,{error_bank:{question_count:1,recovered_questions:1,recovery_rate:100,items:[{question_id:'q1',notebook_id:'nb0',topic_key:'0',title:'Crase',errors:3,last_error_at:'2026-10-08T10:00:00Z',error_cause:'memory',recovered:true,error_evidence_ids:['a1','a2','a3'],later_evidence_ids:['a4']}]},suggestions,related_reviews:[{review_id:'r1',notebook_id:'nb0',topic_key:'0',title:'Crase',due_date:'2026-10-09'}]});
  if(p.endsWith('/cronograma'))return respond(r,{program,notebooks:[discipline],cronograma:[]});
  if(p.endsWith('/edital-verticalizado'))return respond(r,{disciplinas:[discipline]});
  if(p==='/api/study/programs')return respond(r,[program]);
  if(p==='/api/study/notebooks')return respond(r,[discipline]);
  if(p==='/api/study/areas')return respond(r,[{area_id:'area1',name:'Area'}]);
  if(p.includes('stats')||p.includes('streak')||p.endsWith('/overview'))return respond(r,{});
  return respond(r,[]);
 });
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:4179/studies?program=demo&view=desempenho');
 const section=page.getByRole('region',{name:'Inteligência de questões'});await section.getByText('Taxa de recuperação: 100%',{exact:true}).waitFor();
 await section.getByRole('button',{name:'Analisar recorrência dos erros'}).evaluate(b=>{b.click();b.click();});await section.getByRole('alert').filter({hasText:'Synthetic response loss'}).waitFor();
 await section.getByRole('button',{name:'Analisar recorrência dos erros'}).click();await section.getByText('Sugestão · 3 questões diferentes',{exact:true}).waitFor();assert.equal(keys.length,2);assert.ok(keys[0]);assert.equal(keys[0],keys[1]);
 await section.locator('summary').filter({hasText:'Ver evidências da sugestão'}).click();await section.getByText('a1, a2, a3',{exact:true}).last().waitFor();
 await section.locator('summary').filter({hasText:'Revisões relacionadas'}).click();await section.getByRole('button',{name:'Estudar revisão'}).waitFor();
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);fs.mkdirSync('test-results',{recursive:true});await page.screenshot({path:`test-results/questions-intelligence-${width}.png`});
 await section.getByRole('button',{name:'Descartar sugestão'}).click();await section.getByText(/Nenhum agrupamento salvo/).waitFor();
 await page.goto('http://127.0.0.1:4179/studies?program=demo&view=estudar&notebook=nb0&topic=0');
 await page.getByLabel('Dificuldade das questões',{exact:true}).selectOption('dificil');const generate=page.getByRole('button',{name:'Gerar e resolver questões',exact:true});await generate.evaluate(b=>{b.click();b.click();});
 await page.getByRole('alert').filter({hasText:'Synthetic lab response loss'}).waitFor();await generate.click();await page.getByText('Gerada pelo Sirius · IA',{exact:true}).waitFor();assert.equal(labKeys.length,2);assert.ok(labKeys[0]);assert.equal(labKeys[0],labKeys[1]);
 assert.deepEqual(errors,[]);console.log(JSON.stringify({width,analysisRequests:keys.length,labRequests:labKeys.length,overflow:false}));await context.close();
}
}finally{await browser.close();server.close();}})().catch(e=>{console.error(e);process.exitCode=1;server.close();});
