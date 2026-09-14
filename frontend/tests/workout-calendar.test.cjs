const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const helper = import('data:text/javascript;base64,' + Buffer.from(fs.readFileSync(path.join(__dirname, '../src/lib/workout-calendar.js'), 'utf8')).toString('base64'));

test('four weeks: switching weeks repeatedly keeps the correct day, title and exercises', async () => {
  const { getWorkoutCalendar } = await helper;
  const plan = { days: Array.from({ length: 20 }, (_, i) => ({ day_name: `sem${Math.floor(i / 5) + 1}_dia${i % 5 + 1}`, exercises: [{ name: `Exercise ${i}` }] })) };
  let index = 0;
  for (const week of [2, 3, 2, 4, 1, 2, 2]) {
    const previous = getWorkoutCalendar(plan, index);
    index = previous.weeks[week][0]._globalIdx;
    const current = getWorkoutCalendar(plan, index);
    assert.equal(current.selectedWeek, week);
    assert.equal(current.selectedDayIndex, (week - 1) * 5);
    assert.equal(plan.days[index].exercises[0].name, `Exercise ${(week - 1) * 5}`);
  }
});

test('legacy explicit week names override the five-day fallback', async () => {
  const { getWorkoutCalendar } = await helper;
  const plan = { days: Array.from({ length: 12 }, (_, i) => ({ day_label: `Semana ${Math.floor(i / 3) + 1} - Dia ${i % 3 + 1}` })) };
  assert.equal(getWorkoutCalendar(plan, 3).selectedWeek, 2);
  assert.deepEqual(getWorkoutCalendar(plan).weekNumbers, [1, 2, 3, 4]);
});

test('numeric string weeks and invalid selections normalize safely', async () => {
  const { getWorkoutCalendar } = await helper;
  const plan = { days: [{ week: '1' }, { week: '2' }] };
  assert.equal(getWorkoutCalendar(plan, 1).selectedWeek, 2);
  assert.equal(getWorkoutCalendar(plan, 99).selectedWeek, 1);
  assert.equal(getWorkoutCalendar({}).selectedDayIndex, 0);
});

test('selection on one plan does not become the default of another', async () => {
  const { getWorkoutCalendar } = await helper;
  const plan = { days: [{ week: 1 }, { week: 2 }] };
  const selections = { first: 1 };
  assert.equal(getWorkoutCalendar(plan, selections.first).selectedWeek, 2);
  assert.equal(getWorkoutCalendar(plan, selections.second).selectedWeek, 1);
});
