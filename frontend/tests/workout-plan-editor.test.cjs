const { test }=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const c=vm.createContext({});vm.runInContext(fs.readFileSync(path.join(__dirname,'../src/lib/workout-plan-editor.js'),'utf8').replaceAll('export ',''),c);
const plain=value=>JSON.parse(JSON.stringify(value));
test('Editing the last session preserves all weeks, other prescriptions, ranges and duration',()=>{
  const plan={name:'Quatro semanas',plan_duration:'mes',health_condition:'private',days:Array.from({length:20},(_,i)=>({week:Math.floor(i/5)+1,day_name:`sem${Math.floor(i/5)+1}_dia${i%5+1}`,exercises:[{name:'Agachamento',reps:'8-12'},{name:'Flexão',reps:'10'}]}))};
  const before=plain(plan);
  let edited=c.editPlanExercises(plan,19,exercises=>exercises.map((ex,i)=>i?ex:{...ex,name:'Afundo',reps:'10-15'}));
  edited=c.editPlanExercises(edited,19,exercises=>[...exercises,{name:'Mobilidade',reps:'30 s'}]);
  edited=c.editPlanExercises(edited,19,exercises=>exercises.filter((_,i)=>i!==1));
  const payload=plain(c.planEditPayload(edited));
  assert.equal(payload.days.length,20);assert.equal(payload.days[19].week,4);assert.equal(payload.plan_duration,'mes');
  assert.deepEqual(payload.days.slice(0,19),before.days.slice(0,19));assert.deepEqual(payload.days[19].exercises,[{name:'Afundo',reps:'10-15'},{name:'Mobilidade',reps:'30 s'}]);
  assert.deepEqual(plan,before);assert.equal(payload.exercises,undefined);assert.equal(payload.health_condition,undefined);
  assert.equal(c.editableExercises(edited,0)[0].name,'Agachamento');assert.equal(c.editableExercises(edited,19)[0].name,'Afundo');
});
test('Legacy flat exercise editing still creates the existing flat payload',()=>{
  const original={name:'Ficha',plan_duration:'dia',exercises:[{name:'Flexão',reps:'8-12'}]};
  const edited=c.editPlanExercises(original,0,exercises=>[...exercises,{name:'Prancha',reps:'30 s'}]);
  assert.equal(original.exercises.length,1);assert.equal(c.editableExercises(edited,0).length,2);
  const payload=c.planEditPayload(edited);assert.equal(payload.days,undefined);assert.equal(payload.exercises[0].reps,'8-12');assert.equal(payload.plan_duration,'dia');
});
