const { test } = require('node:test'), assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm'), path = require('node:path');
const c = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/lib/workout-generation.js'), 'utf8').replaceAll('export ', ''), c);
test('Every modality uses explicit frequency, duration and inventory with exact session count', () => {
  for (const type of ['musculacao','calistenia','corrida','hibrido']) for (const weeks of [1,4,8,12]) for (const frequency of [2,3,5,7]) {
    const form = { ...c.initialGenerationForm(), workout_type: type, weeks, training_days_per_week: frequency, training_location: 'casa', available_equipment: [] };
    const body = c.generationPayload(form);
    assert.equal(body.training_days_per_week, frequency); assert.equal(body.cycle_weeks, weeks);
    assert.equal(c.generationCount(form), weeks * frequency); assert.equal(body.available_equipment.length, 0);
    assert.equal(body.weekly_frequency, undefined); assert.equal(body.calisthenics_equipment, undefined);
    if (type === 'calistenia' || type === 'corrida') assert.equal(body.generation_mode, 'periodo');
    form.single = true; assert.equal(c.generationPayload(form).duration, 'dia'); assert.equal(c.generationPayload(form).training_days_per_week, undefined); assert.equal(c.generationCount(form), 1);
  }
});
test('Unknown inventory and location require an explicit declaration; split/history keys are retained', () => {
  const form = c.initialGenerationForm(); assert.throws(() => c.generationPayload(form), /onde/);
  form.training_location = 'academia'; assert.throws(() => c.generationPayload(form), /Declare/);
  form.available_equipment = ['halteres', 'banco']; form.generation_mode = 'tipo_treino';
  const body = c.generationPayload(form); assert.equal(body.duration, 'ciclo'); assert.equal(body.split_config.length, 3);
  form.health_condition = ' Relato privado '; form.avoid_text = 'Paralelas\n\nSupino';
  assert.equal(c.generationPayload(form).health_condition, 'Relato privado'); assert.equal(c.generationPayload(form).avoid_exercises.length, 2);
});
test('Lost/internal response locks a snapshot, prevents simultaneous requests and replays the exact key', () => {
  let sequence = 0; const request = c.createGenerationRequest(() => `generation-${++sequence}`), payload = { equipment: ['halteres'], health: 'private' };
  const first = request.begin(payload); payload.equipment.push('banco');
  assert.equal(first.payload.equipment.length, 1); assert.equal(request.begin(payload), null);
  assert.equal(request.finish({ response: { status: 500 } }), true);
  const retry = request.begin({ equipment: [], health: 'changed' });
  assert.equal(retry.key, first.key); assert.equal(JSON.stringify(retry.payload), JSON.stringify(first.payload));
  request.finish(); assert.notEqual(request.begin(payload).key, first.key);
});
test('Typed pre-write provider/calendar errors allow editing; generic unavailable remains uncertain', () => {
  for (const code of ['ai_timeout', 'ai_output_truncated', 'workout_generation_incomplete_bases']) assert.equal(c.uncertainGeneration({ response: { status: 502, data: { detail: { code } } } }), false);
  assert.equal(c.uncertainGeneration({ response: { status: 422 } }), false);
  assert.equal(c.uncertainGeneration({ response: { status: 503 } }), true); assert.equal(c.uncertainGeneration({}), true);
});
