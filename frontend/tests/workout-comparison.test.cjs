const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../src/lib/workout-comparison.js'), 'utf8').replaceAll('export ', '');
const context = vm.createContext({}); vm.runInContext(source, context);
test('comparison uses recorded sets, reps and RPE without guessing missing history', () => {
  const result = context.compareExercise({ sets_data: [{ weight: 20, reps: 10, rpe: 8, completed: true }, { weight: 20, reps: 8, rpe: 9, completed: true }] }, { sets_data: [{ weight: 20, reps: 8, rpe: 8, completed: true }] });
  assert.equal(result.volumeDelta, 200); assert.equal(result.repsDelta, 10); assert.equal(result.rpeDelta, .5);
  assert.equal(context.compareExercise({}, {}), null);
  assert.equal(context.summarizeSets({ sets_data: [{ weight: 'invalid', reps: 10 }] }), null);
});

test('comparison preserves unknown loads and excludes unfinished sets', () => {
  const actual = { weight: '20', reps: 10, completed: true };
  for (const weight of ['', ' ', null, undefined, false, 'invalid']) {
    assert.equal(context.summarizeSets({ sets_data: [actual, { ...actual, weight }] }), null);
  }
  const result = context.summarizeSets({ sets_data: [actual, { weight: '999', reps: 999, completed: false }] });
  assert.equal(result.volume, 200); assert.equal(result.sets, 1);
  assert.equal(context.summarizeSets({ sets_data: [{ ...actual, weight: '0' }] }).volume, 0);
  assert.equal(context.summarizeSets({ sets_data: [{ weight: 20, reps: 10 }] }), null);
});
