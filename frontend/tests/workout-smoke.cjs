// Local visual QA with synthetic data; all API requests are intercepted.
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const { createRequire } = require('node:module');
const localRequire = createRequire(path.join(process.cwd(), 'package.json'));
const { chromium } = localRequire('playwright');
const output = path.join(process.cwd(), 'test-results');
fs.mkdirSync(output, { recursive: true });
const build = path.join(process.cwd(), 'build');
const user = { user_id: 'visual-fixture', name: 'João Pedro', rank: 'Cabo', xp: 420 };
const disciplines = ['Língua Portuguesa', 'Raciocínio Lógico', 'Direito Constitucional', 'Direito Administrativo', 'Legislação Especial'].map((nome, i) => ({
  notebook_id: `nb${i}`, nome, name: nome, peso: i > 1 ? 2 : 1, num_questoes: 10,
  prioridade: i > 1 ? 'alta' : 'media', prioridade_base: 'peso × questões', prioridade_provisoria: false,
  conteudo_programatico: [{ assunto: i ? 'Princípios e fundamentos' : 'Compreensão e interpretação de textos', subtopicos: ['Conceitos essenciais', 'Aplicação em questões'] }, { assunto: 'Revisão e resolução de exercícios', subtopicos: [] }],
  topic_progress: { 0: { studied: true } }, topicos: [], color: '#879eff', area_id: 'area1', program_id: 'demo',
}));
const concurso = { nome: 'Tribunal de Justiça · Concurso 2026', orgao: 'Tribunal de Justiça', banca: 'Banca do concurso', visao_geral: 'Organize sua preparação por disciplina e acompanhe os assuntos do cargo escolhido.', prazos: [{ label: 'Inscrições', data: '20/10/2026', fonte: 'Inscrições até 20/10/2026.' }] };
const cargo = { nome: 'Analista Judiciário — Área Judiciária', vagas: 'Cadastro reserva', remuneracao: 'R$ 8.829,24', escolaridade: 'Graduação em Direito', disciplinas: disciplines, disciplinas_status: 'completo' };
const program = { program_id: 'demo', area_id: 'area1', name: 'TJ · Analista Judiciário', source_type: 'edital_import', target_date: '2026-11-08', edital_data: { concurso, cargo_selecionado: cargo, pdf_filename: 'edital-demonstracao.pdf' } };
const fixtures = {
  '/api/auth/me': user,
  '/api/stats/dashboard': { tasks_completed: 4, tasks_total: 7, habits_completed: 3, habits_total: 5, income: 4200, expenses: 1850, balance: 2350, workout_stats: { total_workouts: 3, total_duration_minutes: 150 }, study_stats: { study_time_today_minutes: 75, current_streak: 5, notebooks_count: 5 } },
  '/api/study/areas': [{ area_id: 'area1', name: 'Concursos públicos', color: '#879eff' }],
  '/api/study/programs': [program], '/api/study/notebooks': disciplines,
  '/api/study/programs/editais': { editais: [{ analysis_id: 'analysis1', concurso, pdf_filename: 'edital-demonstracao.pdf', num_cargos: 2 }] },
  '/api/study/programs/editais/analysis1': { analysis_id: 'analysis1', concurso, cargos: [cargo, { ...cargo, nome: 'Técnico Judiciário' }], pdf_filename: 'edital-demonstracao.pdf' },
  '/api/study/programs/demo/edital-verticalizado': { disciplinas: disciplines },
  '/api/study/programs/demo/cronograma': { program, notebooks: disciplines, estrategia: {}, cronograma: ['Segunda-feira', 'Terça-feira', 'Quarta-feira'].map((day_label, i) => ({ day: i, day_label, total_minutes: 90, blocos: [{ schedule_id: `sc${i}`, notebook_id: `nb${i}`, start_time: '19:00', end_time: '20:30', disciplina_nome: disciplines[i].nome, tipo_estudo: 'Teoria e questões' }] })) },
  '/api/study/streak': { current_streak: 5, best_streak: 12 },
  '/api/study/stats': {}, '/api/study/questions/stats': {}, '/api/study/focus/stats': {},
  '/api/workout-stats': { total_workouts: 3, total_duration_minutes: 150, total_calories: 840, total_xp_earned: 90 },
  '/api/workout-stats/detailed': null, '/api/body-measurements/latest': null,
  '/api/motivational-quote': null, '/api/study/overall-stats': null,
  '/api/dashboard/weekly-summary': null, '/api/stats/analytics': null,
  '/api/streaks/global': null, '/api/dashboard/daily-summary': null,
};
const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost');
  let filename = path.join(build, decodeURIComponent(url.pathname));
  if (!filename.startsWith(build + path.sep) && filename !== build) { res.writeHead(403); return res.end(); }
  if (!fs.existsSync(filename) || fs.statSync(filename).isDirectory()) filename = path.join(build, 'index.html');
  const mime = { '.js': 'application/javascript', '.css': 'text/css', '.html': 'text/html', '.json': 'application/json', '.png': 'image/png', '.svg': 'image/svg+xml' };
  res.setHeader('Content-Type', mime[path.extname(filename)] || 'application/octet-stream');
  fs.createReadStream(filename).pipe(res);
});
(async () => {
  await new Promise(resolve => server.listen(4173, '127.0.0.1', resolve));
  const browser = await chromium.launch({ ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}), headless: true });
  const errors = [];
  try {
    for (const width of [1440, 390, 320]) {
      const context = await browser.newContext({ viewport: { width, height: width > 500 ? 1000 : 844 }, serviceWorkers: 'block' });
      await context.addInitScript(() => localStorage.setItem('sirius_onboarding_complete', 'true'));
      const drafts = new Map();
      let activeWorkout = { session_id: 'active-test', plan_name: 'Treino A · Semana 1', status: 'active', started_at: new Date(Date.now() - 60000).toISOString(), revision: 0, exercises: [{ name: 'Agachamento com halteres', sets: 3, reps: 12, weight: '20', rest_seconds: 60, sets_completed: 0, sets_data: [], completed: false }] };
      await context.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (url.pathname.startsWith('/api/')) {
          let body = Object.hasOwn(fixtures, url.pathname) ? fixtures[url.pathname] : [];
          if (url.pathname === '/api/dashboard/panels') body = {panels: {}, errors: []};
          if (url.pathname === '/api/ai/conversation') body = {messages: []};
          if (url.pathname === '/api/workout-sessions/active') body = { active: true, session: activeWorkout };
          if (url.pathname === '/api/workout-sessions/active-test/exercise/0') {
            const payload = route.request().postDataJSON();
            activeWorkout = { ...activeWorkout, revision: activeWorkout.revision + 1, exercises: [{ ...activeWorkout.exercises[0], ...payload, sets_completed: payload.sets_data.length }] };
            assert.equal(payload.sets_data[0].reps, 10); body = activeWorkout;
          }
          if (url.pathname.endsWith('/draft')) {
            const key = url.pathname + url.search;
            if (route.request().method() === 'PUT') { const data = route.request().postDataJSON(); drafts.set(key, { text: data.text, revision: (drafts.get(key)?.revision || 0) + 1 }); }
            body = drafts.get(key) || { text: '', revision: 0 };
          }
          if (url.pathname.endsWith('/learning-summary')) body = { answered: 40, correct: 30, accuracy: 75 };
          if (url.pathname.endsWith('/dated-plan')) body = { entries: [], settings: null };
          if (url.pathname.endsWith('/edital-jobs')) body = { jobs: [{ job_id: 'job', filename: 'edital-demonstracao.pdf', status: 'completed', phase: 'Análise disponível para conferência', analysis_id: 'analysis1' }] };
          if (url.pathname.endsWith('/lessons')) body = { status: 'not_configured', videos: [], message: 'Pesquise aulas relacionadas a este assunto.', search_url: 'https://www.youtube.com/results?search_query=direito' };
          if (url.pathname.endsWith('/topic-progress') && route.request().method() === 'POST') { const data = route.request().postDataJSON(); body = { topics: { [data.topic_key]: { [data.status]: data.checked } } }; }
          return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
        }
        
        if (url.hostname !== '127.0.0.1') return route.abort();
        return route.continue();
      });
      const page = await context.newPage();
      page.on('pageerror', e => errors.push({ width, url: page.url(), error: e.message }));
      const cases = [['active-workout', '/workouts']];
      for (const [name, url] of cases) {
        if (process.env.VISUAL_CASES && !process.env.VISUAL_CASES.split(',').includes(name)) continue;
        await page.goto(`http://127.0.0.1:4173${url}`);
        await page.locator('h1, h2').first().waitFor();
        await page.waitForTimeout(600);
        if (name === 'syllabus') await page.locator('details summary').first().click();
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
        console.log(JSON.stringify({ name, width, overflow, title: await page.locator('h1, h2').first().innerText() }));
        await page.screenshot({ path: path.join(output, `${name}-${width}.png`), fullPage: name === 'syllabus' });
        if (overflow) console.log(await page.evaluate(() => Array.from(document.querySelectorAll('body *')).filter(e => e.getBoundingClientRect().right > innerWidth + 2).slice(0, 10).map(e => ({ tag: e.tagName, cls: e.className }))));
        if (overflow) errors.push({ name, width, error: 'Horizontal overflow' });
        if (name === 'active-workout') {
          await page.getByRole('button', { name: '2. Retomar treino', exact: true }).click();
          await page.getByRole('button', { name: 'Registrar série de Agachamento com halteres', exact: true }).click();
          await page.getByLabel('Carga da série', { exact: true }).fill('25');
          await page.getByLabel('Repetições da série', { exact: true }).fill('10');
          await page.getByLabel('Esforço percebido da série (RPE)', { exact: true }).fill('7');
          assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
          await page.screenshot({ path: path.join(output, `active-set-${width}.png`), fullPage: true });
          await page.reload();
          await page.getByRole('button', { name: '2. Retomar treino', exact: true }).click();
          assert.equal(await page.getByLabel('Carga da série', { exact: true }).inputValue(), '25');
          assert.equal(await page.getByLabel('Repetições da série', { exact: true }).inputValue(), '10');
          await page.getByRole('button', { name: 'Salvar série', exact: true }).click();
          await page.waitForFunction(() => !document.querySelector('input[aria-label="Carga da série"]'));
          assert.equal(activeWorkout.exercises[0].sets_completed, 1);
          await page.screenshot({ path: path.join(output, `active-rest-${width}.png`), fullPage: true });
        }
        if (name === 'dashboard') {
          const launcher = page.getByRole('button', { name: 'Abrir assistente Sirius', exact: true });
          const before = await launcher.boundingBox();
          await page.mouse.move(before.x + 28, before.y + 28); await page.mouse.down();
          await page.mouse.move(50, 160, { steps: 12 }); await page.mouse.up();
          assert.equal(await page.getByRole('dialog').count(), 0, 'drag must not open chat');
          const moved = await launcher.boundingBox(); assert.ok(moved.y < before.y - 20);
          await launcher.click();
          const close = page.getByRole('button', { name: 'Fechar assistente', exact: true }); await close.waitFor();
          const box = await close.boundingBox(); assert.ok(box.x >= 0 && box.x + box.width <= width);
          await page.getByLabel('Mensagem para o assistente').fill('Como organizar meus estudos?');
          await page.screenshot({ path: path.join(output, `assistant-${width}.png`) });
          if (width < 500) {
            await page.setViewportSize({ width, height: 430 });
            const small = await close.boundingBox(); assert.ok(small.y >= 0 && small.y + small.height < 430);
            await page.screenshot({ path: path.join(output, `assistant-keyboard-${width}.png`) });
            await page.setViewportSize({ width, height: 844 });
          }
          await close.click(); await launcher.waitFor({ state: 'visible' });
          await launcher.click(); await page.keyboard.press('Escape'); await launcher.waitFor({ state: 'visible' });
          await page.reload(); await launcher.waitFor();
          const restored = await launcher.boundingBox(); assert.ok(Math.abs(restored.x - moved.x) < 2);
        }
        if (name === 'session') {
          assert.ok((await page.locator('body').innerText()).includes('45:00'));
          await page.getByRole('button', { name: /Iniciar foco/i }).click();
          await page.waitForTimeout(2100);
          assert.ok(!(await page.locator('body').innerText()).includes('45:00'));
          await page.getByLabel('Anotações da sessão', { exact: true }).fill('Rascunho persistente de teste');
          await page.getByText('Salvo na sua conta', { exact: true }).waitFor();
          await page.reload();
          await page.getByRole('button', { name: 'Pausar foco', exact: true }).waitFor();
          assert.equal(await page.getByLabel('Anotações da sessão', { exact: true }).inputValue(), 'Rascunho persistente de teste');
          await page.getByRole('button', { name: 'Pausar foco', exact: true }).click();
          await page.getByRole('button', { name: 'Retomar foco', exact: true }).waitFor();
        }
        if (name === 'workouts') {
          await page.getByRole('button', { name: 'Registrar Treino', exact: true }).click();
          const dialog = page.getByRole('dialog');
          await dialog.waitFor();
          const bounds = await dialog.boundingBox();
          assert.ok(bounds.x >= 0 && bounds.x + bounds.width <= width + 1);
          await page.screenshot({ path: path.join(output, `workout-dialog-${width}.png`), animations: 'disabled' });
          await page.keyboard.press('Escape');
        }
        if (name === 'syllabus') {
          const saved = page.waitForResponse(r => r.url().endsWith('/topic-progress') && r.request().method() === 'POST');
          await page.getByLabel('Revisado', { exact: true }).first().click();
          await saved;
          await page.waitForFunction(() => Array.from(document.querySelectorAll('label')).some(l => l.textContent === 'Revisado' && l.querySelector('input')?.checked));
          await page.getByRole('button', { name: 'Estudar', exact: true }).first().click();
          await page.getByRole('heading', { name: 'Compreensão e interpretação de textos', exact: true }).waitFor();
          assert.equal(await page.getByLabel('Marcar como revisado', { exact: true }).isChecked(), true);
        }
      }
      await context.close();
    }
    assert.deepEqual(errors, []);
    console.log('Visual checks passed; screenshots in ' + output);
  } finally { await browser.close(); server.close(); }
})().catch(error => { console.error(error); server.close(); process.exitCode = 1; });
