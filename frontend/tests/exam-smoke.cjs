const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const root=path.join(process.cwd(),'build');
const server=http.createServer((req,res)=>{let file=path.join(root,new URL(req.url,'http://localhost').pathname);if(!file.startsWith(root+path.sep)){res.writeHead(403);return res.end();}if(!fs.existsSync(file)||fs.statSync(file).isDirectory())file=path.join(root,'index.html');res.setHeader('Content-Type',({'.js':'application/javascript','.css':'text/css','.html':'text/html'})[path.extname(file)]||'application/octet-stream');fs.createReadStream(file).pipe(res);});
(async()=>{await new Promise(r=>server.listen(4181,'127.0.0.1',r));const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});try{
for(const width of [1440,1024,768,390,320]){
 const context=await browser.newContext({viewport:{width,height:900},serviceWorkers:'block'});await context.addInitScript(()=>localStorage.setItem('sirius_onboarding_complete','true'));
 const errors=[],saveKeys=[],finishKeys=[];let assembly=0,completed=0,saveFailure=true,finishFailure=true;
 const program={program_id:'demo',area_id:'area1',name:'Preparation'},book={notebook_id:'nb0',area_id:'area1',program_id:'demo',name:'Portuguese',conteudo_programatico:[{assunto:'Crase'}],topicos:[]};
 const exam={simulado_id:'exam',program_id:'demo',title:'Practice exam',questions_count:2,duration_minutes:30,questions:[0,1].map(i=>({question_id:'q'+i,question_number:i+1,question_text:'Question '+(i+1),disciplina:'Portuguese',origin:'ai_generated',correct_answer:'A',options:['A) First','B) Second'],type:'multipla_escolha'})),attempts:[]};
 let execution={session_id:'execution',revision:0,status:'active',answers:[],current_question:0,marked:[],elapsed_seconds:0};const receipts=new Map();let result;
 const respond=(r,b,status=200)=>r.fulfill({status,contentType:'application/json',body:JSON.stringify(b)});
 await context.route('**/*',async r=>{const u=new URL(r.request().url()),p=u.pathname,m=r.request().method();if(!p.startsWith('/api/'))return u.hostname==='127.0.0.1'?r.continue():r.abort();
  if(p==='/api/auth/me')return respond(r,{user_id:'fixture',name:'User',rank:'Recruta'});
  if(p.endsWith('/blueprint/simulado')){assembly++;const b=r.request().postDataJSON();assert.equal(b.mode,'discipline');assert.deepEqual(b.notebook_ids,['nb0']);assert.equal(b.num_questions,2);assert.ok(r.request().headers()['idempotency-key']);return respond(r,exam);}
  if(p.endsWith('/blueprint'))return respond(r,{distribution:[],complete:false,disciplines:[{id:'nb0',name:'Portuguese'}],topics:[{id:'t1',name:'Crase'}]});
  if(p.endsWith('/exam/session')){
   if(m==='POST') { assert.notEqual(execution.status,'completed','Must not replace a completed session without explicit retake'); }
   if(m!=='PUT')return respond(r,execution);
   const b=r.request().postDataJSON(),key=r.request().headers()['idempotency-key'];saveKeys.push(key);
   if(receipts.has(key))return respond(r,receipts.get(key));assert.equal(b.revision,execution.revision);
   execution={...execution,...b,revision:b.revision+1};receipts.set(key,execution);
   if(saveFailure){saveFailure=false;return respond(r,{detail:'Synthetic save uncertainty'},504);}return respond(r,execution);
  }
  if(p.endsWith('/exam/submit')){
   const b=r.request().postDataJSON(),key=r.request().headers()['idempotency-key'];finishKeys.push(key);
   if(receipts.has(key))return respond(r,receipts.get(key));assert.equal(b.revision,execution.revision);completed++;
   assert.equal(execution.answers.find(a=>a.question_idx===0).changed_answer,true);
   result={attempt_id:'attempt',simulado_id:'exam',completed_at:'2026-10-08T18:00:00Z',score:0,score_basis:'all_questions_weighted',accuracy:0,total_answered:1,unanswered:1,correct_count:0,total_questions:2,time_spent_seconds:execution.elapsed_seconds,xp_earned:0,answers:[],post_mortem:{by_discipline:{Portuguese:{wrong:1,blank:1,points_lost:3,mean_seconds:2,timed_questions:2}},confidence:{guess:{correct:0,answered:1,accuracy:0}},slow_question_indexes:[],changed_answers:1,repeated_wrong_question_ids:[],notice:'Declared timing, no diagnosis.'}};
   execution={...execution,status:'completed',attempt_id:'attempt'};receipts.set(key,result);
   if(finishFailure){finishFailure=false;return respond(r,{detail:'Synthetic finish uncertainty'},504);}return respond(r,result);
  }
  if(p.endsWith('/exam/results'))return respond(r,result?[result]:[]);
  if(p.endsWith('/simulados/exam'))return respond(r,exam);
  if(p==='/api/study/simulados')return respond(r,[exam]);
  if(p.endsWith('/cronograma'))return respond(r,{program,notebooks:[book],cronograma:[]});
  if(p.endsWith('/edital-verticalizado'))return respond(r,{disciplinas:[book]});
  if(p==='/api/study/programs')return respond(r,[program]);if(p==='/api/study/notebooks')return respond(r,[book]);if(p==='/api/study/areas')return respond(r,[{area_id:'area1',name:'Area'}]);
  if(p.includes('stats')||p.includes('streak')||p.endsWith('/overview'))return respond(r,{});return respond(r,[]);
 });
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());await page.goto('http://127.0.0.1:4181/studies?program=demo&view=questoes');
 const blueprint=page.getByRole('region',{name:'Exam Blueprint'});await blueprint.getByLabel('Modo do simulado').selectOption('discipline');await blueprint.getByLabel('Portuguese',{exact:true}).check();await blueprint.getByLabel('Quantidade de quest\u00f5es').fill('2');
 await blueprint.getByRole('button',{name:'Montar simulado',exact:true}).evaluate(b=>{b.click();b.click();});
 const runner=page.getByRole('region',{name:'Execu\u00e7\u00e3o da prova'});await runner.getByText('Progresso salvo',{exact:true}).waitFor();assert.equal(assembly,1);
 await runner.getByRole('button',{name:'A) First',exact:true}).click();await runner.getByRole('button',{name:'B) Second',exact:true}).click();await runner.getByLabel('Confian\u00e7a na quest\u00e3o').selectOption('guess');
 await runner.getByRole('button',{name:'Quest\u00e3o 2',exact:true}).click();await runner.getByRole('button',{name:'Deixar em branco',exact:true}).click();await runner.getByRole('button',{name:'Quest\u00e3o 1',exact:true}).click();await runner.getByRole('button',{name:'Pausar',exact:true}).click();
 await runner.getByRole('button',{name:'Salvar e sair',exact:true}).click();await runner.getByText('Synthetic save uncertainty',{exact:true}).waitFor();await runner.getByRole('button',{name:'Salvar e sair',exact:true}).click();await page.getByRole('button',{name:'Iniciar',exact:true}).first().click();
 await runner.getByRole('button',{name:'B) Second',exact:true}).waitFor();assert.equal(await runner.getByRole('button',{name:'B) Second',exact:true}).getAttribute('aria-pressed'),'true');assert.equal(saveKeys[0],saveKeys[1]);
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);fs.mkdirSync('test-results',{recursive:true});await page.screenshot({path:`test-results/exam-runner-${width}.png`});
 await runner.getByRole('button',{name:'Finalizar prova',exact:true}).click();await runner.getByText('Synthetic finish uncertainty',{exact:true}).waitFor();await runner.getByRole('button',{name:'Confirmar conclus\u00e3o',exact:true}).click();
 const diagnostics=page.getByRole('region',{name:'Diagn\u00f3stico do simulado'});await diagnostics.getByText('Depois da prova',{exact:true}).waitFor();await diagnostics.getByRole('button',{name:'Ver evolu\u00e7\u00e3o entre tentativas',exact:true}).click();assert.equal(completed,1);assert.equal(finishKeys[0],finishKeys[1]);await page.getByRole('button',{name:'Voltar',exact:true}).click();await page.getByRole('button',{name:/^(Iniciar|Refazer)$/}).first().click();await runner.getByRole('button',{name:'Ver resultado',exact:true}).waitFor();assert.equal(execution.status,'completed');await runner.getByRole('button',{name:'Ver resultado',exact:true}).click();await diagnostics.getByText('Depois da prova',{exact:true}).waitFor();assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);await page.screenshot({path:`test-results/exam-result-${width}.png`});assert.deepEqual(errors,[]);console.log(JSON.stringify({width,assembly,completed,saves:saveKeys.length}));await context.close();
}
}finally{await browser.close();server.close();}})().catch(e=>{console.error(e);process.exitCode=1;server.close();});
