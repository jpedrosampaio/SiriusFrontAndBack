// Synthetic, intercepted API only. Control response order to reproduce real UI races.
const fs=require('node:fs'), path=require('node:path'), http=require('node:http'), assert=require('node:assert/strict');
const {chromium}=require('playwright');
const build=path.join(process.cwd(),'build');
const server=http.createServer((req,res)=>{
  let file=path.join(build,new URL(req.url,'http://localhost').pathname);
  if(!file.startsWith(build+path.sep)) {res.writeHead(403);return res.end();}
  if(!fs.existsSync(file)||fs.statSync(file).isDirectory())file=path.join(build,'index.html');
  res.setHeader('Content-Type',({'.js':'application/javascript','.css':'text/css','.html':'text/html','.png':'image/png','.svg':'image/svg+xml'})[path.extname(file)]||'application/octet-stream');
  fs.createReadStream(file).pipe(res);
});
const waitFor=async fn=>{for(let i=0;i<100;i++){if(fn())return;await new Promise(r=>setTimeout(r,50));}throw Error('Controlled request missing');};
(async()=>{
 await new Promise(r=>server.listen(4175,'127.0.0.1',r));
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
 try {for(const width of [1440,1024,768,390,320]){
  const context=await browser.newContext({viewport:{width,height:900},serviceWorkers:'block'});
  await context.addInitScript(()=>localStorage.setItem('sirius_onboarding_complete','true'));
  const pending={},counts={},posts=[],checks={},taskKeys=[];let task=null,empty=false,zero=false,taskFailure=true;
  const user={user_id:'operational-fixture',name:'User',rank:'Recruta',xp:0};
  const plan={plan_id:'p',name:'Rapid plan',exercises:[0,1,2].map(i=>({name:'Exercise '+i,sets:3,reps:12}))};
  const fulfill=(route,body,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
  await context.route('**/*',async route=>{
   const url=new URL(route.request().url()),p=url.pathname,method=route.request().method();
   if(!p.startsWith('/api/'))return url.hostname==='127.0.0.1'?route.continue():route.abort();
   counts[p]=(counts[p]||0)+1;
   if(p==='/api/ai/conversation'||p==='/api/ai/conversations'){pending[p]=route;return;}
   if(p==='/api/ai/chat'){
    const body=route.request().postDataJSON();return fulfill(route,{user_message:{message_id:'new-u',request_id:body.request_id,role:'user',content:body.message},ai_message:{message_id:'new-a',role:'assistant',content:'New answer'}});
   }
   if(p.includes('/toggle/')){posts.push(route);return;}
   if(p==='/api/auth/me')return fulfill(route,user);
   if(p==='/api/dashboard/panels')return fulfill(route,{panels:{daily:{summary:{score:empty||zero?0:35,greeting:'Hello',progress_summary:'Summary'},raw_data:empty?{}:zero?{tasks_pending:20}:{tasks_done:7,tasks_pending:13}}},errors:[]});
   if(p==='/api/ai/daily')return fulfill(route,{commitments:[],plan:{date:'2026-10-07',available_minutes:180,conflicts:[{}],blocks:[{task_id:'wake',title:'Acordar',kind:'fixed_task',start_minute:390,end_minute:420,past_due:true,duration_minutes:30,duration_estimated:true},{task_id:'study',title:'Study after midday',kind:'flexible_task',start_minute:900,end_minute:945,duration_minutes:45}],unscheduled:[]}});
   if(p==='/api/tasks'&&method==='POST'){
    taskKeys.push(route.request().headers()['idempotency-key']);
    task={...route.request().postDataJSON(),task_id:'task',xp_reward:10};
    if(taskFailure){taskFailure=false;return fulfill(route,{detail:'Synthetic lost response'},504);}
    return fulfill(route,task);
   }
   if(p==='/api/tasks/task'&&method==='PUT'){task={...task,...route.request().postDataJSON()};return fulfill(route,task);}
   if(p==='/api/tasks')return fulfill(route,task?[task]:[]);
   if(p==='/api/workout-plans')return fulfill(route,[plan]);
   if(p==='/api/daily-workout-status')return fulfill(route,{p:{exercises_status:{},completed:false}});
   if(p==='/api/workout-sessions/active')return fulfill(route,{active:false});
   if(p==='/api/stats/dashboard')return fulfill(route,{});
   if(p.includes('stats'))return fulfill(route,{});
   return fulfill(route,[]);
  });
  const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:4175/chat');
  await waitFor(()=>pending['/api/ai/conversation']&&pending['/api/ai/conversations']);
  await page.getByLabel('Mensagem para o assistente',{exact:true}).fill('Before hydration');
  await page.getByRole('button',{name:'Enviar mensagem',exact:true}).click();
  await page.getByText('New answer',{exact:true}).waitFor();
  await fulfill(pending['/api/ai/conversation'],{messages:[{message_id:'old',role:'assistant',content:'Old history'}]});
  await fulfill(pending['/api/ai/conversations'],[{conversation_id:'other',title:'Known conversation'},{conversation_id:'primary',title:'Existing primary'}]);
  await page.getByText('Old history',{exact:true}).waitFor();
  assert.equal(await page.getByText('New answer',{exact:true}).count(),1);
  assert.equal(await page.getByText('Before hydration',{exact:true}).count(),1);
  assert.equal(await page.getByLabel('Conversas recentes').locator('option[value="other"]').count(),1);
  assert.equal(counts['/api/ai/conversation'],1);assert.equal(counts['/api/ai/conversations'],1);
  await page.goto('http://127.0.0.1:4175/dashboard');
  await page.getByText('35%',{exact:true}).waitFor();await page.getByText('Horário definido',{exact:false}).waitFor();
  await page.getByText('Não concluído · horário já passou',{exact:true}).waitFor();
  await page.getByText('Conflito de horário:',{exact:false}).waitFor();
  empty=true;await page.reload();await page.getByText('Sem itens planejados',{exact:true}).waitFor();
  empty=false;zero=true;await page.reload();await page.getByLabel('Progresso do dia').getByText('0%',{exact:true}).waitFor();
  assert.equal(await page.getByText('Sem itens planejados',{exact:true}).count(),0);
  await page.goto('http://127.0.0.1:4175/tasks');await page.getByTestId('tasks-create-btn').click();
  await page.getByTestId('task-title-input').fill('Acordar');await page.getByLabel('Horário (opcional)',{exact:true}).fill('06:30');
  await page.getByLabel('Duração em minutos (opcional)',{exact:true}).fill('45');
  fs.mkdirSync('test-results',{recursive:true});await page.screenshot({path:`test-results/task-scheduling-${width}.png`});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
  await page.getByTestId('task-submit-btn').click();await page.getByText('Erro ao salvar tarefa. Os campos foram preservados.',{exact:true}).waitFor();
  assert.equal(await page.getByLabel('Horário (opcional)',{exact:true}).inputValue(),'06:30');
  await page.getByTestId('task-submit-btn').click();await page.getByText('06:30 · 45 min',{exact:true}).waitFor();
  assert.equal(taskKeys.length,2);assert.ok(taskKeys[0]);assert.equal(taskKeys[0],taskKeys[1]);
  assert.equal(task.scheduled_time,'06:30');assert.equal(task.duration_minutes,45);
  await page.getByRole('button',{name:'Editar tarefa',exact:true}).click();
  await page.getByLabel('Horário (opcional)',{exact:true}).fill('');await page.getByLabel('Duração em minutos (opcional)',{exact:true}).fill('');
  await page.getByTestId('task-submit-btn').click();await page.getByText('Sem horário · 30 min estimados',{exact:true}).waitFor();
  assert.equal(task.scheduled_time,null);assert.equal(task.duration_minutes,null);
  await page.goto('http://127.0.0.1:4175/workouts');await page.getByRole('tab',{name:'Fichas',exact:false}).click();
  await page.getByText('Rapid plan',{exact:true}).click();
  for(let i=0;i<3;i++)await page.getByRole('checkbox',{name:'Marcar Exercise '+i,exact:true}).click();
  await waitFor(()=>posts.length===1);
  assert.equal(await page.getByRole('checkbox',{checked:true}).count(),3);
  checks[0]=true;await fulfill(posts[0],{exercises_status:{...checks},completed:false});await waitFor(()=>posts.length===2);
  await fulfill(posts[1],{detail:'Synthetic conflict'},409);await waitFor(()=>posts.length===3);
  checks[2]=true;await fulfill(posts[2],{exercises_status:{...checks},completed:false});
  await page.waitForTimeout(250);
  assert.equal(await page.getByRole('checkbox',{checked:true}).count(),2);
  assert.deepEqual(posts.map(r=>Number(new URL(r.request().url()).pathname.split('/').at(-1))),[0,1,2]);
  assert.equal(new Set(posts.map(r=>r.request().headers()['idempotency-key'])).size,3);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
  assert.deepEqual(errors,[]);
  fs.mkdirSync('test-results',{recursive:true});await page.screenshot({path:`test-results/operational-${width}.png`});
  console.log(JSON.stringify({width,hydration:true,taskScheduling:true,progress:true,serialToggles:true,overflow:false}));
  await context.close();
 }}finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exitCode=1;server.close();});
