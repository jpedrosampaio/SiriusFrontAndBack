// Real browser at all mandatory widths; no network providers or production writes.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require('playwright');const root=path.join(process.cwd(),'build');
const server=http.createServer((req,res)=>{let f=path.join(root,new URL(req.url,'http://localhost').pathname);
  if(!f.startsWith(root+path.sep)){res.writeHead(403);return res.end();}if(!fs.existsSync(f)||fs.statSync(f).isDirectory())f=path.join(root,'index.html');
  res.setHeader('Content-Type',({'.js':'application/javascript','.css':'text/css','.html':'text/html'})[path.extname(f)]||'application/octet-stream');fs.createReadStream(f).pipe(res);});
(async()=>{await new Promise(r=>server.listen(4187,'127.0.0.1',r));const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
  try{for(const width of [320,390,768,1024,1440]){
    const context=await browser.newContext({viewport:{width,height:900},serviceWorkers:'block'});
    await context.addInitScript(()=>localStorage.setItem('sirius_onboarding_complete','true'));
    const errors=[],writes=[],keys=[];let states=0,lost=true,saves=0,accepted=false;
    const rule={enabled:true,frequency:'daily',priority:'medium',channels:['in_app']};
    const state={enabled:false,daily_cap:3,timezone:'America/Sao_Paulo',policy:{quiet_start:null,quiet_end:null,morning_time:'08:00',night_time:'21:00',weekly_time:'18:00',weekly_weekday:6,rules:{}},inherited_quiet_start:'22:00',inherited_quiet_end:'08:00',runtime_enabled:true,simulation_only:true,channels:{in_app:true,telegram:false},telegram_paired:false,scan:null,catalog:[{event_type:'task.overdue',title:'Tarefa pendente',domain:'tasks',rule} ]};
    const event={event_id:'event-own',event_type:'task.overdue',title:'Tarefa pendente',status:'processed',attempts:1,created_at:'2026-10-13T09:00:00Z',candidate:{facts:{title:'Revisar assunto registrado'},reasons:['Ocorrência registrada vencida e ainda pendente.']},deliveries:[{delivery_id:'delivery-own',channel:'in_app',status:'available',attempts:0,history:[],retry_allowed:false},{delivery_id:'telegram-own',channel:'telegram',status:'uncertain',attempts:1,last_error:'provider_confirmation_unknown',retry_allowed:true,history:[{at:'2026-10-13T09:01:00Z',outcome:'uncertain'}]}]};
    const report={date:'2026-10-13',timezone:'America/Sao_Paulo',mode:'morning',facts:{tasks:{recorded_completed:1,pending_count:1,pending:[{id:'task-own',title:'Estudar conteúdo',date:'2026-10-13'}]},preparation:{recorded_minutes:20,planned_minutes:40},training:{recorded_completed:0,recorded_minutes:0},finance:{recorded_expense:'0.00'},tomorrow:{commitments:[]}},proposals:[{title:'Revisar disponibilidade',link:'/calendar'}],limitations:['Modelos atuais não são snapshots históricos.']};
    const fulfill=(r,data,status=200)=>r.fulfill({status,contentType:'application/json',body:JSON.stringify(data)});
    await context.route('**/*',async r=>{const request=r.request(),url=new URL(request.url()),p=url.pathname;
      if(!p.startsWith('/api/'))return url.hostname==='127.0.0.1'?r.continue():r.abort();let data=[];
      if(request.method()!=='GET')writes.push(p);
      if(p==='/api/auth/me')data={user_id:'event-user',name:'Event Test',xp:0,rank:'Recruta'};
      if(p==='/api/automations/state'){states++;if(states===2)return fulfill(r,{detail:'Falha temporária da leitura'},503);data=state;}
      if(p==='/api/automations/events')data={items:[event,{event_id:'report-own',event_type:'brief.daily',title:'Resumo anterior registrado',status:'processed',attempts:1,created_at:'2026-10-12T12:00:00Z',candidate:{facts:{...report,version:'event-briefing/2'},reasons:['Resumo dos registros próprios.']},deliveries:[]}],next_cursor:null};
      if(p==='/api/dashboard/daily-briefing')data={...report,mode:url.searchParams.get('mode')};
      if(p==='/api/automations/policy'){
        saves++;keys.push(request.headers()['idempotency-key']);assert.ok(keys.at(-1));
        Object.assign(state,{enabled:request.postDataJSON().enabled,daily_cap:request.postDataJSON().daily_cap,policy:request.postDataJSON().policy});
        if(lost){lost=false;return fulfill(r,{detail:'Resposta perdida; retome com a mesma chave'},504);}data=state;
      }
      if(p.startsWith('/api/automations/deliveries/')){
        assert.ok(request.headers()['idempotency-key']);const body=request.postDataJSON();
        if(body.action==='read')event.deliveries[0].status='delivered';
        if(body.action==='retry'){assert.equal(body.accept_duplicate_risk,true);accepted=true;event.deliveries[1].status='pending';event.deliveries[1].retry_allowed=false;}
        data={success:true};
      }
      await fulfill(r,data);
    });
    const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
    await page.goto('http://127.0.0.1:4187/notifications');await page.getByRole('tab',{name:'Automações',exact:true}).click();
    const panel=page.getByRole('region',{name:'Automações inteligentes'});
    await panel.getByRole('alert').getByText('Falha temporária da leitura').waitFor();
    await panel.getByRole('button',{name:'Tentar novamente'}).click();await panel.getByText('Sirius · Disponível no Sirius',{exact:false}).waitFor();
    await panel.getByText(/Modo de simulação do servidor/).waitFor();assert.equal(writes.length,0);
    await panel.getByLabel('Ativar automações',{exact:true}).check();await panel.getByLabel('Silêncio a partir de').fill('22:30');
    await panel.getByRole('button',{name:'Salvar automações'}).click();await panel.getByRole('alert').getByText('Resposta perdida; retome com a mesma chave').waitFor();
    await panel.getByRole('button',{name:'Salvar automações'}).click();await panel.getByText('Preferências salvas.').waitFor();
    assert.equal(saves,2);assert.equal(new Set(keys).size,1);assert.equal(state.policy.quiet_start,'22:30');
    await panel.getByLabel('Período do resumo').selectOption('weekly');const activeReport=panel.getByRole('article',{name:'Resumo integrado'}).first();await activeReport.waitFor();
    assert.equal(await panel.getByRole('article',{name:'Resumo integrado'}).count(),2,'current report and historical evidence are viewable');
    await activeReport.getByText('Fontes e limites do resumo').click();await activeReport.getByText('Modelos atuais não são snapshots históricos.').waitFor();
    await panel.getByRole('button',{name:'Marcar como lido'}).click();await panel.getByText('Sirius · Recebimento confirmado',{exact:false}).waitFor();
    await panel.getByRole('button',{name:'Reenviar com confirmação'}).click();await panel.getByText('Telegram · Aguardando envio',{exact:false}).waitFor();assert.equal(accepted,true);
    await panel.getByText('Tipos de eventos e canais',{exact:true}).click();await panel.getByLabel('Prioridade Tarefa pendente').selectOption('high');
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`horizontal overflow ${width}`);
    assert.deepEqual(errors,[]);assert.ok(writes.every(p=>p.startsWith('/api/automations/')),`unrelated writes ${writes}`);
    await fs.promises.mkdir(path.join('test-results','automations'),{recursive:true});await page.screenshot({path:path.join('test-results','automations',`${width}.png`),fullPage:true});
    await context.close();console.log(`Automation flow ${width}: passed`);
  }}finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});
