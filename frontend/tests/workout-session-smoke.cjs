// Fully intercepted browser QA. No account or production mutations.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const { chromium } = require('playwright');
const build = path.join(process.cwd(), 'build');
const output = path.join(process.cwd(), 'test-results');
fs.mkdirSync(output, { recursive: true });
const server = http.createServer((req, res) => {
  let file = path.join(build, decodeURIComponent(new URL(req.url, 'http://localhost').pathname));
  if (!file.startsWith(build + path.sep) && file !== build) { res.writeHead(403); return res.end(); }
  if (!fs.existsSync(file) || fs.statSync(file).isDirectory()) file = path.join(build, 'index.html');
  res.setHeader('Content-Type', { '.js': 'application/javascript', '.css': 'text/css', '.html': 'text/html', '.json': 'application/json', '.svg': 'image/svg+xml' }[path.extname(file)] || 'application/octet-stream');
  fs.createReadStream(file).pipe(res);
});
const exerciseName = 'Agachamento com halteres e movimento controlado para amplitude confortável';
const exercises = [
  { name: exerciseName, sets: 3, reps: '10–12', weight: '20', rest_seconds: 60, tutorial: 'Mantenha a execução controlada. '.repeat(30), muscle_group: 'Pernas' },
  { name: 'Remada unilateral apoiada', sets: 8, reps: '8–10', weight: '', rest_seconds: 90, tutorial: 'Controle o movimento.' },
  ...Array.from({ length: 10 }, (_, i) => ({ name: `Exercício complementar ${i + 3} com nome extenso para conferir a fila`, sets: 3, reps: 12, weight: '', rest_seconds: 30 })),
];
const plan = { plan_id: 'ux-plan', name: 'Treino completo de força · Semana 1', exercises, days: [{ day_label: 'Treino A', exercises }] };
const json = (route, body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
const clone = value => JSON.parse(JSON.stringify(value));

(async () => {
  await new Promise(resolve => server.listen(4174, '127.0.0.1', resolve));
  const browser = await chromium.launch({ ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}), headless: true });
  const errors = [];
  try {
    for (const width of [1440, 1024, 768, 390, 320]) {
      const context = await browser.newContext({ viewport: { width, height: width > 500 ? 1000 : 844 }, serviceWorkers: 'block' });
      await context.addInitScript(() => {
        if (location.hostname !== '127.0.0.1') return;
        localStorage.setItem('sirius_onboarding_complete', 'true');
        window.wakeStats = { requests: 0, releases: 0, denied: false };
        Object.defineProperty(navigator, 'wakeLock', { configurable: true, value: { request: async () => {
          window.wakeStats.requests++;
          if (window.wakeStats.denied) throw new Error('Platform denied');
          const target = new EventTarget();
          target.release = async () => { window.wakeStats.releases++; target.dispatchEvent(new Event('release')); };
          return target;
        } } });
      });
      let active = null, writes = 0, failCommitted = true, rejectNext = false, historyFail = false, tutorialFail = false;
      const receipts = new Map(), requests = [], setRequests = [];
      await context.route('**/*', async route => {
        const request = route.request(), url = new URL(request.url()), p = url.pathname, method = request.method();
        if (!p.startsWith('/api/')) return url.hostname === '127.0.0.1' ? route.continue() : route.abort();
        requests.push({ p, method });
        if (p === '/api/auth/me') return json(route, { user_id: 'workout-ux-fixture', name: 'Teste', rank: 'Cabo', xp: 420 });
        if (p === '/api/workout-plans') return json(route, [plan]);
        if (p === '/api/workout-stats') return json(route, { total_workouts: 0, total_duration_minutes: 0, total_calories: 0 });
        if (p === '/api/body-measurements/latest' || p === '/api/motivational-quote' || p === '/api/workouts/today-schedule') return json(route, null);
        if (p === '/api/daily-workout-status') return json(route, { 'ux-plan': { exercises_status: {}, completed: false } });
        if (p === '/api/workout-sessions/active') return json(route, { active: active?.status === 'active', session: active });
        if (p === '/api/workout-sessions/start') {
          assert.equal(request.postDataJSON().plan_id, 'ux-plan');
          active = { session_id: 'ux-session', plan_id: plan.plan_id, plan_name: plan.name, status: 'active', current_exercise_idx: 0, started_at: new Date(Date.now() - 61000).toISOString(), revision: 0, exercises: exercises.map(ex => ({ ...ex, sets_data: [], sets_completed: 0, completed: false })) };
          return json(route, active);
        }
        if (p === '/api/workouts/next-loads') return json(route, { suggestions: [{ name: exerciseName, current_weight: '20', next_weight: 22.5 }] });
        if (p === '/api/workouts/exercise-history') {
          if (historyFail) { historyFail = false; return json(route, { detail: 'Unavailable' }, 503); }
          return json(route, { history: url.searchParams.get('exercise_name') === exerciseName ? [{ date: '2026-10-06', sets_data: [{ weight: '20', reps: 10, completed: true, rpe: 7 }, { weight: '20', reps: 9, completed: true }] }] : [] });
        }
        if (p === '/api/workouts/tutorial-videos') {
          if (tutorialFail) return json(route, { status: 'unavailable', videos: [], message: 'Vídeos indisponíveis.' });
          return json(route, { status: 'ok', videos: [{ video_id: 'abcdefghijk', title: 'Execução demonstrada', channel: 'Canal de teste', url: 'https://www.youtube.com/watch?v=abcdefghijk' }] });
        }
        if (p.match(/\/workout-sessions\/ux-session\/exercise\/\d+$/)) {
          const idx = Number(p.split('/').at(-1)), body = request.postDataJSON(), key = request.headers()['idempotency-key'];
          assert.ok(key); setRequests.push({ idx, body, key });
          await new Promise(resolve => setTimeout(resolve, 250));
          if (receipts.has(key)) return json(route, receipts.get(key));
          if (rejectNext) { rejectNext = false; return json(route, { detail: 'Sessão alterada. Confira e tente novamente.' }, 409); }
          assert.equal(body.revision, active.revision); assert.equal(body.current_exercise_idx, idx);
          active.exercises[idx] = { ...active.exercises[idx], ...body, sets_completed: body.sets_data.length };
          active.revision++; active.current_exercise_idx = idx; writes++; receipts.set(key, clone(active));
          if (failCommitted) { failCommitted = false; return json(route, { detail: 'Resposta perdida após salvar' }, 504); }
          return json(route, active);
        }
        if (p.endsWith('/complete')) {
          active.status = 'completed'; return json(route, { total_duration_seconds: 95, completed_exercises: 1, total_exercises: 12, xp_earned: 12 });
        }
        if (p.endsWith('/abandon')) { active.status = 'abandoned'; return json(route, { success: true }); }
        return json(route, []);
      });
      const page = await context.newPage();
      page.on('pageerror', error => errors.push({ width, error: error.message }));
      page.setDefaultTimeout(12000);
      const checkLayout = async stage => {
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, `overflow ${width} ${stage}`);
        await page.screenshot({ path: path.join(output, `workout-ux2-${stage}-${width}.png`), animations: 'disabled' });
        if (stage === 'focus') console.log('LAYOUT ' + JSON.stringify(await page.evaluate(() => ({ scrollX, shell: document.querySelector('.sirius-shell-body').getBoundingClientRect().toJSON(), margin: getComputedStyle(document.querySelector('.sirius-shell-body')).marginLeft, focus: document.querySelector('.ws-focus').getBoundingClientRect().toJSON() }))));
      };
      const current = () => page.locator('.ws-exercise-name');
      const register = () => page.getByRole('button', { name: 'Concluir série', exact: true });
      const switchTo = idx => page.getByRole('button', { name: `Selecionar exercício ${idx + 1}: ${exercises[idx].name}`, exact: true }).click();
      const count = p => requests.filter(r => r.p === p).length;
      await page.goto('http://127.0.0.1:4174/workouts');
      await page.getByRole('button', { name: '1. Meu plano', exact: true }).click();
      await page.getByRole('heading', { name: plan.name, exact: true }).click();
      await page.getByRole('button', { name: 'Iniciar Treino com Timer', exact: true }).click();
      await current().waitFor(); await page.getByText('Sugestão de carga:', { exact: false }).waitFor();
      assert.equal(await current().innerText(), exerciseName);
      assert.equal(count('/api/workouts/tutorial-videos'), 0); assert.equal(count('/api/workouts/exercise-history'), 0);
      assert.equal(count('/api/workouts/next-loads'), 1);
      assert.equal(await page.evaluate(() => wakeStats.requests), 1);
      const baseline = requests.slice();
      await checkLayout('focus');
      await page.evaluate(() => window.scrollTo(0, document.querySelector('.ws-header').getBoundingClientRect().top + scrollY + 100));
      assert.equal(await page.locator('.ws-header').evaluate(el => getComputedStyle(el).position), 'sticky');
      assert.ok(Math.abs((await page.locator('.ws-header').boundingBox()).y - 60) < 2, 'header stays below the app bar');
      await page.evaluate(() => window.scrollTo(0, 0));
      const queueButton = await page.getByRole('button', { name: `Selecionar exercício 1: ${exerciseName}` }).boundingBox();
      assert.ok(queueButton.height >= 44);
      await page.getByLabel('Carga da série', { exact: true }).fill('42,5');
      await page.getByLabel('Repetições da série', { exact: true }).fill('11');
      await page.getByLabel('Esforço percebido da série (RPE)', { exact: true }).fill('7,5');
      await switchTo(1); assert.equal(await current().innerText(), exercises[1].name);
      await page.getByLabel('Carga da série', { exact: true }).fill('15');
      await switchTo(0); assert.equal(await page.getByLabel('Carga da série', { exact: true }).inputValue(), '42,5');
      assert.equal(requests.length, baseline.length, 'visual navigation sends no request');
      await register().click();
      await page.getByRole('button', { name: 'Tentar salvar novamente', exact: true }).waitFor();
      assert.equal(await page.getByLabel('Carga da série', { exact: true }).inputValue(), '42,5');
      assert.equal(await page.locator('.ws-set-track .done').count(), 0, 'no unconfirmed progress');
      await checkLayout('retry');
      await page.reload();
      await page.getByRole('button', { name: '2. Retomar treino', exact: true }).click();
      await page.getByRole('button', { name: 'Tentar salvar novamente', exact: true }).click();
      await page.getByText(/Próxima: série 2 de 3/).waitFor();
      assert.deepEqual(setRequests[0], setRequests[1]); assert.equal(writes, 1); assert.equal(active.exercises[0].sets_data.length, 1);
      assert.equal(active.exercises[0].sets_data[0].weight, '42.5'); assert.equal(active.exercises[0].sets_data[0].rpe, '7.5');
      assert.equal(await page.getByLabel('Repetições da série', { exact: true }).inputValue(), '11');
      let before = await page.locator('.ws-rest-time').innerText();
      await page.getByRole('button', { name: 'Aumentar descanso em 15 segundos' }).click();
      let after = await page.locator('.ws-rest-time').innerText(); assert.notEqual(before, after);
      await page.getByRole('button', { name: 'Diminuir descanso em 15 segundos' }).click();
      await checkLayout('rest');
      await page.reload(); await page.getByRole('button', { name: '2. Retomar treino', exact: true }).click();
      await page.locator('.ws-rest-time').waitFor();
      await page.getByRole('button', { name: 'Pular', exact: true }).click();
      await page.getByText('Pronto para continuar', { exact: true }).waitFor();
      // Definitive conflict preserves editable inputs and reconciles the backend.
      rejectNext = true;
      await register().click(); await page.getByRole('alert').filter({ hasText: 'Sessão alterada' }).waitFor();
      assert.equal(await page.getByLabel('Carga da série', { exact: true }).isEnabled(), true);
      await register().click(); await page.getByText(/Próxima: série 3 de 3/).waitFor();
      assert.equal(writes, 2);
      await page.getByRole('button', { name: 'Desfazer última série', exact: true }).click();
      await page.waitForFunction(() => document.querySelectorAll('.ws-set-track .done').length === 1);
      assert.equal(active.exercises[0].sets_data.length, 1);
      await register().click(); await page.getByText(/Próxima: série 3 de 3/).waitFor();
      await page.getByRole('button', { name: 'Pular', exact: true }).click();
      await register().click(); await page.getByRole('heading', { name: 'Exercício concluído', exact: true }).waitFor();
      assert.equal(active.exercises[0].completed, true); assert.equal(writes, 5);
      await page.getByRole('button', { name: `Ver tutorial de ${exerciseName}`, exact: true }).click();
      await page.getByText('Execução demonstrada', { exact: true }).waitFor();
      assert.equal(count('/api/workouts/tutorial-videos'), 1); assert.equal(await page.locator('iframe').count(), 0);
      await page.getByRole('button', { name: 'Assistir aqui', exact: true }).click(); assert.equal(await page.locator('iframe').count(), 1);
      await page.getByRole('button', { name: 'Fechar vídeo', exact: true }).click();
      await checkLayout('tutorial');
      await page.getByRole('button', { name: `Ver tutorial de ${exerciseName}`, exact: true }).click();
      historyFail = true;
      await page.getByRole('button', { name: 'Histórico', exact: true }).click();
      await page.getByRole('button', { name: 'Tentar histórico novamente' }).click();
      await page.getByText('Último treino · 2026-10-06', { exact: true }).waitFor();
      await page.locator('.ws-history summary').click();
      assert.equal(await page.getByText('Comparação com 2026-10-06', { exact: true }).count(), 1);
      await checkLayout('history');
      await page.getByRole('button', { name: 'Histórico', exact: true }).click(); await page.getByRole('button', { name: 'Histórico', exact: true }).click();
      assert.equal(count('/api/workouts/exercise-history'), 2, 'successful history is reused after the initial failed request');
      await page.getByRole('button', { name: 'Ir para próximo', exact: true }).click();
      assert.equal(await current().innerText(), exercises[1].name); assert.equal(await page.getByLabel('Carga da série', { exact: true }).inputValue(), '15');
      assert.equal(await page.locator('.ws-set-track span').count(), 8);
      assert.equal(count('/api/workouts/tutorial-videos'), 1);
      await page.getByRole('button', { name: 'Histórico', exact: true }).click();
      await page.getByText('Nenhum histórico registrado para este exercício.', { exact: true }).waitFor();
      tutorialFail = true;
      await page.getByRole('button', { name: `Ver tutorial de ${exercises[1].name}`, exact: true }).click();
      await page.getByText('Controle o movimento.', { exact: true }).waitFor();
      await page.getByLabel('Carga da série', { exact: true }).fill('');
      await page.getByLabel('Esforço percebido da série (RPE)', { exact: true }).fill('');
      await register().click(); await page.getByText(/Próxima: série 2 de 8/).waitFor();
      assert.equal(active.exercises[1].sets_data[0].weight, ''); assert.equal(active.exercises[1].sets_data[0].rpe, '');
      await checkLayout('next');
      if (width < 500) {
        await page.setViewportSize({ width, height: 430 });
        await page.getByLabel('Repetições da série', { exact: true }).focus();
        const button = await register().boundingBox(); assert.ok(button.y >= 0 && button.y + button.height < 430);
        assert.equal(await page.locator('.ws-primary-action').evaluate(el => getComputedStyle(el).position), 'fixed');
        assert.ok(Number.parseFloat(await page.locator('.ws-primary-action').evaluate(el => getComputedStyle(el).bottom)) >= 68);
        await checkLayout('keyboard'); await page.setViewportSize({ width, height: 844 });
      }
      await page.getByRole('button', { name: 'Abandonar sessão', exact: true }).click();
      await page.getByRole('dialog').waitFor(); await page.getByRole('button', { name: 'Continuar treino', exact: true }).click();
      assert.equal(count('/api/workout-sessions/ux-session/abandon'), 0);
      await page.getByRole('button', { name: 'Finalizar treino', exact: true }).click();
      await page.getByRole('dialog').waitFor(); await checkLayout('feedback');
      await page.getByRole('button', { name: 'Concluir', exact: true }).click();
      await page.getByRole('heading', { name: 'Treino concluído!', exact: true }).waitFor();
      const dialogText = await page.getByRole('dialog').innerText(); assert.ok(dialogText.includes('+12')); assert.ok(!dialogText.includes('Volume total')); assert.ok(!dialogText.includes('Cal'));
      await checkLayout('summary'); assert.ok(await page.evaluate(() => wakeStats.releases) >= 1);
      await page.getByRole('button', { name: 'Continuar', exact: true }).click();
      await page.getByRole('button', { name: '1. Meu plano', exact: true }).click();
      await page.getByRole('heading', { name: plan.name, exact: true }).click();
      await page.evaluate(() => { wakeStats.denied = true; });
      await page.getByRole('button', { name: 'Iniciar Treino com Timer', exact: true }).click();
      await current().waitFor(); assert.equal(await register().isEnabled(), true);
      await page.getByRole('button', { name: 'Abandonar sessão', exact: true }).click();
      await page.getByRole('button', { name: 'Confirmar abandono', exact: true }).click();
      await page.waitForFunction(() => !document.querySelector('.workout-session'));
      assert.equal(active.status, 'abandoned');
      console.log('WORKOUT_UX2 ' + JSON.stringify({ width, writes, retries: 1, nextLoadsStart: 1, initialVideos: 0, initialHistory: 0, visualSwitchRequests: 0, overflow: false, initialRequests: baseline }));
      await context.close();
    }
    assert.deepEqual(errors, []);
    console.log('Workout UX2 flow passed at all five viewports.');
  } finally { await browser.close(); server.close(); }
})().catch(error => { console.error(error); server.close(); process.exitCode = 1; });
