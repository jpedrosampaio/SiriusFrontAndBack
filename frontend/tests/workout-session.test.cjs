const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const context = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/lib/workout-session.js'), 'utf8').replaceAll('export ', ''), context);

test('load suggestions require the same stable day, account plan and muscle group', () => {
  const session = { plan_id: 'plan', day_index: 0, day_id: 'day-B' };
  const exercise = { name: 'Supino', muscle_group: 'Peito' };
  const wrong = { ...exercise, day_index: 0, day_id: 'day-A', next_weight: 99 };
  const correct = { ...exercise, day_index: 0, day_id: 'day-B', next_weight: 22.5 };
  const loads = { plan_id: 'plan', suggestions: [wrong, correct] };
  assert.equal(context.nextLoadForExercise(session, exercise, loads), correct);
  for (const changed of [{ day_id: undefined }, { day_index: 1 }, { plan_id: 'other' }]) {
    assert.equal(context.nextLoadForExercise({ ...session, ...changed }, exercise, loads), undefined);
  }
  assert.equal(context.nextLoadForExercise(session, { ...exercise, muscle_group: 'Outro' }, loads), undefined);
});

test('summary counts confirmed series and excludes unknown volume instead of claiming zero', () => {
  const session = { exercises: [{ completed: true, sets_data: [{ weight: '42.5', reps: 12, completed: true }, { weight: 40, reps: 10, completed: true }, { weight: 100, reps: 20, completed: false }] }] };
  assert.equal(context.workoutSummary(session).volume, 910);
  assert.equal(context.workoutSummary(session).sets, 2);
  assert.equal(context.workoutSummary(session).exercises, 1);
  session.exercises[0].sets_data.push({ weight: '', reps: 10 });
  assert.equal(context.workoutSummary(session).volume, null);
  assert.equal(context.workoutSummary({}).volume, null);
  assert.equal(context.workoutSummary({ exercises: [{ sets_data: [{ weight: 0, reps: 10 }] }] }).volume, 0);
});
test('set defaults preserve real zero, previous reps and RPE without treating textual loads as numbers', () => {
  assert.equal(context.setDefaults({ weight: 'moderada', reps: '10–12' }).weight, '');
  const defaults = context.setDefaults({ weight: 50, reps: '10–12', sets_data: [{ weight: 0, reps: 8, rpe: 7.5 }] });
  assert.equal(defaults.weight, '0'); assert.equal(defaults.reps, '8'); assert.equal(defaults.rpe, '7.5');
});
test('decimal weights and optional RPE normalize within the existing API contract', () => {
  const set = context.validateSet({ weight: '42,5', reps: '12', rpe: '7,5' });
  assert.equal(set.weight, '42.5'); assert.equal(set.reps, 12); assert.equal(set.rpe, '7.5');
  assert.equal(context.validateSet({ weight: '', reps: '1', rpe: '' }).weight, '');
  for (const weight of ['-1', 'NaN', '1.1234', '10000000', '20kg']) assert.throws(() => context.validateSet({ weight, reps: '12', rpe: '' }));
  for (const reps of ['0', '1000', '2.5', '']) assert.throws(() => context.validateSet({ weight: '', reps, rpe: '' }));
  assert.throws(() => context.validateSet({ weight: '', reps: '12', rpe: '11' }));
});
