const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const root=path.join(process.cwd(),'build');
const server=http.createServer((req,res)=>{let file=path.join(root,new URL(req.url,'http://localhost').pathname);if(!file.startsWith(root+path.sep)){res.writeHead(403);return res.end();}if(!fs.existsSync(file)||fs.statSync(file).isDirectory())file=path.join(root,'index.html');res.setHeader('Content-Type',({'.js':'application/javascript','.css':'text/css','.html':'text/html'})[path.extname(file)]||'application/octet-stream');fs.createReadStream(file).pipe(res);});
const wait=async fn=>{for(let i=0;i<100;i++){if(fn())return;await new Promise(r=>setTimeout(r,50));}throw Error('Expected request missing');};
(async()=>{await new Promise(r=>server.listen(4176,'127.0.0.1',r));const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});try{
for(const width of [1440,1024,768,390,320])for(const mode of ['direct','background','fallback','other503']){
 const context=await browser.newContext({viewport:{width,height:844},serviceWorkers:'block'});await context.addInitScript(()=>localStorage.setItem('sirius_onboarding_complete','true'));
 let jobs=[],jobGets=0,directPosts=0,jobPosts=0,analysisGets=0,created=null,pendingDirect=null,failDirect=true;
 const filename='edital-'+('nome-longo-sem-espaco'.repeat(10))+'.pdf';
 const subject={nome:'Mathematics',topicos:['Algebra'],conteudo_programatico:[{assunto:'Algebra'}]};
 const analysis={analysis_id:'a1',pdf_filename:filename,cached:true,concurso:{nome:'Contest',banca:'Board'},cargos:[{nome:'Analyst '+('long role '.repeat(12)),disciplinas:[subject],disciplinas_status:'completo'},{nome:'Incomplete',disciplinas:[subject],conferencia:{missing:[{name:'History',page:1}]}},{nome:'Technician',disciplinas:[subject],disciplinas_status:'completo'}]};
 const respond=(r,b,status=200)=>r.fulfill({status,contentType:'application/json',body:JSON.stringify(b)});
 await context.route('**/*',async r=>{const url=new URL(r.request().url()),p=url.pathname,m=r.request().method();if(!p.startsWith('/api/'))return url.hostname==='127.0.0.1'?r.continue():r.abort();
  if(p==='/api/auth/me')return respond(r,{user_id:'fixture',name:'User',rank:'Recruta'});
  if(p==='/api/study/areas')return respond(r,[{area_id:'area1',name:'Concursos'}]);
  if(p==='/api/study/edital-jobs'&&m==='GET'){jobGets++;return respond(r,{jobs,upload_available:mode!=='direct'});}
  if(p==='/api/study/edital-jobs'&&m==='POST'){jobPosts++;if(mode==='fallback')return respond(r,{detail:{code:'durable_storage_unavailable',message:'Unavailable'}},503);if(mode==='other503')return respond(r,{detail:{code:'database_unavailable',message:'Database unavailable'}},503);jobs=[{job_id:'j1',filename,status:'queued'}];return respond(r,{job_id:'j1',status:'queued'},202);}
  if(p==='/api/study/programs/analyze-edital'){directPosts++;if(failDirect){failDirect=false;return r.abort('failed');}pendingDirect=r;return;}
  if(p==='/api/study/programs/editais/a1'){analysisGets++;return respond(r,analysis);}
  if(p==='/api/study/programs/import-edital-with-cargo'){created=r.request().postDataJSON();return respond(r,{success:true,program:{program_id:'p1',name:'Created program'},disciplinas:[],concurso:analysis.concurso,message:'Created'});}
  if(p==='/api/study/programs/editais')return respond(r,{editais:[]});
  if(p==='/api/study/v2/today')return respond(r,{});
  if(p.includes('stats')||p.includes('streak'))return respond(r,{});
  return respond(r,[]);
 });
 const page=await context.newPage(),errors=[];await page.clock.install();page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:4176/studies');
 await page.getByRole('button',{name:'Prepara\u00e7\u00f5es',exact:true}).click();await page.getByRole('button',{name:'Editais analisados',exact:true}).click();await page.getByRole('button',{name:'Analisar novo edital',exact:true}).click();
 const modal=page.getByRole('dialog');await modal.getByLabel('PDF do Edital',{exact:true}).setInputFiles({name:filename,mimeType:'application/pdf',buffer:Buffer.from('%PDF-synthetic')});
 await modal.getByRole('button',{name:'Remover PDF selecionado',exact:true}).click();assert.equal(await modal.getByLabel('PDF do Edital',{exact:true}).evaluate(e=>e.files.length),0);await modal.getByLabel('PDF do Edital',{exact:true}).setInputFiles({name:filename,mimeType:'application/pdf',buffer:Buffer.from('%PDF-synthetic')});
 if(width===1440&&mode==='direct')for(const invalid of [{name:'bad.txt',mimeType:'text/plain',buffer:Buffer.from('bad')},{name:'large.pdf',mimeType:'application/pdf',buffer:Buffer.alloc(20*1024*1024+1)}]){await modal.getByLabel('PDF do Edital',{exact:true}).setInputFiles(invalid);await modal.getByRole('alert').waitFor();assert.equal(await modal.getByLabel('PDF do Edital',{exact:true}).evaluate(e=>e.files.length),0);assert.equal(await page.getByTestId('analyze-edital-btn').isDisabled(),true);assert.equal(directPosts,0);await modal.getByLabel('PDF do Edital',{exact:true}).setInputFiles({name:filename,mimeType:'application/pdf',buffer:Buffer.from('%PDF-synthetic')});}
 assert.equal(await modal.getByText('Horas por dia',{exact:true}).count(),0);const bounds=await modal.boundingBox();assert.ok(bounds.height<=824);await page.keyboard.press('Tab');assert.equal(await page.evaluate(()=>!!document.activeElement.closest('[role=dialog]')),true);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);fs.mkdirSync('test-results',{recursive:true});await page.screenshot({path:`test-results/edital-dialog-${mode}-${width}.png`});await page.getByTestId('analyze-edital-btn').waitFor();
 await page.getByTestId('analyze-edital-btn').click();
 if(mode==='other503'){await modal.getByRole('alert').filter({hasText:'Database unavailable'}).waitFor();assert.equal(directPosts,0);assert.equal(jobPosts,1);await context.close();continue;}
 if(mode==='background'){await modal.waitFor({state:'hidden'});await wait(()=>jobs.length&&jobGets>=2);assert.equal(directPosts,0);await page.getByText('Na fila',{exact:true}).waitFor();let activeGets=jobGets;await page.clock.fastForward(5500);await wait(()=>jobGets>activeGets);jobs=[{job_id:'j1',filename,status:'completed',analysis_id:'a1'}];await page.getByRole('button',{name:'Atualizar an\u00e1lises',exact:true}).click();await page.getByRole('button',{name:'Conferir an\u00e1lise',exact:true}).waitFor();const terminalGets=jobGets;await page.clock.fastForward(30000);await page.waitForTimeout(100);assert.equal(jobGets,terminalGets);await page.getByRole('button',{name:'Conferir an\u00e1lise',exact:true}).click();}
 else{
  await modal.getByRole('alert').waitFor();assert.equal(await modal.getByLabel('PDF do Edital',{exact:true}).evaluate(e=>e.files.length),1);
  const before=directPosts;await page.getByTestId('analyze-edital-btn').click();await wait(()=>pendingDirect);await page.getByTestId('analyze-edital-btn').evaluate(b=>{b.form.requestSubmit();b.form.requestSubmit();});assert.equal(directPosts,before+1);
  assert.equal(await modal.getByRole('button',{name:'Interromper espera',exact:true}).count(),1);
  page.once('dialog',d=>d.dismiss());await page.keyboard.press('Escape');assert.equal(await modal.isVisible(),true);
  await respond(pendingDirect,analysis);pendingDirect=null;
 }
 await page.getByLabel('Cargo / especialidade',{exact:true}).waitFor();await page.getByLabel('Cargo / especialidade',{exact:true}).selectOption('1');const create=page.getByRole('button',{name:'Gerar programa para este cargo',exact:true});assert.equal(await create.isDisabled(),true);
 await page.getByLabel('Cargo / especialidade',{exact:true}).selectOption('2');await page.getByRole('combobox',{name:/\u00c1rea de estudos/}).selectOption('area1');await page.getByLabel('Data da prova / meta',{exact:true}).fill('2026-12-01');await page.getByRole('combobox',{name:/Horas por dia/}).selectOption('2');await page.getByRole('combobox',{name:/Dias por semana/}).selectOption('4');
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);fs.mkdirSync('test-results',{recursive:true});await page.screenshot({path:`test-results/edital-${mode}-${width}.png`,fullPage:true});
 await create.click();await page.getByRole('heading',{name:'Programa Criado com Sucesso!',exact:true}).waitFor();assert.equal(created.cargo_index,2);assert.equal(created.hours_per_day,2);assert.equal(created.days_per_week,4);assert.equal(created.target_date,'2026-12-01');assert.equal(created.area_id,'area1');
 if(mode==='direct'){assert.equal(jobPosts,0);assert.equal(analysisGets,0);}if(mode==='fallback')assert.equal(jobPosts,1);
 assert.deepEqual(errors,[]);console.log(JSON.stringify({width,mode,jobGets,directPosts,jobPosts,analysisGets,selectedCargo:created.cargo_index,overflow:false}));await context.close();
}
}finally{await browser.close();server.close();}})().catch(e=>{console.error(e);process.exitCode=1;server.close();});
