const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const root=path.join(process.cwd(),'build');
const server=http.createServer((req,res)=>{let file=path.join(root,new URL(req.url,'http://localhost').pathname);if(!file.startsWith(root+path.sep)){res.writeHead(403);return res.end();}if(!fs.existsSync(file)||fs.statSync(file).isDirectory())file=path.join(root,'index.html');res.setHeader('Content-Type',({'.js':'application/javascript','.css':'text/css','.html':'text/html'})[path.extname(file)]||'application/octet-stream');fs.createReadStream(file).pipe(res);});
(async()=>{await new Promise(r=>server.listen(4182,'127.0.0.1',r));const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});try{
for(const width of [1440,1024,768,390,320]){
 const context=await browser.newContext({viewport:{width,height:900},serviceWorkers:'block'});await context.addInitScript(()=>localStorage.setItem('sirius_onboarding_complete','true'));
 const errors=[],keys=[],cardKeys=[],reviewKeys=[];let provider=0,fail=true,cards=0,linked=false,reviews=0;
 const history=new Map(),receipts=new Map();
 const program={program_id:'demo',area_id:'area1',name:'Preparation',source_type:'manual'};
 const book={notebook_id:'nb0',area_id:'area1',program_id:'demo',name:'Portuguese',nome:'Portuguese',conteudo_programatico:[{assunto:'Interpretation',subtopicos:[]}],topicos:[]};
 const respond=(r,b,status=200)=>r.fulfill({status,contentType:'application/json',body:JSON.stringify(b)});
 await context.route('**/*',async r=>{const u=new URL(r.request().url()),p=u.pathname,m=r.request().method();if(!p.startsWith('/api/'))return u.hostname==='127.0.0.1'?r.continue():r.abort();
  if(p==='/api/auth/me')return respond(r,{user_id:'fixture',name:'User',rank:'Recruta'});
  if(p.endsWith('/tutor/history'))return respond(r,{messages:history.get(u.searchParams.get('conversation_id'))||[]});
  if(p.endsWith('/tutor/turn')){
   const b=r.request().postDataJSON();assert.equal(b.preparation_id,'demo');assert.equal(b.notebook_id,'nb0');assert.equal(b.topic_key,'0');keys.push(b.request_id);
   if(receipts.has(b.request_id))return respond(r,receipts.get(b.request_id));provider++;
   const um={message_id:'u'+provider,role:'user',content:b.message},am={message_id:'a'+provider,role:'assistant',content:'Uma pergunta curta: explique sua resposta.',tutor:{estimated:true,knowledge_basis:'provided_sources_and_sirius_facts'},citations:[{id:'S1',title:'Material',category:'user_material',page:2,text:'Um trecho para recordar.',source_id:'file1'}]};
   const result={user_message:um,ai_message:am};history.set(b.conversation_id,[...(history.get(b.conversation_id)||[]),um,am]);receipts.set(b.request_id,result);
   if(fail){fail=false;return respond(r,{detail:'Synthetic tutor response loss'},504);}return respond(r,result);
  }
  if(p.endsWith('/tutor/materials'))return respond(r,{materials:linked?[{attachment_id:'file1',filename:'material.pdf'}]:[],related_errors:[],notice:'Texto extraído, original não retido.'});
  if(p.endsWith('/ai/attachments'))return respond(r,{attachment_id:'file1',filename:'material.pdf'});
  if(p.endsWith('/materials/file1/link')){assert.equal(r.request().postDataJSON().topic_key,'0');assert.ok(r.request().headers()['idempotency-key']);linked=true;return respond(r,{});}
  if(p.endsWith('/tutor/review')){const k=r.request().headers()['idempotency-key'];reviewKeys.push(k);if(!receipts.has(k)){reviews++;receipts.set(k,{review_id:'r1'});return respond(r,{detail:'Synthetic review response loss'},504);}return respond(r,receipts.get(k));}
  if(p.endsWith('/tutor/copilot'))return respond(r,{recorded_minutes:25,answered:4,accuracy:75,reviewed_topics:reviews,recommendation:'Revise os erros registrados.',notice:'Fatos registrados, sem XP adicional.'});
  if(p==='/api/study/flashcards'&&m==='POST'){const k=r.request().headers()['idempotency-key'];cardKeys.push(k);if(!receipts.has(k)){cards++;receipts.set(k,{flashcard_id:'c1'});return respond(r,{detail:'Synthetic card response loss'},504);}return respond(r,receipts.get(k));}
  if(p.endsWith('/cronograma'))return respond(r,{program,notebooks:[book],cronograma:[]});
  if(p.endsWith('/edital-verticalizado'))return respond(r,{disciplinas:[book]});
  if(p==='/api/study/programs')return respond(r,[program]);if(p==='/api/study/notebooks')return respond(r,[book]);if(p==='/api/study/areas')return respond(r,[{area_id:'area1',name:'Area'}]);
  if(p.endsWith('/draft'))return respond(r,{text:'',revision:0});if(p.endsWith('/overview')||p.includes('stats')||p.includes('streak'))return respond(r,{});return respond(r,[]);
 });
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
 const url='http://127.0.0.1:4182/studies?program=demo&view=estudar&notebook=nb0&topic=0';await page.goto(url);
 const tutor=page.getByRole('region',{name:'Sirius Tutor',exact:true});await tutor.waitFor();await tutor.getByLabel('Modo do tutor').selectOption('socratic');
 await tutor.getByLabel('Mensagem para o tutor').fill('Me faça uma pergunta');await tutor.getByRole('button',{name:'Enviar ao tutor',exact:true}).click();await tutor.getByText('Synthetic tutor response loss',{exact:true}).waitFor();await tutor.getByRole('button',{name:'Enviar ao tutor',exact:true}).click();await tutor.locator('article').filter({hasText:'Uma pergunta curta: explique sua resposta.'}).waitFor().catch(async e=>{console.error(JSON.stringify({keys,provider,text:await tutor.innerText()}));throw e;});assert.equal(provider,1);assert.equal(keys[0],keys[1]);
 await page.reload();await tutor.getByLabel('Modo do tutor').selectOption('socratic');await tutor.locator('article').filter({hasText:'Uma pergunta curta: explique sua resposta.'}).waitFor().catch(async e=>{console.error(JSON.stringify({keys,provider,text:await tutor.innerText()}));throw e;});
 await tutor.locator('summary').filter({hasText:'Fontes e materiais de estudo'}).click();await tutor.getByLabel('Vincular material PDF').setInputFiles({name:'material.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF- synthetic test only')});await tutor.getByText('material.pdf · texto extraído',{exact:true}).waitFor();
 await tutor.getByRole('button',{name:'Usar trecho como proposta',exact:true}).click();await tutor.locator('summary').filter({hasText:'Trechos e propostas'}).click();await tutor.getByRole('button',{name:'Propor flashcard',exact:true}).click();assert.equal(cards,0);await tutor.getByRole('button',{name:'Confirmar e salvar proposta',exact:true}).click();await tutor.getByText('Synthetic card response loss',{exact:true}).waitFor();await tutor.getByRole('button',{name:'Confirmar e salvar proposta',exact:true}).click();await tutor.getByText('Proposta salva na biblioteca.',{exact:true}).waitFor();assert.equal(cards,1);assert.equal(cardKeys[0],cardKeys[1]);
 await tutor.getByRole('button',{name:'Confirmar revisão deste assunto',exact:true}).click();await tutor.getByText('Synthetic review response loss',{exact:true}).waitFor();await tutor.getByRole('button',{name:'Confirmar revisão deste assunto',exact:true}).click();await tutor.getByText('Revisão registrada na sessão.',{exact:true}).waitFor();assert.equal(reviews,1);assert.equal(reviewKeys[0],reviewKeys[1]);await tutor.getByRole('button',{name:'Conferir sessão até agora',exact:true}).click();await tutor.getByRole('region',{name:'Resumo factual da sessão'}).waitFor();assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
 fs.mkdirSync('test-results',{recursive:true});await tutor.scrollIntoViewIfNeeded();await page.screenshot({path:`test-results/tutor-${width}.png`});assert.deepEqual(errors,[]);console.log(JSON.stringify({width,provider,cards,linked,overflow:false}));await context.close();
}
}finally{await browser.close();server.close();}})().catch(e=>{console.error(e);process.exitCode=1;server.close();});
