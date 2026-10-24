const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../src/lib/edital-diagnostics.js'),'utf8').replace(/export /g,'');
function helpers(){const context=vm.createContext({});vm.runInContext(source,context);return context;}

test('copied diagnostics exclude private text and arbitrary provider fields',()=>{
  const c=helpers(),privateText='PRIVATE-PDF-PROMPT-KEY';
  const item={reference:'0434ab82-659a-4f94-be93-cd88fc3ff0a0',kind:'inventory',provider_calls:7,
    error_message:privateText,last_observed_model:{provider:'gemini',model:'gemini-3.8-flash'},
    failure:{http_status:400,request_format:'gemini_response_format',schema_bytes:2315,schema_sha256:'a'.repeat(64),
      provider_rejection:{status:'INVALID_ARGUMENT',category:'unspecified',fields:['store',privateText],message:privateText}}};
  const result=JSON.parse(JSON.stringify(c.publicDiagnostic(item)));
  assert.equal(result.provider_status,'INVALID_ARGUMENT');assert.equal(result.category,'unspecified');
  assert.deepEqual(result.fields,['store']);assert.equal(result.unit_reserved_calls,7);
  assert.equal(result.reference,item.reference);assert.equal(JSON.stringify(result).includes(privateText),false);
  const untrusted=c.publicDiagnostic({reference:privateText,kind:privateText,last_observed_model:{provider:privateText,model:privateText},
    failure:{http_status:privateText,schema_sha256:privateText,provider_rejection:{status:privateText,category:privateText,fields:privateText}}});
  assert.equal(JSON.stringify(untrusted).includes(privateText),false);
});
test('generic or legacy failures never invent provider details or rejected fields',()=>{
  const c=helpers();for(const failure of [null,{}, {provider_rejection:{code:400,status:'INVALID_ARGUMENT',category:'unspecified',fields:[]}}]){
    const result=c.publicDiagnostic({failure});assert.equal(result.fields.length,0);assert.equal(result.model,undefined);
  }
});

test('Groq public failure codes and schema fingerprints survive copy without private error bodies',()=>{
  const c=helpers(),privateText='PRIVATE-PDF-PROMPT-KEY';
  const failure={http_status:400,request_format:'groq_json_schema',schema_bytes:2315,schema_sha256:'a'.repeat(64),
    provider_rejection:{provider_code:'json_validate_failed',provider_type:'invalid_request_error',category:'output_validation',
      fields:['response_format.json_schema.schema',privateText],failed_generation:privateText,message:privateText}};
  const result=JSON.parse(JSON.stringify(c.publicDiagnostic({failure})));
  assert.equal(result.provider_code,'json_validate_failed');assert.equal(result.category,'output_validation');
  assert.equal(result.request_format,'groq_json_schema');assert.equal(result.schema_sha256,'a'.repeat(64));
  assert.equal(JSON.stringify(result).includes(privateText),false);
  assert.equal(c.publicDiagnostic({failure:{provider_rejection:{provider_code:privateText,provider_type:privateText}}}).provider_code,undefined);
});
test('stage counts use active checkpoints only and exclude replaced split parents',()=>{
  const c=helpers(),rows=[{kind:'inventory',status:'split',units:1},{kind:'inventory',status:'completed',units:2},
    {kind:'inventory',status:'pending',units:65},{kind:'verify',status:'completed',units:4}];
  assert.deepEqual(JSON.parse(JSON.stringify(c.stageProgress(rows,'inventory'))),{total:67,done:2,pending:65});
  assert.deepEqual(JSON.parse(JSON.stringify(c.stageProgress(undefined,'detail'))),{total:0,done:0,pending:0});
});

test('strict Groq wire mode survives safe diagnostic copying without accepting arbitrary modes',()=>{
  const c=helpers();
  assert.equal(c.publicDiagnostic({failure:{request_format:'groq_json_schema_strict'}}).request_format,'groq_json_schema_strict');
  assert.equal(c.publicDiagnostic({failure:{request_format:'PRIVATE-PROMPT'}}).request_format,undefined);
});

test('local validation copy includes finite stage and canonical field but no private output or dynamic keys',()=>{
  const c=helpers(),privateText='PRIVATE-PDF-PROMPT-KEY';
  const response_validation={stage:'pydantic',code:'value_error',path:'$.roles[].name',rule:'fact_missing_inconsistent',input:privateText,message:privateText,ctx:{error:privateText}};
  const result=JSON.parse(JSON.stringify(c.publicDiagnostic({failure:{response_validation}})));
  assert.deepEqual(result.response_validation,{stage:'pydantic',code:'value_error',path:'$.roles[].name',rule:'fact_missing_inconsistent'});
  assert.equal(JSON.stringify(result).includes(privateText),false);
  for(const bad of [null,[],{stage:'__proto__',code:'value_error'},{stage:{},code:[]},{stage:'pydantic',code:privateText}])assert.equal(c.publicValidation(bad),null);
  for(const path of ['$.roles[].'+privateText,'$.roles[123].name','$.roles.'+'name.'.repeat(100),'$.__proto__']){
    const sanitized=c.publicValidation({...response_validation,path,rule:privateText});
    assert.equal(sanitized.path,'$');assert.equal(sanitized.rule,undefined);
  }
});
