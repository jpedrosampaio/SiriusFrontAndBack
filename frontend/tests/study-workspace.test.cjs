const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const helper = import('data:text/javascript;base64,' + Buffer.from(fs.readFileSync(path.join(__dirname, '../src/lib/study-workspace.js'), 'utf8')).toString('base64'));

test('nested topic keys preserve existing progress indexes, including malformed legacy entries', async () => {
  const { topicRows } = await helper;
  assert.deepEqual(topicRows({ conteudo_programatico: [null, { assunto: 'Constituição', subtopicos: ['Direitos', null, 'Garantias'] }, 'Legislação'] }).map(t => [t.key, t.title, t.depth]), [
    ['1', 'Constituição', 0], ['1_0', 'Direitos', 1], ['1_2', 'Garantias', 1], ['2', 'Legislação', 0],
  ]);
  assert.equal(topicRows({ topicos: ['Revisão'] })[0].key, '0');
  assert.deepEqual(topicRows({ conteudo_programatico: [{ assunto: 'Direito', subtopicos: ['Garantias'], topic_key: '1', subtopic_keys: ['1_1'] }] }).map(t => t.key), ['1', '1_1']);
  assert.equal(topicRows({ conteudo_programatico: [{ assunto: 'Direito', subtopicos: 'Princípios' }] })[1].title, 'Princípios');
  assert.deepEqual(topicRows({ conteudo_programatico: 'invalid', topicos: null }), []);
});

test('scheduled session duration uses valid block boundaries and falls back for legacy invalid times', async () => {
  const { blockMinutes } = await helper;
  assert.equal(blockMinutes({ start_time: '8:15', end_time: '09:00' }), 45);
  for (const block of [{}, { start_time: '25:00', end_time: '26:00' }, { start_time: '09:00', end_time: '08:00' }, { start_time: '09:60', end_time: '10:30' }]) assert.equal(blockMinutes(block), 25);
});

test('search ignores accents and date-only values do not shift with timezones', async () => {
  const { normalizeStudyText, displayStudyDate } = await helper;
  assert.equal(normalizeStudyText('LÍNGUA Portuguesa'), 'lingua portuguesa');
  assert.equal(displayStudyDate('2026-11-08'), '08/11/2026');
  assert.equal(displayStudyDate('A definir'), 'A definir');
});
