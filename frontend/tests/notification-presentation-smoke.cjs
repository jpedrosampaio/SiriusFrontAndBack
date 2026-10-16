// Browser presentation lifecycle; database arbitration is tested against PostgreSQL.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require('playwright');const root=path.join(process.cwd(),'build');
const server=http.createServer((req,res)=>{let f=path.join(root,new URL(req.url,'http://localhost').pathname);
  if(!f.startsWith(root+path.sep)){res.writeHead(403);return res.end();}if(!fs.existsSync(f)||fs.statSync(f).isDirectory())f=path.join(root,'index.html');
  res.setHeader('Content-Type',({'.js':'application/javascript','.css':'text/css','.html':'text/html'})[path.extname(f)]||'application/octet-stream');fs.createReadStream(f).pipe(res);});
(async()=>{await new Promise(r=>server.listen(4191,'127.0.0.1',r));const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
  try{for(const width of [320,390,768,1024,1440]){
    const owner='a1010000-0000-4000-8000-000000000001',identity='a1010000-0000-4000-8000-000000000002';
    const errors=[],writes=[],readKeys=[],claimKeys=[],reservations=new Map();let rendered=0,reads=0,status='available',claims=0,inFlight=0,maxInFlight=0,reminderAvailable=false,pairedReminders=true,legacyFailureTested=false,uncertainResponse=false;
    const nativeSlots=new Map();let nativeScenario='desktop',nativeAckLost=false,nativeAckCount=0,nativeConflictDone=false,configurationFailure=false;
    const rule={enabled:true,frequency:'daily',priority:'high',channels:['in_app']};
    const state={user_id:owner,enabled:true,daily_cap:3,timezone:'America/Sao_Paulo',policy:{routine_popups:false,quiet_start:'00:00',quiet_end:'00:00',morning_time:'08:00',night_time:'21:00',weekly_time:'18:00',weekly_weekday:6,rules:{}},inherited_quiet_start:'22:00',inherited_quiet_end:'08:00',runtime_enabled:true,simulation_only:true,channels:{in_app:true,telegram:false},catalog:[{event_type:'task.overdue',title:'Tarefa pendente',domain:'tasks',rule}]};
    const fullMessage='Mensagem completa preservada na central. '+('Detalhe do registro original. '.repeat(80));
    const event=()=>({event_id:'event-own',event_type:'task.overdue',title:'Tarefa pendente',status:'processed',attempts:1,created_at:'2026-10-15T12:00:00Z',message:fullMessage,candidate:{facts:{title:'Revisão registrada'},reasons:['Ocorrência registrada vencida.']},deliveries:[{delivery_id:identity,channel:'in_app',status,attempts:0,history:[],retry_allowed:false,presentation:{state:rendered?'presented':'claimed'}}]});
    const contexts=[];
    const newContext=async(permission='default',nativeMode='desktop')=>{
      const context=await browser.newContext({viewport:{width,height:900},serviceWorkers:'block'});contexts.push(context);
      await context.addInitScript(({permission,nativeMode})=>{localStorage.setItem('sirius_onboarding_complete','true');window.__permissionRequests=0;window.__nativeNotices=[];window.__nativeMode=nativeMode;
        Object.defineProperty(navigator.serviceWorker,'getRegistration',{configurable:true,value:async()=>window.__nativeMode==='desktop'?undefined:{
          async showNotification(title,options){if(window.__nativeMode==='broken')throw new TypeError('SW unavailable');window.__nativeNotices.push({title,...options,transport:'service-worker',closed:false});},
          async getNotifications({tag}){return window.__nativeNotices.filter(n=>n.tag===tag).map(n=>({...n,close(){n.closed=true;}}));}}});
        window.Notification=class {static permission=permission;static async requestPermission(){window.__permissionRequests++;return permission;}
          constructor(title,options){if(window.__nativeMode!=='desktop')throw new TypeError('Use service worker');this.record={title,...options,closed:false};window.__nativeNotices.push(this.record);}close(){this.record.closed=true;}};},{permission,nativeMode});
      await context.route('**/*',async r=>{const request=r.request(),url=new URL(request.url()),p=url.pathname;
        if(!p.startsWith('/api/'))return url.hostname==='127.0.0.1'?r.continue():r.abort();let data=[];
        const fulfill=(body,code=200)=>r.fulfill({status:code,contentType:'application/json',body:JSON.stringify(body)});
        if(request.method()!=='GET')writes.push(p);
        if(p==='/api/auth/me')data={user_id:state.user_id,name:'Owned account',xp:0,rank:'Recruta'};
        if(p==='/api/automations/state'){assert.equal(uncertainResponse,false,'immediate recovery must not spend its replay window refetching configuration');if(configurationFailure)return fulfill({detail:'Estado temporariamente indisponível'},503);data=state;}
        if(p==='/api/automations/events')data={items:[event()],next_cursor:null};
        if(p==='/api/notifications')data=[...nativeSlots.values()].map(n=>({...n,native_presentation:{state:n.nativeState,occurrence:'2026-10-15',attempted_at:'2026-10-15T12:00:00+00:00',attempts:n.attempts},native_claim:undefined}));
        if(p==='/api/automations/telegram-replies')data={items:[],next_cursor:null};
        if(p==='/api/dashboard/daily-briefing')data={date:'2026-10-15',timezone:'America/Sao_Paulo',mode:'morning',facts:{tasks:{recorded_completed:0,pending_count:1,pending:[]},preparation:{recorded_minutes:0,planned_minutes:0},training:{recorded_completed:0,recorded_minutes:0},finance:{recorded_expense:'0.00'},tomorrow:{commitments:[]}},proposals:[],limitations:[]};
        if(p==='/api/automations/presentations/claim'){
          const requestOwner=state.user_id,key=request.headers()['idempotency-key'],prior=reservations.get(requestOwner);
          const record=prior||{key,rendered:false,item:{delivery_id:requestOwner===owner?identity:'b1010000-0000-4000-8000-000000000002',event_type:'task.overdue',title:requestOwner===owner?'Aviso recente da conta':'Aviso da segunda conta',preview:'Uma revisão registrada precisa de atenção.',grouped_count:8}};
          reservations.set(requestOwner,record);claimKeys.push(key);
          claims++;inFlight++;maxInFlight=Math.max(inFlight,maxInFlight);
          assert.match(request.headers()['idempotency-key'],/^[\da-f-]{36}$/);
          await new Promise(resolve=>setTimeout(resolve,120));
          inFlight--;
          // The claim commits, but its first HTTP response is lost. Only a
          // prompt same-key retry can recover it before the replay deadline.
          if(!prior&&requestOwner===owner){uncertainResponse=true;return fulfill({detail:'Resposta perdida'},503);}
          uncertainResponse=false;
          data={user_id:requestOwner,item:record.key===key&&!record.rendered?record.item:null};
        }
        if(p.startsWith('/api/automations/presentations/')&&!p.endsWith('/claim')){rendered++;for(const record of reservations.values())if(p.endsWith(record.item.delivery_id))record.rendered=true;data={state:'presented'};}
        if(p==='/api/notifications/check'){
          const allowed=url.searchParams.get('browser_allowed');assert.ok(['true','false'].includes(allowed));
          if(state.user_id!=='a1010000-0000-4000-8000-000000000001'&&!legacyFailureTested){legacyFailureTested=true;return fulfill({detail:'Lembretes temporariamente indisponíveis'},503);}
          if(pairedReminders&&state.user_id===owner){pairedReminders=false;data=[{notification_id:'in-app-once',title:'Lembrete único',message:'Detalhes na central',channels:['in_app']},{notification_id:'hybrid-once',title:'Lembrete sem permissão nativa',message:'Detalhes na central',channels:['in_app','browser']}];}
          if(reminderAvailable&&allowed==='true'){reminderAvailable=false;data=[1,2].map(n=>{
            const notification_id=`${nativeScenario}-reminder-${n}`,row={notification_id,user_id:state.user_id,title:`Lembrete ${n}`,enabled:true,repeat:'none',scheduled_time:'09:00',created_at:'2026-10-14T12:00:00Z',last_sent:null,
              message:'Texto completo reservado à central',channels:['browser'],nativeState:'reserved',attempts:1,native_claim:{notification_id,claim_id:`${nativeScenario}-claim-${n}`,occurrence:'2026-10-15'}};
            nativeSlots.set(notification_id,row);return row;});}
        }
        if(p==='/api/notifications/native-presentations'){
          nativeAckCount++;const body=request.postDataJSON();
          if(nativeScenario==='conflict'&&!nativeConflictDone){nativeConflictDone=true;nativeSlots.delete('conflict-reminder-1');}
          if(body.claims.some(claim=>!nativeSlots.has(claim.notification_id)))return fulfill({detail:'Lembrete excluído'},404);
          for(const claim of body.claims){const row=nativeSlots.get(claim.notification_id);assert.equal(row.native_claim.claim_id,claim.claim_id);row.nativeState=body.outcome;if(body.outcome==='accepted')row.last_sent='2026-10-15T12:00:01Z';}
          if(nativeScenario==='desktop'&&!nativeAckLost){nativeAckLost=true;return fulfill({detail:'Resposta do ACK perdida após commit'},503);}
          data={user_id:state.user_id,items:[]};
        }
        if(p.endsWith('/retry-native')){const row=nativeSlots.get(p.split('/')[3]);assert.ok(row);assert.match(request.headers()['idempotency-key'],/^[\da-f-]{36}$/);
          row.native_claim={...row.native_claim,claim_id:row.native_claim.claim_id+'-retry'};row.nativeState='reserved';row.attempts++;data={user_id:state.user_id,item:row};}
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
    await notice.getByText('Há 2 lembretes na central.',{exact:false}).waitFor();
    assert.equal(claimKeys[0],claimKeys[1],'lost response retries the same key before normal polling');
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
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`central overflow ${width}`);
    // The global presenter clears the preceding account and re-identifies the owner.
    state.user_id='b1010000-0000-4000-8000-000000000001';
    await page.evaluate(()=>window.dispatchEvent(new Event('sirius-auth-changed')));
    try { await page.getByText('Aviso da segunda conta',{exact:true}).waitFor(); }
    catch(error){console.error({claims,rendered,errors,visibility:await page.evaluate(()=>document.visibilityState),url:page.url(),writes});console.error((await page.locator('body').innerText()).slice(-1500));throw error;}
    assert.equal(await page.getByText('Aviso recente da conta',{exact:true}).count(),0);
    assert.equal(legacyFailureTested,true,'a failed reminder check must not hide the claimed automation');
    state.user_id=null;state.enabled=false;
    await page.evaluate(()=>window.dispatchEvent(new Event('sirius-auth-changed')));
    await page.getByText('Aviso da segunda conta',{exact:true}).waitFor({state:'hidden'});
    state.user_id='b1010000-0000-4000-8000-000000000001';reminderAvailable=true;
    const nativeContext=await newContext('granted'),nativePage=await nativeContext.newPage();
    const firstNativeAck=nativePage.waitForResponse(r=>new URL(r.url()).pathname==='/api/notifications/native-presentations');
    await nativePage.goto('http://127.0.0.1:4191/notifications');
    await nativePage.waitForFunction(()=>window.__nativeNotices.length===1);
    const native=await nativePage.evaluate(()=>window.__nativeNotices);
    assert.equal(native[0].title,'2 lembretes disponíveis');assert.equal(native[0].body,'Confira os detalhes na central de Notificações.');
    await firstNativeAck;
    const recoveredAck=nativePage.waitForResponse(r=>new URL(r.url()).pathname==='/api/notifications/native-presentations'&&r.status()===200);
    await nativePage.evaluate(()=>window.dispatchEvent(new Event('online')));await recoveredAck;
    assert.equal(await nativePage.evaluate(()=>window.__nativeNotices.length),1,'lost ACK retries the receipt, not the OS presentation');assert.equal(nativeAckCount,2);
    nativeScenario='mobile';reminderAvailable=true;
    const mobileContext=await newContext('granted','mobile'),mobilePage=await mobileContext.newPage();
    await mobilePage.goto('http://127.0.0.1:4191/notifications');await mobilePage.waitForFunction(()=>window.__nativeNotices.length===1);
    assert.equal((await mobilePage.evaluate(()=>window.__nativeNotices))[0].transport,'service-worker');
    await mobilePage.getByText('Aviso aceito pelo navegador; isso não confirma leitura.',{exact:true}).first().waitFor();
    nativeScenario='broken';reminderAvailable=true;
    const brokenContext=await newContext('granted','broken'),brokenPage=await brokenContext.newPage();
    await brokenPage.goto('http://127.0.0.1:4191/notifications');
    await brokenPage.getByText('O navegador recusou o aviso. O lembrete foi preservado.',{exact:true}).first().waitFor();
    assert.equal(await brokenPage.evaluate(()=>window.__nativeNotices.length),0);
    for(const row of nativeSlots.values())if(row.notification_id.startsWith('broken'))assert.equal(row.last_sent,null);
    await brokenPage.evaluate(()=>{window.__nativeMode='mobile';});
    await brokenPage.getByRole('button',{name:'Tentar aviso no navegador',exact:true}).first().click();
    await brokenPage.waitForFunction(()=>window.__nativeNotices.length===1);
    assert.equal((await brokenPage.evaluate(()=>window.__nativeNotices))[0].transport,'service-worker');
    nativeScenario='conflict';reminderAvailable=true;
    const conflictContext=await newContext('granted','mobile'),conflictPage=await conflictContext.newPage();
    const peerAck=conflictPage.waitForResponse(r=>new URL(r.url()).pathname==='/api/notifications/native-presentations'&&r.status()===200&&r.request().postDataJSON().claims.some(c=>c.notification_id==='conflict-reminder-2'));
    await conflictPage.goto('http://127.0.0.1:4191/notifications');await peerAck;
    assert.equal(nativeSlots.get('conflict-reminder-2').nativeState,'accepted','a deleted group peer must not discard valid ACKs');
    assert.equal(await conflictPage.evaluate(()=>window.__nativeNotices.length),1,'ACK decomposition must never re-show the OS notice');
    configurationFailure=true;
    const queuedContext=await newContext('granted','mobile'),queuedPage=await queuedContext.newPage();
    const failedConfiguration=queuedPage.waitForResponse(r=>new URL(r.url()).pathname==='/api/automations/state'&&r.status()===503);
    await queuedPage.goto('http://127.0.0.1:4191/notifications');await failedConfiguration;
    await queuedPage.evaluate(()=>window.dispatchEvent(new CustomEvent('sirius-native-retry',{detail:{user_id:'another-owner',item:{notification_id:'foreign',title:'Aviso de outra conta',channels:['browser']}}})));
    const queuedRetry=queuedPage.waitForResponse(r=>new URL(r.url()).pathname.endsWith('/retry-native'));
    await queuedPage.getByRole('button',{name:'Tentar aviso no navegador',exact:true}).first().click();await queuedRetry;
    assert.equal(await queuedPage.evaluate(()=>window.__nativeNotices.length),0,'unidentified account must not present personal notices');
    configurationFailure=false;await queuedPage.evaluate(()=>window.dispatchEvent(new Event('online')));
    await queuedPage.waitForFunction(()=>window.__nativeNotices.length===1);
    assert.equal((await queuedPage.evaluate(()=>window.__nativeNotices))[0].transport,'service-worker','queued manual retry survives configuration failure');
    assert.notEqual((await queuedPage.evaluate(()=>window.__nativeNotices))[0].title,'Aviso de outra conta');
    for(const nativeView of [nativePage,mobilePage,brokenPage,queuedPage,conflictPage])assert.equal(await nativeView.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`native central overflow ${width}`);
    await fs.promises.mkdir(path.join('test-results','notification-presentation'),{recursive:true});
    await queuedPage.screenshot({path:path.join('test-results','notification-presentation',`native-${width}.png`),fullPage:true});
    assert.equal(await nativePage.evaluate(()=>window.__permissionRequests),0);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`overflow ${width}`);
    assert.deepEqual(errors,[]);assert.ok(writes.every(p=>p.startsWith('/api/automations/')||p==='/api/notifications/native-presentations'||p.endsWith('/retry-native')));
    await fs.promises.mkdir(path.join('test-results','notification-presentation'),{recursive:true});await page.screenshot({path:path.join('test-results','notification-presentation',`${width}.png`),fullPage:true});
    for(const c of contexts)await c.close();console.log(`Notification presentation ${width}: passed`);
  }}finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});
