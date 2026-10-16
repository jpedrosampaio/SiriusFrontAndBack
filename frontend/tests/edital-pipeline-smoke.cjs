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
          state.status='awaiting_review';state.phase='review';state.inventory.status='awaiting_review';state.scopes['role-a'].status='awaiting_review';state.scopes['role-a'].program=program();
          data.progress=[{kind:'inventory',status:'completed',units:3},{kind:'detail',status:'completed',units:2},{kind:'verify',status:'completed',units:5}];
          data.diagnostics=[{unit_id:'unit-a',kind:'detail',status:'completed',provider_calls:1,last_observed_model:{provider:'mock',model:'synthetic-only'},last_completed_model:{provider:'mock',model:'synthetic-only'}}];
        }else if(action==='facts'){
          if(!staleFact){staleFact=true;data.revision++;return respond(route,{detail:{code:'stale_revision',message:'A análise mudou em outra aba. Atualize antes de salvar.'}},409);}
          state.scopes['role-a'].program.disciplines[0].name={...fact(body.value),state:'corrected_by_user',origin:'human_declared',human_note:body.note,verification:'confirmed'};
        }else if(action==='confirm'){assert.equal(body.acknowledge_document_limits,true);state.status=state.scopes['role-a'].status='completed';state.phase='result';state.scopes['role-a'].confirmed_digest='a'.repeat(64);}
        else if(action==='import'){imported=body;return respond(route,{success:true,program:{program_id:'created-v6',name:'Programa conferido'},message:'Programa conferido criado.'});}
        else throw Error('Unhandled action '+action);
        data.revision++;const result={analysis_id:data.analysis_id,revision:data.revision,status:state.status};receipts.set(key,result);
        if(action==='resume'&&!resumeLost){resumeLost=true;return route.abort('failed');}return respond(route,result);
      }
      if(p==='/api/study/programs/created-v6/cronograma')return respond(route,{program:{name:'Programa conferido'},cronograma:[],disciplinas:[]});
      if(p==='/api/study/programs/created-v6/edital-verticalizado')return respond(route,{program_name:'Programa conferido',disciplinas:[],concurso:{nome:'Concurso conferido'}});
      if(p.endsWith('/state'))return respond(route,{target:{name:'Programa conferido'},coverage:{total:0,studied:0},domains:[],candidates:[],priorities:[],notices:[],warnings:[],syllabus_graph:{disciplines:[],topics:[]},readiness:{components:[]},recent_evidence:[],upcoming:[]});
      if(p==='/api/agent/preferences')return respond(route,{enabled:false});
      if(p.includes('stats')||p.includes('streak')||p==='/api/study/v2/today')return respond(route,{});
      return respond(route,[]);
    });
    const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));await page.goto('http://127.0.0.1:4193/studies');
    await page.getByRole('button',{name:'Preparações',exact:true}).click();await page.getByRole('button',{name:'Editais analisados',exact:true}).click();await page.getByRole('button',{name:'Analisar novo edital',exact:true}).click();
    const dialog=page.getByRole('dialog');await dialog.getByLabel('PDF do Edital',{exact:true}).setInputFiles({name:'synthetic.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF-synthetic-only')});
    await page.getByTestId('analyze-edital-btn').click();await dialog.getByRole('alert').waitFor();assert.equal(legacyPosts,0);
    await page.getByTestId('analyze-edital-btn').click();await page.getByRole('heading',{name:'Conferir meu edital',exact:true}).waitFor();assert.equal(uploadKeys.length,2);assert.equal(uploadKeys[0],uploadKeys[1]);
    const create=page.getByRole('button',{name:'Criar programa com conteúdo confirmado',exact:true});assert.equal(await create.isDisabled(),true);
    await page.getByRole('button',{name:'Abrir análise deste cargo',exact:true}).click();await page.getByRole('button',{name:'Cancelar processamento',exact:true}).click();
    await page.getByRole('heading',{name:'Cancelado · checkpoints preservados',exact:true}).waitFor();await page.reload();await page.getByRole('heading',{name:'Cancelado · checkpoints preservados',exact:true}).waitFor();
    await page.getByRole('button',{name:'Retomar lotes pendentes',exact:true}).click();await page.getByRole('alert').waitFor();
    await page.getByRole('button',{name:'Retomar lotes pendentes',exact:true}).click();await page.getByRole('heading',{name:'Aguardando sua conferência',exact:true}).waitFor();assert.equal(resumeKeys.length,2);assert.equal(resumeKeys[0],resumeKeys[1]);
    await page.getByRole('button',{name:'Corrigir Disciplina',exact:true}).click();await page.getByLabel('Valor de Disciplina',{exact:true}).fill('Língua Portuguesa');
    await page.getByLabel('Origem e justificativa da correção',{exact:true}).fill('Nome conferido manualmente no edital.');await page.getByRole('button',{name:'Salvar correção',exact:true}).click();
    await page.getByRole('alert').getByText('A análise mudou em outra aba. Atualize antes de salvar.',{exact:true}).waitFor();assert.equal(writes.filter(w=>w.action==='facts').length,1);
    await page.getByRole('button',{name:'Cancelar correção',exact:true}).click();await page.getByRole('button',{name:'Corrigir Disciplina',exact:true}).click();await page.getByLabel('Valor de Disciplina',{exact:true}).fill('Língua Portuguesa');await page.getByLabel('Origem e justificativa da correção',{exact:true}).fill('Nome novamente conferido no edital.');await page.getByRole('button',{name:'Salvar correção',exact:true}).click();
    await page.getByText('Língua Portuguesa',{exact:true}).first().waitFor();assert.equal(await create.isDisabled(),true);
    await page.getByText('Evidências e alternativas',{exact:true}).first().click();await page.getByRole('button',{name:'Consultar página 1',exact:true}).first().click();
    await page.getByRole('dialog').getByRole('heading',{name:'Página 1 · texto extraído',exact:true}).waitFor();await page.getByRole('dialog').getByText(citation.quote,{exact:true}).waitFor();await page.getByRole('button',{name:'Fechar página',exact:true}).click();assert.equal(sourceReads,1);
    await page.getByLabel('Registro da conferência final',{exact:true}).fill('Conferi o cargo, os conteúdos, as fontes e as limitações.');await page.getByRole('checkbox',{name:/Conferi o cargo, as associações/}).check();
    await page.getByRole('button',{name:'Confirmar cargo e conteúdo conferidos',exact:true}).click();await page.getByRole('heading',{name:'Cargo confirmado por você',exact:true}).waitFor();
    await page.getByLabel('Área de estudos',{exact:true}).selectOption('area-a');await page.getByLabel('Meta pessoal de estudo (opcional)',{exact:true}).fill('2027-03-01');assert.equal(await create.isEnabled(),true);
    await page.getByText('Diagnóstico seguro e histórico',{exact:true}).click();await page.getByRole('button',{name:'Consultar histórico de revisões',exact:true}).click();await page.getByText(/Correção de informação/).waitFor();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);fs.mkdirSync('test-results/edital-pipeline',{recursive:true});await page.screenshot({path:`test-results/edital-pipeline/review-${width}.png`,fullPage:true});
    await create.click();await page.getByRole('heading',{name:'Programa conferido',exact:true}).first().waitFor();assert.equal(imported.role_id,'role-a');assert.equal(imported.target_date,'2027-03-01');assert.equal(imported.confirmed_digest,'a'.repeat(64));assert.equal(legacyPosts,0);
    assert.deepEqual(errors,[]);console.log(JSON.stringify({width,uploadReplay:true,resumeReplay:true,staleWriteRejected:true,sourceReads,confirmed:true,legacyPosts,overflow:false}));await context.close();
  }}finally{await browser.close();server.close();}
})().catch(error=>{console.error(error);process.exitCode=1;server.close();});
