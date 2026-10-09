// Five widths, synthetic API only. Suggestions are never applied as mutations.
const fs = require('node:fs'), path = require('node:path'), http = require('node:http'), assert = require('node:assert/strict');
const { chromium } = require('playwright');
const root = path.join(process.cwd(), 'build');
const server = http.createServer((req, res) => {
  let file = path.join(root, new URL(req.url, 'http://localhost').pathname);
  if (!file.startsWith(root + path.sep)) { res.writeHead(403); return res.end(); }
  if (!fs.existsSync(file) || fs.statSync(file).isDirectory()) file = path.join(root, 'index.html');
  res.setHeader('Content-Type', ({ '.js': 'application/javascript', '.css': 'text/css', '.html': 'text/html' })[path.extname(file)] || 'application/octet-stream');
  fs.createReadStream(file).pipe(res);
});
(async () => {
  await new Promise(resolve => server.listen(4185, '127.0.0.1', resolve));
  const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
  try {
    for (const width of [1440, 1024, 768, 390, 320]) {
      const context = await browser.newContext({ viewport: { width, height: 900 }, serviceWorkers: 'block' });
      await context.addInitScript(() => localStorage.setItem('sirius_onboarding_complete', 'true'));
      const errors = [], writes = [];
      let reads = 0, alternatives = 0, failState = false, failAlternative = true, requestedDays = 90;
      const plan = { plan_id: '00000000-0000-4000-8000-000000000001', name: 'Plano com nome extenso para testar quebra de texto no celular', objective: 'hipertrofia', plan_duration: 'dia', days: [{ day_label: 'Treino A', week: 1, exercises: [{ name: 'Supino reto com halteres e descrição longa', sets: 3, reps: '8-12', muscle_group: 'Peito', weight: '20' }] }] };
      plan.exercises = plan.days.flatMap(day => day.exercises);
      const exercise = { key: 'supino|peito', name: 'Supino reto com halteres e descrição longa', muscle_group: 'Peito', executions: 2,
        recorded_sets: 6, prescribed_sets: 6, known_volume: '1440.000', volume: null, average_rpe: null, rpe_samples: 0,
        records: [{ kind: 'max_load', value: '20.000', reps: 12, date: '2026-10-07', log_id: 'actual-source' }],
        progression: { action: 'review_increase', current_weight: '20.000', suggested_weight: '20.500', reason: 'Duas execuções completas. Avalie o incremento; nada foi alterado.', evidence_dates: ['2026-10-02', '2026-10-07'], automatic: false },
        alerts: [{ code: 'load_jump', reason: 'Confira a mudança de carga registrada, sem diagnóstico.' }],
        history: [{ date: '2026-10-07', log_id: 'actual-source', recorded_sets: 3, prescribed_sets: 3, volume: null, max_load: '20', average_rpe: null }] };
      const state = { as_of: '2026-10-08', start: '2026-07-11', timezone: 'America/Sao_Paulo', truncated: true,
        completed_workouts: 4, analyzed_workouts: 2, training_days: 2, recorded_minutes: 60, set_adherence: 100,
        exercises: [exercise], muscle_groups: [{ name: 'Peito', recorded_sets: 6, volume: null, known_volume: '1440' }],
        weekly_frequency: [{ week_start: '2026-10-05', workouts: 2, training_days: 2 }],
        limitations: ['Recordes na janela, não em toda a vida.', 'Dados ausentes continuam desconhecidos.'] };
      await context.route('**/*', async route => {
        const request = route.request(), url = new URL(request.url());
        if (!url.pathname.startsWith('/api/')) {
          if (url.hostname === '127.0.0.1') return route.continue();
          return route.abort();
        }
        let data = [];
        if (request.method() !== 'GET' && !url.pathname.endsWith('/intelligence/substitutions')) writes.push(url.pathname);
        if (url.pathname === '/api/auth/me') data = { user_id: 'training-smoke', name: 'Training', xp: 10, rank: 'Cabo', timezone: 'America/Sao_Paulo' };
        if (url.pathname === '/api/workout-plans') data = [plan];
        if (url.pathname === '/api/workout-sessions/active') data = { active: false };
        if (url.pathname === '/api/daily-workout-status') data = {};
        if (url.pathname === '/api/workout-stats') data = { total_workouts: 0, total_duration_minutes: 0 };
        if (url.pathname === '/api/workouts/intelligence/state') {
          reads++; requestedDays = Number(url.searchParams.get('days'));
          if (failState) { failState = false; return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Falha temporária da análise' }) }); }
          data = state;
        }
        if (url.pathname === '/api/workouts/intelligence/substitutions') {
          alternatives++; assert.deepEqual(request.postDataJSON(), { plan_id: plan.plan_id, day_index: 0, exercise_index: 0 });
          if (failAlternative) { failAlternative = false; return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Falha temporária das alternativas' }) }); }
          data = { exercise: exercise.name, automatic: false, truncated: false, suggestions: [{ name: 'Alternativa registrada', source_plan_id: plan.plan_id, movement_confirmed: false, reason: 'Mesmo grupo e objetivo, movimento desconhecido.' }], limitations: ['Não altera ficha ou sessão.'] };
        }
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data) });
      });
      const page = await context.newPage(); page.on('pageerror', error => errors.push(error.message));
      await page.goto('http://127.0.0.1:4185/workouts');
      await page.getByRole('tab', { name: 'Inteligência', exact: true }).waitFor(); assert.equal(reads, 0);
      await page.getByRole('tab', { name: 'Inteligência', exact: true }).click().catch(async error => {
        console.error(JSON.stringify({ width, errors, url: page.url(), body: (await page.locator('body').innerText()).slice(0, 1800) })); throw error;
      });
      const panel = page.getByRole('region', { name: 'Inteligência de treino', exact: true });
      await panel.getByRole('heading', { name: 'Aumento para avaliar' }).waitFor();
      await panel.getByText('Incompleto', { exact: true }).waitFor();
      assert.equal(await panel.getByText('Não disponível · 0 amostras', { exact: true }).count(), 1);
      await panel.getByText('Recordes na janela e últimas execuções', { exact: true }).click();
      await panel.getByText(/Maior carga: 20 kg/).waitFor();
      await panel.getByLabel('Janela de análise').selectOption('30');
      await page.waitForFunction(() => !document.body.textContent.includes('Analisando registros…')); assert.equal(requestedDays, 30);
      failState = true; await panel.getByRole('button', { name: 'Atualizar análise' }).click();
      await panel.getByRole('alert').getByText('Falha temporária da análise').waitFor();
      await panel.getByRole('button', { name: 'Atualizar análise' }).click();
      await panel.getByRole('heading', { name: 'Aumento para avaliar' }).waitFor();
      await panel.getByLabel('Exercício da ficha').selectOption(`${plan.plan_id}:0:0`);
      await panel.getByText('Falha temporária das alternativas', { exact: false }).waitFor();
      await panel.getByRole('button', { name: 'Tentar alternativas novamente' }).click();
      await panel.getByRole('heading', { name: 'Alternativa registrada' }).waitFor();
      await panel.getByText('Movimento não confirmado: candidato para avaliação.', { exact: true }).waitFor();
      fs.mkdirSync('test-results', { recursive: true });
      await page.screenshot({ path: `test-results/training-intelligence-populated-${width}.png`, fullPage: true });
      state.exercises = []; state.muscle_groups = []; state.completed_workouts = 0; state.set_adherence = null; state.training_days = 0; state.recorded_minutes = 0;
      await page.evaluate(() => window.dispatchEvent(new Event('sirius-data-changed')));
      await panel.getByText(/Ainda não há séries analisáveis/).waitFor();
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
      assert.deepEqual(writes, []); assert.deepEqual(errors, []); assert.equal(alternatives, 2); assert.equal(reads, 5);
      fs.mkdirSync('test-results', { recursive: true }); await panel.getByRole('heading', { name: 'Inteligência de treino', exact: true }).scrollIntoViewIfNeeded();
      await page.screenshot({ path: `test-results/training-intelligence-${width}.png` });
      console.log(JSON.stringify({ width, readonly: true, unknowns: true, explicitSuggestions: true, retries: true, overflow: false }));
      await context.close();
    }
  } finally { await browser.close(); server.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; server.close(); });
