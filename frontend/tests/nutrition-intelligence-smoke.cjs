// Five real widths. Synthetic routes only; confirmation, retries, provenance and readonly previews.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const root=path.join(process.cwd(),'build');
const server=http.createServer((req,res)=>{
  let file=path.join(root,new URL(req.url,'http://localhost').pathname);
  if(!file.startsWith(root+path.sep)){res.writeHead(403);return res.end();}
  if(!fs.existsSync(file)||fs.statSync(file).isDirectory())file=path.join(root,'index.html');
  res.setHeader('Content-Type',({'.js':'application/javascript','.css':'text/css','.html':'text/html'})[path.extname(file)]||'application/octet-stream');fs.createReadStream(file).pipe(res);
});
(async()=>{
  await new Promise(resolve=>server.listen(4186,'127.0.0.1',resolve));
  const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
  try{for(const width of [1440,1024,768,390,320]){
    const context=await browser.newContext({viewport:{width,height:900},serviceWorkers:'block'});
    await context.addInitScript(()=>localStorage.setItem('sirius_onboarding_complete','true'));
    const errors=[],writes=[],keys=[];let reads=0,previews=0,repeats=0,committed=0,plans=0,lost=true,failPreview=true;
    const macros=Object.fromEntries([['calories',100],['protein',2],['carbs',20],['fat',0]].map(([key,n])=>[key,{registered:'0',estimated:String(n),legacy_unverified:'0',known_total:String(n),total:String(n),unknown_items:0,unit:key==='calories'?'kcal':'g'}]));
    const prefs={favorite_meals:[],available_foods:null,excluded_foods:[],budget:null,budget_period:'weekly',prices:[]};
    const state={date:'2026-10-09',timezone:'America/Sao_Paulo',consumed:{...macros,protein:{...macros.protein,total:null,unknown_items:1}},remaining:{calories:null,protein:null,carbs:null,fat:null},goals:null,water_ml:0,consistency:{recorded_days:1,days:28},meals:[{meal_id:'meal-own',name:'Arroz registrado',meal_type:'lunch',foods:[{}]}],planned:[],training_context:[],routine_context:[],preferences:prefs,limitations:['Dados antigos desconhecidos não justificam metas.'],truncated:false};
    const candidate={template_id:'meal-own',template_kind:'meal',name:'Arroz registrado',meal_type:'lunch',favorite:false,portions:'1',macros,composition_source:'estimated',cost:'2.10',cost_source:'estimated',currency:'BRL',reason:'Fonte própria; porção escolhida pela pessoa.'};
    const imported={name:'Plano a revisar',description:'',objective:'',diet_type:'',start_date:null,end_date:null,source_filename:'fake.pdf',daily_calories:0,daily_protein:0,daily_carbs:0,daily_fat:0,daily_fiber:0,restrictions:[],tips:[],shopping_items:[],days:[{day_name:'dia1',day_label:'Dia 1',calories:100,meals:[{name:'Arroz previsto',meal_type:'lunch',time:'',calories:100,protein:2,carbs:20,fat:0,fiber:0,preparation:'',notes:'',foods:[{name:'Arroz',quantity:'100',unit:'g',calories:100,protein:2,carbs:20,fat:0}]}]}]};
    const fulfill=(route,data,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(data)});
    await context.route('**/*',async route=>{
      const request=route.request(),url=new URL(request.url()),p=url.pathname;
      if(!p.startsWith('/api/'))return url.hostname==='127.0.0.1'?route.continue():route.abort();
      let data=[];
      if(request.method()!=='GET')writes.push(p);
      if(p==='/api/auth/me')data={user_id:'nutrition-user',name:'Nutrition',xp:0,rank:'Recruta',timezone:'America/Sao_Paulo'};
      if(p==='/api/nutrition/goals')data={goal_id:null,configured:false,confirmed_fields:[]};
      if(p==='/api/nutrition/stats')data={consumed:{calories:0,protein:0,carbs:0,fat:0},remaining:{},meals_count:0};
      if(p==='/api/nutrition/water')data={total_ml:0,logs:[]};
      if(p==='/api/nutrition/weekly-trend')data={daily:[],averages:{dias_registrados:0}};
      if(p==='/api/nutrition/intelligence/state'){reads++;data=state;}
      if(p==='/api/nutrition/intelligence/alternatives'){
        previews++;const body=request.postDataJSON();assert.equal(body.portions,'1');assert.equal(body.days,7);
        if(failPreview){failPreview=false;return fulfill(route,{detail:'Prévia temporariamente indisponível'},503);}
        data={candidates:[{...candidate,favorite:prefs.favorite_meals.includes(candidate.template_id)}],organization:[{date:body.date,name:candidate.name,portions:'1',cost:'2.10'}],limitations:['Nenhuma transação financeira ou agendamento criado.'],automatic:false};
      }
      if(p==='/api/nutrition/intelligence/preferences'){
        assert.ok(request.headers()['idempotency-key']);Object.assign(prefs,request.postDataJSON());data=prefs;
      }
      if(p==='/api/nutrition/intelligence/templates/meal/meal-own/record'){
        repeats++;keys.push(request.headers()['idempotency-key']);assert.ok(keys.at(-1));
        if(!committed){committed++;state.meals.push({meal_id:'new-once',name:'Nova refeição confirmada',foods:[{}]});}
        if(lost){lost=false;return fulfill(route,{detail:'Resposta perdida; tente novamente'},504);}
        data={meal_id:'new-once',replayed:true};
      }
      if(p==='/api/nutrition/import-plan'){
        assert.equal(url.searchParams.get('preview'),'true');data={preview:imported,saved:false,requires_confirmation:true};
      }
      if(p==='/api/nutrition/intelligence/confirm-plan'){
        plans++;assert.ok(request.headers()['idempotency-key']);assert.equal(request.postDataJSON().days[0].meals[0].calories,125);assert.equal(request.postDataJSON().days[0].meals[0].foods[0].calories,125);
        data={success:true,plan:{plan_id:'new-plan'},xp_earned:10,meals_created:0};
      }
      await fulfill(route,data);
    });
    const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
    await page.goto('http://127.0.0.1:4186/nutrition');
    await page.getByRole('tab',{name:'Inteligência',exact:true}).click();
    const panel=page.getByRole('region',{name:'Inteligência nutricional'});
    await panel.getByRole('heading',{name:'Seu dia alimentar'}).waitFor();assert.equal(reads,1);
    await panel.getByText(/1 item\(ns\) com dados desconhecidos/).waitFor();
    await panel.getByLabel('Período da organização').selectOption('7');
    await panel.getByRole('button',{name:'Comparar alternativas'}).click();
    await panel.getByRole('alert').getByText('Prévia temporariamente indisponível').waitFor();
    await panel.getByRole('button',{name:'Comparar alternativas'}).click();
    await panel.getByRole('heading',{name:'Arroz registrado'}).waitFor();assert.equal(reads,1);assert.equal(committed,0);
    await panel.getByRole('button',{name:'Favoritar',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('section[aria-label="Inteligência nutricional"]')?.textContent.includes('Seu dia alimentar')&&!document.querySelector('section[aria-label="Inteligência nutricional"]')?.textContent.includes('Favoritar'));
    await panel.getByRole('button',{name:'Comparar alternativas'}).click();
    await panel.getByRole('button',{name:'Remover favorita',exact:true}).waitFor();
    await panel.getByRole('button',{name:'Registrar com confirmação'}).click();
    await panel.getByRole('alert').getByText('Resposta perdida; tente novamente').waitFor();
    await panel.getByRole('button',{name:'Registrar com confirmação'}).click();
    await panel.getByText('Nova refeição confirmada',{exact:false}).waitFor();
    assert.equal(committed,1);assert.equal(repeats,2);assert.equal(new Set(keys).size,1);
    await page.getByRole('tab',{name:'Plano Alimentar',exact:true}).click();
    await page.getByTestId('import-meal-plan-btn').click();
    const dialog=page.getByRole('dialog');
    await page.locator('#import-file-input').setInputFiles({name:'fake.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF synthetic')});
    await page.getByTestId('import-plan-submit-btn').click();
    await dialog.getByText('Revisar estimativas antes de salvar').waitFor();assert.equal(plans,0);
    await dialog.getByLabel('Arroz · Energia (kcal)',{exact:true}).fill('125');
    await dialog.getByRole('button',{name:'Confirmar plano revisado'}).click();
    await dialog.waitFor({state:'hidden'});assert.equal(plans,1);
    assert.equal(writes.filter(p=>p==='/api/nutrition/meals').length,0);
    assert.equal(writes.some(p=>p.startsWith('/api/finance/')||p.startsWith('/api/calendar')),false);
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
    if(overflow){console.error(JSON.stringify({width,elements:await page.evaluate(()=>Array.from(document.querySelectorAll('body *')).filter(e=>e.getBoundingClientRect().right>innerWidth+1).slice(0,12).map(e=>({tag:e.tagName,classes:e.className,right:e.getBoundingClientRect().right,text:e.textContent.slice(0,80)})))}));fs.mkdirSync('test-results',{recursive:true});await page.screenshot({path:`test-results/nutrition-overflow-${width}.png`,fullPage:true});}
    assert.equal(overflow,false);assert.deepEqual(errors,[]);
    fs.mkdirSync('test-results',{recursive:true});await page.screenshot({path:`test-results/nutrition-intelligence-${width}.png`,fullPage:true});
    console.log(JSON.stringify({width,unknowns:true,readonlyPreviews:previews,confirmedMealOnce:true,retrySameKey:true,imagePlanReview:true,overflow:false}));
    await context.close();
  }}finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exitCode=1;server.close();});
