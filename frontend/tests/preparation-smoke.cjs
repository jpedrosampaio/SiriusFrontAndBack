const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require('playwright'),state=require('./preparation-fixture.cjs');
const root=path.join(process.cwd(),'build');
const server=http.createServer((req,res)=>{let file=path.join(root,new URL(req.url,'http://localhost').pathname);if(!file.startsWith(root+path.sep)){res.writeHead(403);return res.end();}if(!fs.existsSync(file)||fs.statSync(file).isDirectory())file=path.join(root,'index.html');res.setHeader('Content-Type',({'.js':'application/javascript','.css':'text/css','.html':'text/html'})[path.extname(file)]||'application/octet-stream');fs.createReadStream(file).pipe(res);});
(async()=>{await new Promise(r=>server.listen(4177,'127.0.0.1',r));const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});try{
for(const width of [1440,1024,768,390,320]){
 const context=await browser.newContext({viewport:{width,height:844},serviceWorkers:'block'});await context.addInitScript(()=>localStorage.setItem('sirius_onboarding_complete','true'));
 let primary=false,failedPrimary=false,failedState=false,stateReads=0;const keys=[],errors=[];
 const respond=(r,b,status=200)=>r.fulfill({status,contentType:'application/json',body:JSON.stringify(b)});
 const program={program_id:'demo',area_id:'area1',name:'Preparation',source_type:'manual'};
 const discipline={notebook_id:'nb0',area_id:'area1',program_id:'demo',name:'Portuguese',nome:'Portuguese',conteudo_programatico:[{assunto:'Interpretation',subtopicos:[]}],topicos:[]};
 await context.route('**/*',async r=>{const url=new URL(r.request().url()),p=url.pathname;if(!p.startsWith('/api/'))return url.hostname==='127.0.0.1'?r.continue():r.abort();
  if(p==='/api/auth/me')return respond(r,{user_id:'fixture',name:'User',rank:'Recruta'});
  if(p==='/api/study/v2/targets')return respond(r,[{target_id:'t1',program_id:'demo',name:'Preparation',kind:'custom',is_primary:primary}]);
  if(p.endsWith('/primary')){keys.push(r.request().headers()['idempotency-key']);primary=true;if(!failedPrimary){failedPrimary=true;return respond(r,{detail:'Synthetic response loss'},504);}return respond(r,{is_primary:true});}
  if(p.endsWith('/state')){stateReads++;if(!failedState){failedState=true;return respond(r,{detail:'Synthetic read failure'},503);}return respond(r,state);}
  if(p.endsWith('/overview'))return respond(r,{});
  if(p.endsWith('/cronograma'))return respond(r,{program,notebooks:[discipline],cronograma:[]});
  if(p.endsWith('/edital-verticalizado'))return respond(r,{disciplinas:[discipline]});
  if(p==='/api/study/programs')return respond(r,[program]);
  if(p==='/api/study/notebooks')return respond(r,[discipline]);
  if(p==='/api/study/areas')return respond(r,[{area_id:'area1',name:'Area'}]);
  if(p==='/api/study/v2/today')return respond(r,{});
  if(p.includes('stats')||p.includes('streak'))return respond(r,{});
  return respond(r,[]);
 });
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:4177/studies');
 await page.getByRole('button',{name:'Preparações',exact:true}).click();
 await page.getByRole('button',{name:'Definir como principal',exact:true}).evaluate(b=>{b.click();b.click();});
 await page.getByRole('alert').filter({hasText:'Synthetic response loss'}).waitFor();
 await page.getByRole('button',{name:'Definir como principal',exact:true}).click();
 await page.getByText('Objetivo pessoal · Principal',{exact:true}).waitFor();assert.equal(keys.length,2);assert.ok(keys[0]);assert.equal(keys[0],keys[1]);
 await page.goto('http://127.0.0.1:4177/studies?program=demo&view=edital');
 await page.getByText('Não foi possível carregar o estado da preparação.',{exact:true}).waitFor();await page.getByRole('button',{name:'Tentar novamente',exact:true}).click();
 const section=page.getByRole('region',{name:'Estado da preparação',exact:true});await section.waitFor();
 await section.locator('summary').filter({hasText:'Domínio estimado'}).click();await section.getByText('Sem questões individuais respondidas; exposição não comprova domínio.',{exact:true}).waitFor();
 await section.locator('summary').filter({hasText:'Por quê?'}).click();await section.getByText(/revisão vencida · sem amostra de domínio/).waitFor();
 await section.locator('summary').filter({hasText:'Evidências dos indicadores'}).click();await section.getByText('ID: session1',{exact:true}).waitFor();
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
 assert.equal(await page.getByText('Resumo do edital',{exact:true}).count(),0);
 await page.evaluate(()=>{window.scrollTo(0,0);document.activeElement.blur();});
 fs.mkdirSync('test-results',{recursive:true});await page.screenshot({path:`test-results/preparation-state-${width}.png`});
 await section.getByRole('button',{name:'Estudar',exact:true}).click();await page.waitForURL(/view=estudar/);assert.equal(new URL(page.url()).searchParams.get('topic'),'0');assert.equal(new URL(page.url()).searchParams.get('notebook'),'nb0');
 assert.deepEqual(errors,[]);console.log(JSON.stringify({width,stateReads,primaryRequests:keys.length,overflow:false}));await context.close();
}
}finally{await browser.close();server.close();}})().catch(e=>{console.error(e);process.exitCode=1;server.close();});
