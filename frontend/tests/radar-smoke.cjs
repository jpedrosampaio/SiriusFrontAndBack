const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require('playwright'),state=require('./preparation-fixture.cjs');
const root=path.join(process.cwd(),'build');
const server=http.createServer((req,res)=>{let file=path.join(root,new URL(req.url,'http://localhost').pathname);if(!file.startsWith(root+path.sep)){res.writeHead(403);return res.end();}if(!fs.existsSync(file)||fs.statSync(file).isDirectory())file=path.join(root,'index.html');res.setHeader('Content-Type',({'.js':'application/javascript','.css':'text/css','.html':'text/html'})[path.extname(file)]||'application/octet-stream');fs.createReadStream(file).pipe(res);});
(async()=>{await new Promise(r=>server.listen(4178,'127.0.0.1',r));const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});try{
for(const width of [1440,1024,768,390,320]){
 const context=await browser.newContext({viewport:{width,height:844},serviceWorkers:'block'});await context.addInitScript(()=>localStorage.setItem('sirius_onboarding_complete','true'));
 const errors=[];let radarReads=0;
 const respond=(r,b,status=200)=>r.fulfill({status,contentType:'application/json',body:JSON.stringify(b)});
 const program={program_id:'demo',area_id:'area1',name:'Preparation',source_type:'manual'};
 const discipline={notebook_id:'nb0',area_id:'area1',program_id:'demo',name:'Portuguese',nome:'Portuguese',conteudo_programatico:[{assunto:'Interpretation',subtopicos:[]}],topicos:[]};
 await context.route('**/*',async r=>{const url=new URL(r.request().url()),p=url.pathname;if(!p.startsWith('/api/'))return url.hostname==='127.0.0.1'?r.continue():r.abort();
  if(p==='/api/auth/me')return respond(r,{user_id:'fixture',name:'User',rank:'Recruta'});
  if(p==='/api/study/v2/targets')return respond(r,[{target_id:'t1',program_id:'demo',name:'Preparation',kind:'custom',is_primary:false}]);
  if(p.endsWith('/state'))return respond(r,state);
  if(p.endsWith('/radar')){radarReads++;return respond(r,{sources:[{source_id:'s1',title:'Official source'}],latest_versions:[{version_id:'v1',source_id:'s1',hash_basis:'page_text',detected_at:'2026-10-07T12:00:00Z',details:{title:'Official source'},impact:{categories:['syllabus'],baseline:false},partial:false}],dates:[{version_id:'v1',event:'exam',date:'2027-02-01',quote:'Prova objetiva: 01/02/2027',url:'https://orgao.gov.br',conflicting_candidates:true}],date_notice:'Confirm extracted dates'});}
  if(p.endsWith('/versions'))return respond(r,{items:[{version_id:'v1',detected_at:'2026-10-07T12:00:00Z',hash_basis:'page_text',impact:{added:['Disciplina nova'],removed:['Peso anterior'],partial:true}}],next_offset:null});
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
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:4178/studies');
 await page.goto('http://127.0.0.1:4178/studies?program=demo&view=atualizacoes');
 const radar=page.getByRole('region',{name:'Radar de editais',exact:true});await radar.waitFor();
 await radar.getByRole('button',{name:'Ver hist\u00f3rico',exact:true}).click();
 await radar.locator('summary').filter({hasText:'Mudan\u00e7as textuais'}).click();
 await radar.getByText('+ Disciplina nova',{exact:true}).waitFor();
 await radar.getByText('\u2212 Peso anterior',{exact:true}).waitFor();
 await radar.getByText(/mais de uma data candidata/).waitFor();
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
 await radar.getByRole('button',{name:'Fechar hist\u00f3rico',exact:true}).click();
 fs.mkdirSync('test-results',{recursive:true});await page.screenshot({path:`test-results/radar-${width}.png`});
 assert.deepEqual(errors,[]);console.log(JSON.stringify({width,radarReads,overflow:false}));await context.close();
}
}finally{await browser.close();server.close();}})().catch(e=>{console.error(e);process.exitCode=1;server.close();});