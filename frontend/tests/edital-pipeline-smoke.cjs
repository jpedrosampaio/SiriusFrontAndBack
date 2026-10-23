// Synthetic HTTP contracts only. No provider, production writes or private PDF.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require('playwright'),root=path.join(process.cwd(),'build');
const server=http.createServer((req,res)=>{let file=path.join(root,new URL(req.url,'http://localhost').pathname);
  if(!file.startsWith(root+path.sep)){res.writeHead(403);return res.end();}
  if(!fs.existsSync(file)||fs.statSync(file).isDirectory())file=path.join(root,'index.html');
  res.setHeader('Content-Type',({'.js':'application/javascript','.css':'text/css','.html':'text/html'})[path.extname(file)]||'application/octet-stream');fs.createReadStream(file).pipe(res);});
const respond=(route,data,status=200,headers={})=>route.fulfill({status,contentType:'application/json',headers,body:JSON.stringify(data)});
const citation={page:1,block_id:'p0001-b0002',quote:'Português: redação oficial.'};
const fact=value=>({value,state:value===null?'missing':'extracted',sources:value===null?[]:[citation],verification:'awaiting_review',alternatives:[],origin:'document'});
function fixture(){return {analysis_id:'analysis-v6',user_id:'fixture',filename:'edital-sintetico.pdf',revision:1,pipeline:'edital/universal/6',worker_configured:true,
  manifest:{version:'edital/universal/6',status:'processing',phase:'inventory',selected_role_id:null,
    source:{pages:4,ocr_required_pages:[],original_available:false},budget:{reserved_attempts:2,provider_limit:120,reported_usage:{total_tokens:120},usage_incomplete:true},
    inventory:{status:'processing',roles:[{id:'role-a',name:fact('Analista'),code:fact('A'),vacancies:fact(null),salary:fact(null),requirements:fact('Graduação')}],facts:[],findings:{},finding_resolutions:{},issue_resolutions:{}},scopes:{}},
  progress:[{kind:'inventory',status:'completed',units:1},{kind:'inventory',status:'pending',units:2}],diagnostics:[],
  review:{sections:[{key:'section-a',block_id:'p0001-b0002',kind:'program',title:fact('Português')}],inventory_issues:[],program_issues:[]}};}
const program=()=>({disciplines:[{id:'discipline-a',name:fact('Português'),stage:fact('Objetiva'),group:fact('Comuns'),
  topics:[{id:'topic-a',title:fact('redação oficial'),parent_id:null,numbering:'1'}]}],rules:[{id:'rule-group',target_scope:'group',kind:'question_count',target:fact('Comuns'),fact:fact('40')}],issues:[]});
(async()=>{await new Promise(resolve=>server.listen(4193,'127.0.0.1',resolve));const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
  try{for(const width of [320,390,768,1024,1440]){
    const context=await browser.newContext({viewport:{width,height:900},serviceWorkers:'block'});await context.addInitScript(()=>localStorage.setItem('sirius_onboarding_complete','true'));
    let data=fixture(),uploadLost=false,resumeLost=false,staleFact=false,sourceReads=0,legacyPosts=0,imported=null;
    const uploadKeys=[],resumeKeys=[],writes=[],receipts=new Map(),errors=[];
    await context.route('**/*',async route=>{const url=new URL(route.request().url()),p=url.pathname,method=route.request().method();
      if(!p.startsWith('/api/'))return url.hostname==='127.0.0.1'?route.continue():route.abort();
      if(p==='/api/auth/me')return respond(route,{user_id:'fixture',name:'User',rank:'Recruta'});
      if(p==='/api/study/areas')return respond(route,[{area_id:'area-a',name:'Concursos'}]);
      if(p==='/api/study/edital-jobs')return respond(route,{jobs:[],upload_available:false,incremental_available:true});
      if(p==='/api/study/edital-pipeline'&&method==='POST'){
        uploadKeys.push(route.request().headers()['idempotency-key']);if(!uploadLost){uploadLost=true;return route.abort('failed');}
        return respond(route,{analysis_id:data.analysis_id,job_id:'job-a',status:data.manifest.status},202);
      }
      if(p==='/api/study/programs/analyze-edital'||p==='/api/study/programs/import-edital-with-cargo'){legacyPosts++;return respond(route,{detail:'Unexpected legacy call'},500);}
      if(p==='/api/study/programs/editais/analysis-v6')return respond(route,{analysis_id:data.analysis_id,pipeline:data.pipeline,analysis_version:6});
      if(p==='/api/study/programs/editais')return respond(route,{editais:[{analysis_id:data.analysis_id,pipeline:data.pipeline,analysis_version:6,pipeline_status:data.manifest.status,pdf_filename:data.filename,num_cargos:1}]});
      const base='/api/study/edital-pipeline/analysis-v6';
      if(p===base&&method==='GET'){
        const etag=`"analysis-${data.revision}"`;if(route.request().headers()['if-none-match']===etag)return route.fulfill({status:304,headers:{ETag:etag}});
        return respond(route,data,200,{ETag:etag});
      }
      if(p===base+'/source/1'){sourceReads++;return respond(route,{page:1,original_available:false,blocks:[{id:'p0001-b0001',text:'Cargo A: Analista.'},{id:citation.block_id,text:citation.quote}],quality:'text'});}
      if(p===base+'/history')return respond(route,{history:[{id:'audit-1',at:'2026-10-16T10:00:00Z',action:'correct_fact',before:{value:'Português'},after:{value:'Língua Portuguesa'}}],has_more:false});
      if(p===base+'/import-candidates')return respond(route,{programs:[{program_id:'preserved-v5',name:'Programa preservado da primeira análise',archived:false}],next_offset:null});
      if(p.startsWith(base+'/')&&method==='POST'){
        const action=p.slice(base.length+1),body=route.request().postDataJSON(),key=route.request().headers()['idempotency-key'];
        writes.push({action,body,key});assert.match(key,/^[a-f0-9-]{36}$/);
        if(action==='resume')resumeKeys.push(key);
        if(receipts.has(key))return respond(route,{...receipts.get(key),replayed:true});
        if(body.revision!==data.revision)return respond(route,{detail:{code:'stale_revision',message:'A análise mudou em outra aba. Atualize antes de salvar.'}},409);
        const state=data.manifest;
        if(action==='select-role'){state.selected_role_id=body.role_id;state.phase='program';state.scopes[body.role_id]={status:'processing',program:{disciplines:[],rules:[]},bindings:{},binding_corrections:{},findings:{},finding_resolutions:{},issue_resolutions:{}};}
        else if(action==='cancel'){state.status='cancelled';state.scopes['role-a'].status='cancelled';}
        else if(action==='resume'){
          if(body.mode){
            assert.ok(data.execution_plan);assert.equal(state.status,'waiting_provider');
            if(body.diagnostic_case){
              assert.equal(body.mode,'pilot');assert.ok(['text','json','inventory'].includes(body.diagnostic_case));assert.equal(body.provider_limit,undefined);
              state.budget.reserved_attempts++;state.error_kind='provider_probe_accepted';
              state.provider_approval={mode:'paused',diagnostic_case:body.diagnostic_case,pilot_validated:false};
              data.execution_plan.minimum_total_attempts++;
              data.diagnostics[0].provider_probes=[...(data.diagnostics[0].provider_probes||[]),{case:body.diagnostic_case,outcome:'accepted'}];
            }else if(body.mode==='pilot'){
              assert.equal(body.provider_limit,undefined);state.budget.reserved_attempts++;state.error_kind='pilot_review_required';
              data.execution_plan.live_provider_validated=true;data.execution_plan.minimum_remaining_attempts--;data.execution_plan.stages.inventory--;
              data.execution_plan.diagnostic_cases=[];state.provider_approval={mode:'paused',diagnostic_case:null,pilot_validated:true};
              data.progress=[{kind:'inventory',status:'completed',units:1},{kind:'inventory',status:'pending',units:66}];
            }else{
              assert.equal(body.mode,'full');assert.equal(data.execution_plan.live_provider_validated,true);
              assert.equal(body.provider_limit,147);state.budget.provider_limit=body.provider_limit;state.status='processing';state.error_kind=null;
            }
          }else{
          state.status='awaiting_review';state.phase='review';state.inventory.status='awaiting_review';state.scopes['role-a'].status='awaiting_review';state.scopes['role-a'].program=program();
          data.progress=[{kind:'inventory',status:'completed',units:3},{kind:'detail',status:'completed',units:2},{kind:'verify',status:'completed',units:5}];
          data.diagnostics=[{unit_id:'unit-a',kind:'detail',status:'completed',provider_calls:1,last_observed_model:{provider:'mock',model:'synthetic-only'},last_completed_model:{provider:'mock',model:'synthetic-only'}}];
          }
        }else if(action==='facts'){
          if(!staleFact){staleFact=true;data.revision++;return respond(route,{detail:{code:'stale_revision',message:'A análise mudou em outra aba. Atualize antes de salvar.'}},409);}
          state.scopes['role-a'].program.disciplines[0].name={...fact(body.value),state:'corrected_by_user',origin:'human_declared',human_note:body.note,verification:'confirmed'};
        }else if(action==='resolve'){assert.equal(body.identity,'orphaned-correction');state.scopes['role-a'].issue_resolutions[body.identity]={value:'reviewed',note:body.note};}
        else if(action==='confirm'){assert.equal(body.acknowledge_document_limits,true);assert.ok(state.scopes['role-a'].issue_resolutions['orphaned-correction']);state.status=state.scopes['role-a'].status='completed';state.phase='result';state.scopes['role-a'].confirmed_digest='a'.repeat(64);}
        else if(action==='import'){imported=body;return respond(route,{success:true,program:{program_id:'created-v6',name:'Programa conferido'},message:'Programa conferido criado.'});}
        else throw Error('Unhandled action '+action);
        data.revision++;const result={analysis_id:data.analysis_id,revision:data.revision,status:state.status};receipts.set(key,result);
        if(action==='resume'&&!resumeLost){resumeLost=true;return route.abort('failed');}return respond(route,result);
      }
      if(p==='/api/study/programs/created-v6/cronograma')return respond(route,{program:{name:'Programa conferido'},cronograma:[],disciplinas:[]});
      if(p==='/api/study/programs/created-v6/edital-verticalizado')return respond(route,{program_name:'Programa conferido',disciplinas:[],concurso:{nome:'Concurso conferido'}});
      if(p==='/api/study/programs/preserved-v5/cronograma')return respond(route,{program:{name:'Programa preservado da primeira análise'},cronograma:[],disciplinas:[]});
      if(p==='/api/study/programs/preserved-v5/edital-verticalizado')return respond(route,{program_name:'Programa preservado da primeira análise',disciplinas:[],concurso:{nome:'Concurso anterior'}});
      if(p.endsWith('/state'))return respond(route,{target:{name:'Programa conferido'},coverage:{total:0,studied:0},domains:[],candidates:[],priorities:[],notices:[],warnings:[],syllabus_graph:{disciplines:[],topics:[]},readiness:{components:[]},recent_evidence:[],upcoming:[]});
      if(p==='/api/agent/preferences')return respond(route,{enabled:false});
      if(p.includes('stats')||p.includes('streak')||p==='/api/study/v2/today')return respond(route,{});
      return respond(route,[]);
    });
    const page=await context.newPage();await page.addInitScript(()=>{window.__safeDiagnosticCopy=null;Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async text=>{window.__safeDiagnosticCopy=text;}}});});page.on('pageerror',error=>errors.push(error.message));await page.goto('http://127.0.0.1:4193/studies');
    await page.getByRole('button',{name:'Preparações',exact:true}).click();await page.getByRole('button',{name:'Editais analisados',exact:true}).click();await page.getByRole('button',{name:'Analisar novo edital',exact:true}).click();
    const dialog=page.getByRole('dialog');await dialog.getByLabel('PDF do Edital',{exact:true}).setInputFiles({name:'synthetic.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF-synthetic-only')});
    await page.getByTestId('analyze-edital-btn').click();await dialog.getByRole('alert').waitFor();assert.equal(legacyPosts,0);
    await page.getByTestId('analyze-edital-btn').click();await page.getByRole('heading',{name:'Conferir meu edital',exact:true}).waitFor();assert.equal(uploadKeys.length,2);assert.equal(uploadKeys[0],uploadKeys[1]);
    await page.getByText('Criar programa no meu planejamento',{exact:true}).click();
    const create=page.getByRole('button',{name:'Criar programa com conteúdo confirmado',exact:true});assert.equal(await create.isDisabled(),true);
    await page.getByText('Criar programa no meu planejamento',{exact:true}).click();
    await page.getByRole('button',{name:'Abrir análise deste cargo',exact:true}).click();await page.getByRole('button',{name:'Cancelar processamento',exact:true}).click();
    await page.getByRole('heading',{name:'Cancelado · checkpoints preservados',exact:true}).waitFor();await page.reload();await page.getByRole('heading',{name:'Cancelado · checkpoints preservados',exact:true}).waitFor();
    await page.getByRole('button',{name:'Retomar lotes pendentes',exact:true}).click();await page.getByRole('alert').waitFor();
    await page.getByRole('button',{name:'Retomar lotes pendentes',exact:true}).click();await page.getByRole('heading',{name:'Aguardando sua conferência',exact:true}).waitFor();assert.equal(resumeKeys.length,2);assert.equal(resumeKeys[0],resumeKeys[1]);
    await page.getByRole('button',{name:'Corrigir Disciplina',exact:true}).click();await page.getByLabel('Valor de Disciplina',{exact:true}).fill('Língua Portuguesa');
    await page.getByLabel('Origem e justificativa da correção',{exact:true}).fill('Nome conferido manualmente no edital.');await page.getByRole('button',{name:'Salvar correção',exact:true}).click();
    await page.getByRole('alert').getByText('A análise mudou em outra aba. Atualize antes de salvar.',{exact:true}).waitFor();assert.equal(writes.filter(w=>w.action==='facts').length,1);
    await page.getByRole('button',{name:'Cancelar correção',exact:true}).click();await page.getByRole('button',{name:'Corrigir Disciplina',exact:true}).click();await page.getByLabel('Valor de Disciplina',{exact:true}).fill('Língua Portuguesa');await page.getByLabel('Origem e justificativa da correção',{exact:true}).fill('Nome novamente conferido no edital.');await page.getByRole('button',{name:'Salvar correção',exact:true}).click();
    await page.locator('p').filter({hasText:/^Língua Portuguesa$/}).waitFor();assert.equal(await create.isDisabled(),true);
    await page.getByText('Evidências e alternativas',{exact:true}).first().click();await page.getByRole('button',{name:'Consultar página 1',exact:true}).first().click();
    await page.getByRole('dialog').getByRole('heading',{name:'Página 1 · texto extraído',exact:true}).waitFor();await page.getByRole('dialog').getByText(citation.quote,{exact:true}).waitFor();await page.getByRole('button',{name:'Fechar página',exact:true}).click();assert.equal(sourceReads,1);
    data.manifest.scopes['role-a'].unapplied_corrections=['disciplines/old/name'];data.manifest.scopes['role-a'].corrections={'disciplines/old/name':{value:'Correção humana anterior',note:'Valor preservado da revisão anterior.'}};
    data.review.program_issues=[{id:'orphaned-correction',message:'Uma correção anterior exige associação explícita.'}];data.revision++;
    await page.getByRole('button',{name:'Atualizar andamento',exact:true}).click();await page.getByText(/Correção preservada: Correção humana anterior/).waitFor();
    await page.getByLabel('Registro da conferência final',{exact:true}).fill('Conferi o cargo, os conteúdos, as fontes e as limitações.');await page.getByRole('checkbox',{name:/Conferi o cargo, as associações/}).check();
    assert.equal(await page.getByRole('button',{name:'Confirmar cargo e conteúdo conferidos',exact:true}).isDisabled(),true);
    await page.getByLabel('Como você conferiu esta pendência?',{exact:true}).fill('Transferi a correção conferida para a disciplina atual.');await page.getByRole('button',{name:'Registrar conferência',exact:true}).click();
    await page.getByRole('button',{name:'Confirmar cargo e conteúdo conferidos',exact:true}).click();await page.getByRole('heading',{name:'Cargo confirmado por você',exact:true}).waitFor();
    await page.getByLabel('Área de estudos',{exact:true}).selectOption('area-a');await page.getByLabel('Meta pessoal de estudo (opcional)',{exact:true}).fill('2027-03-01');assert.equal(await create.isEnabled(),true);
    await page.getByText('Diagnóstico seguro e histórico',{exact:true}).click();await page.getByRole('button',{name:'Consultar histórico de revisões',exact:true}).click();await page.getByText(/Correção de informação/).waitFor();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);fs.mkdirSync('test-results/edital-pipeline',{recursive:true});await page.screenshot({path:`test-results/edital-pipeline/review-${width}.png`,fullPage:true});
    await page.getByRole('button',{name:'Ver programas já criados deste PDF',exact:true}).click();await page.getByText('Programa preservado da primeira análise',{exact:true}).waitFor();
    await page.getByRole('button',{name:'Abrir programa anterior',exact:true}).click();await page.getByRole('heading',{name:'Programa preservado da primeira análise',exact:true}).first().waitFor();assert.equal(imported,null);
    await page.goBack();await page.getByRole('heading',{name:'Cargo confirmado por você',exact:true}).waitFor();await page.getByLabel('Área de estudos',{exact:true}).selectOption('area-a');
    await page.getByRole('checkbox',{name:/Conferi os programas já criados deste PDF/}).check();
    await create.click();await page.getByRole('heading',{name:'Programa conferido',exact:true}).first().waitFor();assert.equal(imported.role_id,'role-a');assert.equal(imported.target_date,'2027-03-01');assert.equal(imported.confirmed_digest,'a'.repeat(64));assert.equal(imported.create_new_version,true);assert.equal(legacyPosts,0);
    data=fixture();data.revision=100;data.manifest.status='waiting_provider';data.manifest.error_kind='invalid_request';data.manifest.inventory.roles=[];
    data.filename='EDITAL_2026_ABERTURA_CONCURSO_PUBLICO_DOCUMENTO_COMPLETO_70_PAGINAS.pdf';
    data.manifest.source.pages=70;data.manifest.budget.reserved_attempts=10;
    data.execution_plan={stages:{inventory:67,scope:0,detail:0,verify:67},minimum_remaining_attempts:134,minimum_total_attempts:144,
      maximum_limit:200,extension_required:true,unknown_stages:['selected_role_content'],live_provider_validated:false,diagnostic_cases:['text','json','inventory']};
    data.progress=[{kind:'inventory',status:'pending',units:67}];
    data.diagnostics=[{unit_id:'blocked-unit',kind:'inventory',status:'waiting_provider',provider_calls:8,error_kind:'invalid_request',reference:'8e6cb78f-73cb-4336-a6d6-49196f4e0a82',
      last_observed_model:{provider:'gemini',model:'gemini-3.8-flash'},
      failure:{http_status:400,incompatibility:'request_rejected',provider_attempted:true,request_format:'gemini_response_format',schema_bytes:2315,schema_sha256:'a'.repeat(64),
        provider_rejection:{code:400,status:'INVALID_ARGUMENT',category:'unspecified',fields:[],message:'PRIVATE-MOCK-PROMPT'}}}];
    await page.goBack();await page.getByRole('heading',{name:'Aguardando correção/configuração da IA',exact:true}).waitFor();
    await page.getByText('0 de 67 lotes concluídos · 67 pendentes',{exact:true}).waitFor();
    const diagnosis=page.getByRole('region',{name:'Diagnóstico do provedor'}).first();
    await diagnosis.getByRole('heading',{name:'A IA recusou a solicitação',exact:true}).waitFor();
    await diagnosis.getByText('Ver detalhes técnicos',{exact:true}).click();
    await diagnosis.getByText('Ainda não identificado no diagnóstico seguro',{exact:true}).waitFor();
    const writesBeforeCopy=writes.length;await diagnosis.getByRole('button',{name:'Copiar diagnóstico seguro',exact:true}).click();
    await diagnosis.getByText('Diagnóstico copiado.',{exact:true}).waitFor();
    const copied=JSON.parse(await page.evaluate(()=>window.__safeDiagnosticCopy));
    assert.equal(copied.provider_status,'INVALID_ARGUMENT');assert.equal(copied.unit_reserved_calls,8);assert.equal(copied.schema_bytes,2315);
    assert.equal(JSON.stringify(copied).includes('PRIVATE-MOCK-PROMPT'),false);assert.equal(writes.length,writesBeforeCopy);
    await diagnosis.getByText('Ver detalhes técnicos',{exact:true}).click();
    await page.getByRole('navigation',{name:'Navegação da análise'}).getByRole('link',{name:'Cargos e informações',exact:true}).click();
    await page.getByText('Os cargos aparecerão aqui após a descoberta validada.',{exact:true}).waitFor();
    await page.evaluate(()=>window.scrollTo({top:0,left:0,behavior:'instant'}));
    assert.equal(await page.getByRole('button',{name:'Executar lote piloto (1 chamada)',exact:true}).isVisible(),false);
    const nextAction=page.getByTestId('edital-next-action');await nextAction.waitFor();
    const position=await nextAction.boundingBox();assert(position&&position.y>=0&&position.y+position.height<815,`Primary action is below the first viewport: ${JSON.stringify({width,position})}`);
    if(process.env.SIRIUS_VISUAL_DIR){
      await page.getByText('Programa conferido criado.',{exact:true}).waitFor({state:'hidden'});await page.mouse.move(0,0);
      console.log('EDITAL_VISUAL '+JSON.stringify({width,layout:await page.evaluate(()=>{
        const bounds=selector=>{const el=document.querySelector(selector);return el?{left:el.getBoundingClientRect().left,width:el.getBoundingClientRect().width,padding:getComputedStyle(el).padding,font:getComputedStyle(el).fontFamily}:null;};
        return {main:bounds('.edital-workspace'),header:bounds('.edital-workspace header'),shell:bounds('.sirius-shell-body'),heading:bounds('.edital-workspace h2'),scrollers:[...document.querySelectorAll('*')].filter(el=>el.scrollLeft>0).map(el=>({tag:el.tagName,id:el.id,left:el.scrollLeft}))};
      })}));
      await page.screenshot({path:path.join(process.env.SIRIUS_VISUAL_DIR,`edital-overview-${width}.png`),fullPage:true});await page.screenshot({path:path.join(process.env.SIRIUS_VISUAL_DIR,`edital-viewport-${width}.png`)});
    }
    for(const [kind,label] of [['text','Testar IA sem PDF (1 chamada)'],['json','Testar JSON mínimo (1 chamada)'],['inventory','Testar contrato sem PDF (1 chamada)']]){
      if(kind==='inventory'){
        await page.getByTestId('edital-next-action').filter({hasText:'Executar lote piloto (1 chamada)'}).waitFor();
        await page.getByText('Outras opções de diagnóstico e teste do edital',{exact:true}).click();
        await page.getByLabel('Tipo de diagnóstico',{exact:true}).selectOption('inventory');
      }
      const button=page.getByRole('button',{name:kind==='inventory'?'Executar diagnóstico (1 chamada, sem PDF)':label,exact:true});await button.waitFor();
      const beforeDiagnostic=writes.length;page.once('dialog',dialog=>dialog.dismiss());
      await button.click();assert.equal(writes.length,beforeDiagnostic);
      page.once('dialog',async dialog=>{assert.match(dialog.message(),/sem texto do PDF/);await dialog.accept();});
      await button.click();
      await page.getByRole('heading',{name:'Diagnóstico técnico aceito · análise pausada',exact:true}).waitFor();
      assert.equal(writes.length,beforeDiagnostic+1);assert.equal(writes.at(-1).body.diagnostic_case,kind);
      assert.equal(data.execution_plan.live_provider_validated,false);assert.equal(data.manifest.inventory.roles.length,0);
      assert.equal(data.manifest.budget.provider_limit,120);
      assert.equal(await page.getByRole('button',{name:'Autorizar e retomar lotes pendentes',exact:true}).count(),0);
      await page.getByText('0 de 67 lotes concluídos · 67 pendentes',{exact:true}).waitFor();
    }
    const before=writes.length;page.once('dialog',dialog=>dialog.dismiss());
    await page.getByRole('button',{name:'Executar lote piloto (1 chamada)',exact:true}).click();assert.equal(writes.length,before);
    page.once('dialog',async dialog=>{assert.match(dialog.message(),/no máximo uma chamada real/);await dialog.accept();});
    await page.getByRole('button',{name:'Executar lote piloto (1 chamada)',exact:true}).click();
    await page.getByRole('heading',{name:'Piloto validado · aguardando sua autorização',exact:true}).waitFor();
    assert.equal(await page.locator('#edital-progress').getByRole('region',{name:'Diagnóstico do provedor'}).count(),0);
    assert.equal(writes.length,before+1);assert.equal(writes.at(-1).body.mode,'pilot');
    await page.getByText('1 de 67 lotes concluídos · 66 pendentes',{exact:true}).waitFor();
    await page.getByLabel('Limite total a autorizar',{exact:true}).fill('146');
    assert.equal(await page.getByRole('button',{name:'Autorizar e retomar lotes pendentes',exact:true}).isDisabled(),true);
    await page.getByLabel('Limite total a autorizar',{exact:true}).fill('147');
    page.once('dialog',async dialog=>{assert.match(dialog.message(),/limite total de 147/);await dialog.accept();});
    await page.getByRole('button',{name:'Autorizar e retomar lotes pendentes',exact:true}).click();
    await page.getByRole('button',{name:'Cancelar processamento',exact:true}).waitFor();
    assert.equal(writes.length,before+2);assert.equal(writes.at(-1).body.provider_limit,147);
    const writesBeforeBlocked=writes.length;
    for(const blocked of ['failed_diagnostic','cooldown','budget']){
      data.manifest.status='waiting_provider';data.manifest.error_kind='invalid_request';
      data.manifest.provider_approval=blocked==='failed_diagnostic'?{mode:'paused',diagnostic_case:'text',pilot_validated:false}:null;
      data.manifest.retry_at=blocked==='cooldown'?new Date(Date.now()+60000).toISOString():null;
      data.manifest.budget.reserved_attempts=blocked==='budget'?120:10;data.manifest.budget.provider_limit=120;
      data.execution_plan.live_provider_validated=false;data.execution_plan.diagnostic_cases=['text','json','inventory'];data.revision++;
      await page.getByRole('button',{name:'Atualizar andamento',exact:true}).click();
      if(blocked==='failed_diagnostic')await page.getByRole('heading',{name:'A IA ainda precisa de correção',exact:true}).waitFor();
      if(blocked==='cooldown')await page.getByRole('status').filter({hasText:'Nova tentativa a partir de'}).waitFor();
      if(blocked==='budget')await page.getByText('120 / 120 tentativas',{exact:true}).waitFor();
      await page.getByRole('button',{name:'Testar IA sem PDF (1 chamada)',exact:true}).waitFor();
      await page.waitForFunction(()=>document.querySelector('[data-testid="edital-next-action"]')?.disabled===true);
      assert.equal(writes.length,writesBeforeBlocked,`A ${blocked} state must not dispatch another request`);
    }
    data.manifest.provider_approval=null;data.manifest.retry_at=null;data.manifest.budget.reserved_attempts=12;
    data.execution_plan.diagnostic_cases=[];data.execution_plan.extraction_route=[{provider:'groq',model:'qwen/qwen3.8-27b'}];
    data.diagnostics=[{unit_id:'blocked-unit',kind:'inventory',status:'waiting_provider',provider_calls:10,
      reference:'3b71513c-c5c1-44ad-babd-b88e18b37b97',last_observed_model:{provider:'groq',model:'openai/gpt-oss-120b'},
      failure:{http_status:400,request_format:'groq_json_schema',schema_bytes:2315,schema_sha256:'a'.repeat(64),
        provider_rejection:{provider_code:'json_validate_failed',provider_type:'invalid_request_error',category:'output_validation',
          fields:[],failed_generation:'PRIVATE-MOCK-GENERATION'}}}];data.revision++;
    await page.getByRole('button',{name:'Atualizar andamento',exact:true}).click();
    const groqDiagnosis=page.getByRole('region',{name:'Diagnóstico do provedor'}).first();
    await groqDiagnosis.getByRole('heading',{name:'A resposta da IA não passou na validação',exact:true}).waitFor();
    await groqDiagnosis.getByText('Ver detalhes técnicos',{exact:true}).click();
    await groqDiagnosis.getByText('json_validate_failed · Resposta gerada fora do contrato',{exact:true}).waitFor();
    await page.getByText(/Rota da próxima tentativa: groq \/ qwen\/qwen3.8-27b/).waitFor();
    assert.equal(await page.getByRole('button',{name:'Testar IA sem PDF (1 chamada)',exact:true}).isVisible(),false);
    assert.equal(await page.getByRole('button',{name:'Executar lote piloto (1 chamada)',exact:true}).isVisible(),true);
    assert.equal(await page.getByText('PRIVATE-MOCK-GENERATION',{exact:false}).count(),0);
    assert.equal(writes.length,writesBeforeBlocked,'Inspecting a Groq generation failure must not resume the analysis');
    if(process.env.SIRIUS_VISUAL_DIR)await page.screenshot({path:require('node:path').join(process.env.SIRIUS_VISUAL_DIR,`edital-groq-${width}.png`)});
    data.execution_plan.extraction_route=[];data.revision++;
    await page.getByRole('button',{name:'Atualizar andamento',exact:true}).click();
    await page.getByText('Configure um modelo compatível para a extração antes de autorizar uma tentativa.',{exact:true}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Executar lote piloto (1 chamada)',exact:true}).isEnabled(),false);
    assert.equal(writes.length,writesBeforeBlocked);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
    assert.deepEqual(errors,[]);console.log(JSON.stringify({width,uploadReplay:true,resumeReplay:true,staleWriteRejected:true,sourceReads,confirmed:true,
      explicitPilot:true,explicitBudgetExtension:true,legacyPosts,overflow:false}));await context.close();
  }}finally{await browser.close();server.close();}
})().catch(error=>{console.error(error);process.exitCode=1;server.close();});
