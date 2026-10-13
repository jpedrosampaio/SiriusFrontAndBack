// Synthetic browser coverage; every remote/API request is intercepted.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const root=path.join(process.cwd(),'build');
const server=http.createServer((req,res)=>{let file=path.join(root,new URL(req.url,'http://localhost').pathname);if(!file.startsWith(root+path.sep)){res.writeHead(403);return res.end();}if(!fs.existsSync(file)||fs.statSync(file).isDirectory())file=path.join(root,'index.html');res.setHeader('Content-Type',({'.js':'application/javascript','.css':'text/css','.html':'text/html'})[path.extname(file)]||'application/octet-stream');fs.createReadStream(file).pipe(res);});
const why={source:'global-planner/1',evidence:['Prazo registrado para hoje.'],constraints:['Compromisso fixo preservado.'],limitations:['Prévia não confirmada.']};
const id='11111111-1111-4111-8111-111111111111',other='22222222-2222-4222-8222-222222222222';
(async()=>{await new Promise(r=>server.listen(4190,'127.0.0.1',r));const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});let lastPage;try{
for(const width of [320,390,768,1024,1440]){
 const context=await browser.newContext({viewport:{width,height:900},serviceWorkers:'block',acceptDownloads:true});await context.addInitScript(()=>localStorage.setItem('sirius_onboarding_complete','true'));
 const page=await context.newPage(),errors=[],calls=[],keys=[];page.on('pageerror',e=>errors.push(e.message));
 lastPage=page;
 let memory=[],failed=false,undo=false,homeFailure=false,owner='Command user';
 const respond=(r,b,status=200,headers={})=>r.fulfill({status,contentType:'application/json',headers,body:JSON.stringify(b)});
 await context.route('**/*',async r=>{const u=new URL(r.request().url()),p=u.pathname,m=r.request().method();if(!p.startsWith('/api/'))return u.hostname==='127.0.0.1'?r.continue():r.abort();calls.push({p,m,body:m==='GET'?null:r.request().postDataJSON()});
  if(p==='/api/auth/me')return respond(r,{user_id:owner,name:owner,rank:'Recruta',timezone:'America/Sao_Paulo'});
  if(p==='/api/command/home'){
   if(homeFailure)return respond(r,{detail:'Synthetic unavailable'},503);
   await new Promise(resolve=>setTimeout(resolve,100));
   const next={id:'review',title:'Revisar Licitações',start_minute:1080,end_minute:1115,confirmed:false,link:'/studies',why};
   return respond(r,{date:'2026-10-13',timezone:'America/Sao_Paulo',next_action:next,today:[next,{id:'fixed',title:'Compromisso fixo',start_minute:1140,end_minute:1200,confirmed:true,link:'/calendar',why}],today_count:2,attention:[{id:'bill',title:'Conta com vencimento registrado',subtitle:'R$ 10.01 · 2026-10-14',link:'/finance',why}],attention_count:1,areas:[{domain:'finance',facts:{expense:'10.01'},candidate_count:1,link:'/finance'},{domain:'training',facts:{completed_today:1},candidate_count:0,link:'/workouts'}],warnings:[],unscheduled_count:1});
  }
  if(p==='/api/command/memory'&&m==='GET')return respond(r,memory);
  if(p==='/api/command/memory'&&m==='POST'){
   const b=r.request().postDataJSON(),key=r.request().headers()['idempotency-key'];assert.ok(key);keys.push(key);assert.equal(b.category,'fact');
   if(!failed){memory=[{...b,memory_id:id,version:'a'.repeat(64),provenance:{origin:'user_declared',verified:false}}];failed=true;return respond(r,{detail:'Resposta perdida; tente novamente.'},502);}
   assert.equal(keys[0],key,'uncertain retry must reuse key');return respond(r,{memory_id:id,version:'a'.repeat(64)});
  }
  if(p.startsWith('/api/command/memory/')&&m==='PUT'){const b=r.request().postDataJSON();assert.equal(b.expected_version,'a'.repeat(64));return respond(r,{detail:'Memória alterada. Recarregue antes de corrigir.'},409);}
  if(p==='/api/command/audit')return respond(r,{items:[{id,actor:'user',event:'life.plan.accepted',action:'allocate',created_at:'2026-10-13T12:00:00Z',entity_type:'calendar',why,undo_available:!undo,undone_at:undo?'2026-10-13T13:00:00Z':null}],timezone:'America/Sao_Paulo',next_cursor:null});
  if(p===`/api/command/audit/${id}/undo`){assert.equal(r.request().postDataJSON().confirmed,true);assert.ok(r.request().headers()['idempotency-key']);undo=true;return respond(r,{undone:true});}
  if(p==='/api/command/scenarios'){
   const b=r.request().postDataJSON();assert.equal(b.routine.capacity_minutes,45);assert.equal(b.finance.monthly_income,'20.00');
   return respond(r,{read_only:true,routine:{state:{warnings:[]},plan:{blocks:[{candidate_id:id,title:'Estudo registrado',duration_minutes:30,reasons:why.evidence}],unscheduled:[]}},finance:{scenario:{months:[{month:'2026-10-01',net_change:'9.99',scenario_income:'20.00',scenario_expense:'10.01'}],assumptions:['Hipóteses declaradas.']}},limitations:['Nenhum registro alterado.']});
  }
  if(p==='/api/command/export/finance/json')return respond(r,{version:'sirius-export/1',records:[{id,amount:'10.01'}],next_cursor:other},200,{'content-disposition':'attachment; filename="sirius_finance.json"','x-export-next-cursor':other,'access-control-expose-headers':'X-Export-Next-Cursor'});
  if(p==='/api/search/global'){
   const second=u.searchParams.has('cursor'),item={id:second?other:id,type:'question',domain:'questions',title:second?'Questão seguinte':'Questão de Licitações',subtitle:'Questão',link:'/studies?question='+id};
   return respond(r,{results:[item],groups:[{domain:'questions',results:[item],next_cursor:second?null:other}]});
  }
  if(p==='/api/ai/conversation')return respond(r,{messages:[]});if(p==='/api/ai/conversations')return respond(r,[{conversation_id:id,title:'Conversa localizada'},{conversation_id:other,title:'Outra conversa'}]);
  if(p==='/api/ai/status')return respond(r,{agent:true});if(p==='/api/ai/preferences')return respond(r,{event_automation:{enabled:false}});
  if(p==='/api/ai/chat'){const b=r.request().postDataJSON(),hint=JSON.parse(b.page_context);assert.equal(hint.question_id,other);assert.equal(hint.intent,'explain');return respond(r,{user_message:{message_id:'u',role:'user',content:b.message},ai_message:{message_id:'a',role:'assistant',content:'Consulta contextual simulada.'}});}
  return respond(r,[]);
 });
 await page.goto('http://127.0.0.1:4190/dashboard');await page.getByRole('heading',{name:'Revisar Licitações',exact:true}).waitFor();
 assert.equal(calls.filter(r=>r.p==='/api/command/home').length,1);assert.equal(calls.filter(r=>r.p==='/api/stats/dashboard'||r.p==='/api/dashboard/panels'||r.p==='/api/command/memory').length,0,'closed tools and legacy panels must not fetch');
 const titles=await page.locator('#next-action-title,#today-title,#attention-title,#areas-title').allTextContents();assert.deepEqual(titles,['Próxima ação','Hoje','Atenção','Áreas']);
 if(width>=768)assert.equal(await page.evaluate(()=>{const heading=document.querySelector('#next-action-title'),rect=heading.getBoundingClientRect(),sidebar=document.querySelector('.sirius-sidebar').getBoundingClientRect();return rect.left>=sidebar.right&&Boolean(document.elementFromPoint(rect.left+4,rect.top+4)?.closest('[data-testid="command-center"]'));}),true,'desktop Home must remain visible beyond the fixed sidebar');
 await page.getByText('Por quê?',{exact:true}).first().click();await page.getByText('Prazo registrado para hoje.',{exact:true}).first().waitFor();
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await fs.promises.mkdir('test-results/command-center',{recursive:true});await page.screenshot({path:`test-results/command-center/home-${width}.png`,fullPage:width<768});
 await page.getByRole('button',{name:'Memória explícita',exact:true}).click();const tool=page.getByRole('region',{name:'Controle integrado'});
 await tool.getByText('Nenhuma memória explícita cadastrada.',{exact:true}).waitFor();await tool.getByLabel('Informação para lembrar',{exact:true}).fill('Trabalho de manhã.');
 await tool.getByRole('button',{name:'Confirmar memória',exact:true}).click();await tool.getByRole('alert').waitFor();assert.equal(await tool.getByLabel('Informação para lembrar',{exact:true}).inputValue(),'Trabalho de manhã.');
 await tool.getByRole('button',{name:'Confirmar memória',exact:true}).click();await tool.getByText('Trabalho de manhã.',{exact:true}).waitFor();assert.equal(keys.length,2);
 await tool.getByRole('button',{name:'Corrigir memória',exact:true}).click();await tool.getByLabel('Informação para lembrar',{exact:true}).fill('Rascunho preservado');await tool.getByRole('button',{name:'Salvar correção',exact:true}).click();await tool.getByText('Memória alterada. Recarregue antes de corrigir.',{exact:true}).waitFor();assert.equal(await tool.getByLabel('Informação para lembrar',{exact:true}).inputValue(),'Rascunho preservado');
 await page.getByRole('button',{name:'Histórico de ações',exact:true}).click();await tool.getByRole('button',{name:'Desfazer ação',exact:true}).click();assert.equal(undo,false);await tool.getByRole('button',{name:'Confirmar desfazer',exact:true}).click();await tool.getByText('Reversão confirmada.',{exact:true}).waitFor();assert.equal(undo,true);
 await page.getByRole('button',{name:'Simular cenários',exact:true}).click();await tool.getByLabel('Limite de minutos flexíveis (opcional)',{exact:true}).fill('45');await tool.getByLabel('Receita mensal hipotética (R$)',{exact:true}).fill('20.00');await tool.getByLabel('Despesa mensal hipotética (R$)',{exact:true}).fill('10.01');await tool.getByRole('button',{name:'Simular sem alterar registros',exact:true}).click();await tool.getByRole('heading',{name:'Prévia, sem aplicação',exact:true}).waitFor();await tool.getByText('Variação estimada de fluxo: R$ 9,99',{exact:true}).waitFor();assert.equal(calls.filter(r=>r.p==='/api/life/accept').length,0);
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await tool.scrollIntoViewIfNeeded();await page.screenshot({path:`test-results/command-center/scenarios-${width}.png`,fullPage:width<768});
 await page.getByRole('button',{name:'Exportar dados',exact:true}).click();const [download]=await Promise.all([page.waitForEvent('download'),tool.getByRole('button',{name:'Baixar página de dados',exact:true}).click()]);const exported=JSON.parse(await fs.promises.readFile(await download.path(),'utf8'));assert.equal(exported.records[0].amount,'10.01');await tool.getByRole('button',{name:'Selecionar próxima página',exact:true}).waitFor();
 await page.keyboard.press('Control+k');await page.getByRole('combobox',{name:'Buscar registros e ações'}).fill('Licitações');await page.getByRole('option',{name:'Questão de Licitações Questão',exact:true}).waitFor();await page.getByRole('option',{name:'Próxima página de Questões',exact:true}).click();await page.getByRole('option',{name:'Perguntar ao Sirius sobre Questão seguinte',exact:true}).click();await page.getByRole('button',{name:'Enviar mensagem',exact:true}).click();await page.getByText('Consulta contextual simulada.',{exact:true}).waitFor();await page.getByRole('button',{name:'Fechar assistente',exact:true}).click();
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);assert.deepEqual(errors,[]);
 homeFailure=true;await page.reload();await page.getByText('Não foi possível atualizar o Command Center. Tente novamente.',{exact:true}).waitFor();homeFailure=false;await page.getByRole('button',{name:'Tentar novamente',exact:true}).click();await page.getByRole('heading',{name:'Revisar Licitações',exact:true}).waitFor();
 owner='Other account';await page.evaluate(()=>window.dispatchEvent(new Event('sirius-auth-changed')));await page.getByRole('heading',{name:'Seu próximo passo, Other',exact:true}).waitFor();assert.equal(await page.getByText('Trabalho de manhã.',{exact:true}).count(),0);
 await page.goto('http://127.0.0.1:4190/chat?conversation='+id);await page.waitForFunction(expected=>sessionStorage.getItem('sirius-conversation')===expected,id);
 await page.getByLabel('Conversas recentes').selectOption(other);await page.waitForFunction(expected=>sessionStorage.getItem('sirius-conversation')===expected,other);
 await page.waitForTimeout(300);assert.equal(await page.evaluate(()=>sessionStorage.getItem('sirius-conversation')),other,'a consumed search link must not reset a subsequent manual selection');
 await context.close();console.log(`Command Center ${width}: passed`);
}
}catch(e){if(lastPage&&!lastPage.isClosed()){await fs.promises.mkdir('test-results/command-center',{recursive:true});await lastPage.screenshot({path:'test-results/command-center/failure.png',fullPage:true});console.error(await lastPage.locator('body').innerText());}throw e;}finally{await browser.close();await new Promise(r=>server.close(r));}})().catch(e=>{console.error(e);process.exitCode=1;});
