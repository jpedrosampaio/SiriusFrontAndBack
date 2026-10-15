// Browser presentation lifecycle; database arbitration is tested against PostgreSQL.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require('playwright');const root=path.join(process.cwd(),'build');
const server=http.createServer((req,res)=>{let f=path.join(root,new URL(req.url,'http://localhost').pathname);
  if(!f.startsWith(root+path.sep)){res.writeHead(403);return res.end();}if(!fs.existsSync(f)||fs.statSync(f).isDirectory())f=path.join(root,'index.html');
  res.setHeader('Content-Type',({'.js':'application/javascript','.css':'text/css','.html':'text/html'})[path.extname(f)]||'application/octet-stream');fs.createReadStream(f).pipe(res);});
(async()=>{await new Promise(r=>server.listen(4191,'127.0.0.1',r));const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
  try{for(const width of [320,390,768,1024,1440]){
    const owner='a1010000-0000-4000-8000-000000000001',identity='a1010000-0000-4000-8000-000000000002';
    const errors=[],writes=[],readKeys=[],claimedOwners=new Set();let rendered=0,reads=0,status='available',claims=0,inFlight=0,maxInFlight=0;
    const rule={enabled:true,frequency:'daily',priority:'high',channels:['in_app']};
    const state={user_id:owner,enabled:true,daily_cap:3,timezone:'America/Sao_Paulo',policy:{routine_popups:false,quiet_start:'00:00',quiet_end:'00:00',morning_time:'08:00',night_time:'21:00',weekly_time:'18:00',weekly_weekday:6,rules:{}},inherited_quiet_start:'22:00',inherited_quiet_end:'08:00',runtime_enabled:true,simulation_only:true,channels:{in_app:true,telegram:false},catalog:[{event_type:'task.overdue',title:'Tarefa pendente',domain:'tasks',rule}]};
    const fullMessage='Mensagem completa preservada na central. '+('Detalhe do registro original. '.repeat(80));
    const event=()=>({event_id:'event-own',event_type:'task.overdue',title:'Tarefa pendente',status:'processed',attempts:1,created_at:'2026-10-15T12:00:00Z',message:fullMessage,candidate:{facts:{title:'Revisão registrada'},reasons:['Ocorrência registrada vencida.']},deliveries:[{delivery_id:identity,channel:'in_app',status,attempts:0,history:[],retry_allowed:false,presentation:{state:rendered?'presented':'claimed'}}]});
    const contexts=[];
    const newContext=async()=>{
      const context=await browser.newContext({viewport:{width,height:900},serviceWorkers:'block'});contexts.push(context);
      await context.addInitScript(()=>{localStorage.setItem('sirius_onboarding_complete','true');window.__permissionRequests=0;
        window.Notification=class {static permission='default';static async requestPermission(){window.__permissionRequests++;return 'default';}};});
      await context.route('**/*',async r=>{const request=r.request(),url=new URL(request.url()),p=url.pathname;
        if(!p.startsWith('/api/'))return url.hostname==='127.0.0.1'?r.continue():r.abort();let data=[];
        const fulfill=(body,code=200)=>r.fulfill({status:code,contentType:'application/json',body:JSON.stringify(body)});
        if(request.method()!=='GET')writes.push(p);
        if(p==='/api/auth/me')data={user_id:state.user_id,name:'Owned account',xp:0,rank:'Recruta'};
        if(p==='/api/automations/state')data=state;
        if(p==='/api/automations/events')data={items:[event()],next_cursor:null};
        if(p==='/api/automations/telegram-replies')data={items:[],next_cursor:null};
        if(p==='/api/dashboard/daily-briefing')data={date:'2026-10-15',timezone:'America/Sao_Paulo',mode:'morning',facts:{tasks:{recorded_completed:0,pending_count:1,pending:[]},preparation:{recorded_minutes:0,planned_minutes:0},training:{recorded_completed:0,recorded_minutes:0},finance:{recorded_expense:'0.00'},tomorrow:{commitments:[]}},proposals:[],limitations:[]};
        if(p==='/api/automations/presentations/claim'){
          const requestOwner=state.user_id,alreadyClaimed=claimedOwners.has(requestOwner);
          claimedOwners.add(requestOwner);
          claims++;inFlight++;maxInFlight=Math.max(inFlight,maxInFlight);
          assert.match(request.headers()['idempotency-key'],/^[\da-f-]{36}$/);
          await new Promise(resolve=>setTimeout(resolve,120));
          data={item:alreadyClaimed?null:{delivery_id:requestOwner===owner?identity:'b1010000-0000-4000-8000-000000000002',event_type:'task.overdue',title:requestOwner===owner?'Aviso recente da conta':'Aviso da segunda conta',preview:'Uma revisão registrada precisa de atenção.',grouped_count:8}};
          inFlight--;
        }
        if(p.startsWith('/api/automations/presentations/')&&!p.endsWith('/claim')){rendered++;data={state:'presented'};}
        if(p===`/api/automations/deliveries/${identity}`){
          reads++;readKeys.push(request.headers()['idempotency-key']);
          if(reads===1)return fulfill({detail:'Leitura não confirmada. Tente novamente.'},503);
          status='delivered';data={status};
        }
        if(p==='/api/automations/policy'){Object.assign(state,{policy:request.postDataJSON().policy});data=state;}
        return fulfill(data);
      });return context;
    };
    const context=await newContext(),page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
    const firstAck=page.waitForResponse(r=>new URL(r.url()).pathname===`/api/automations/presentations/${identity}`);
    await page.goto('http://127.0.0.1:4191/notifications');
    await page.getByText('Aviso recente da conta',{exact:true}).waitFor();await firstAck;
    const notice=page.locator('[data-sonner-toast]').filter({hasText:'Aviso recente da conta'});
    assert.ok((await notice.innerText()).length<250);assert.equal(reads,0);assert.equal(rendered,1);
    await notice.getByRole('button',{name:'Close toast',exact:true}).click();assert.equal(reads,0);
    await page.evaluate(()=>{for(let n=0;n<8;n++)window.dispatchEvent(new Event('online'));});
    // The automatic controller never overlaps its own requests.
    await page.waitForResponse(r=>new URL(r.url()).pathname==='/api/notifications/check');
    assert.equal(maxInFlight,1);
    const second=await context.newPage();await second.goto('http://127.0.0.1:4191/notifications');
    await second.waitForResponse(r=>new URL(r.url()).pathname==='/api/notifications/check');
    assert.equal(await second.getByText('Aviso recente da conta',{exact:true}).count(),0);
    const device=await newContext(),other=await device.newPage();await other.goto('http://127.0.0.1:4191/notifications');
    await other.waitForResponse(r=>new URL(r.url()).pathname==='/api/notifications/check');
    assert.equal(await other.getByText('Aviso recente da conta',{exact:true}).count(),0);
    const reloaded=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/notifications/check');await page.reload();await reloaded;
    assert.equal(await page.getByText('Aviso recente da conta',{exact:true}).count(),0);assert.equal(rendered,1);
    assert.equal(await page.evaluate(()=>window.__permissionRequests),0);
    await page.getByRole('tab',{name:'Automações',exact:true}).click();
    const panel=page.getByRole('region',{name:'Automações inteligentes'});
    await panel.getByText('Ver mensagem completa',{exact:true}).click();await panel.getByText(fullMessage,{exact:true}).waitFor();
    await panel.getByRole('button',{name:'Marcar como lido'}).click();await panel.getByRole('alert').getByText('Leitura não confirmada. Tente novamente.').waitFor();
    await panel.getByRole('button',{name:'Marcar como lido'}).click();await panel.getByText('Sirius · Recebimento confirmado',{exact:false}).waitFor();
    assert.equal(reads,2);assert.equal(new Set(readKeys).size,1);
    await panel.getByLabel('Receber pop-ups de resumos rotineiros',{exact:true}).check();
    await panel.getByRole('button',{name:'Salvar automações'}).click();await panel.getByText('Preferências salvas.').waitFor();
    assert.equal(state.policy.routine_popups,true);assert.ok(claims>=4);
    // The global presenter clears the preceding account and re-identifies the owner.
    state.user_id='b1010000-0000-4000-8000-000000000001';
    await page.evaluate(()=>window.dispatchEvent(new Event('sirius-auth-changed')));
    try { await page.getByText('Aviso da segunda conta',{exact:true}).waitFor(); }
    catch(error){console.error({claims,rendered,errors,visibility:await page.evaluate(()=>document.visibilityState),url:page.url(),writes});console.error((await page.locator('body').innerText()).slice(-1500));throw error;}
    assert.equal(await page.getByText('Aviso recente da conta',{exact:true}).count(),0);
    state.user_id=null;state.enabled=false;
    await page.evaluate(()=>window.dispatchEvent(new Event('sirius-auth-changed')));
    await page.getByText('Aviso da segunda conta',{exact:true}).waitFor({state:'hidden'});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`overflow ${width}`);
    assert.deepEqual(errors,[]);assert.ok(writes.every(p=>p.startsWith('/api/automations/')));
    await fs.promises.mkdir(path.join('test-results','notification-presentation'),{recursive:true});await page.screenshot({path:path.join('test-results','notification-presentation',`${width}.png`),fullPage:true});
    for(const c of contexts)await c.close();console.log(`Notification presentation ${width}: passed`);
  }}finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});
