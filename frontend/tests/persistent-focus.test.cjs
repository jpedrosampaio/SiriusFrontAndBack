const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../src/lib/session-storage.js'), 'utf8');
const helper = import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));

test('a backgrounded countdown catches up by wall clock and never becomes negative', async () => {
  const { remainingSeconds } = await helper;
  const state = { isRunning: true, isPaused: false, timeLeft: 1500, deadline: 1500000 };
  assert.equal(remainingSeconds(state, 120000), 1380);
  assert.equal(remainingSeconds(state, 1499900), 1);
  assert.equal(remainingSeconds(state, 1600000), 0);
  assert.equal(remainingSeconds({ ...state, isPaused: true, timeLeft: 45 }, 1600000), 45);
});

test('unavailable or corrupt storage does not crash a study session', async () => {
  const { readSaved, writeSaved } = await helper;
  const previous = global.localStorage;
  try {
    global.localStorage = { getItem() { return '{broken'; }, setItem() { throw new Error('quota'); } };
    assert.equal(readSaved('user:one', 'fallback'), 'fallback');
    assert.equal(writeSaved('user:one', { text: 'Draft' }), false);
  } finally { global.localStorage = previous; }
});
