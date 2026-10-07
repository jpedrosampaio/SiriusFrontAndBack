process.env.VISUAL_CASES ||= 'auth,dashboard,workouts,chat,tasks,habits,calendar,finance,nutrition,reports,studies,preparation,analysis,syllabus,session,agent';
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
  '/api/ai/status': { flags: { dry_run: true }, providers: { gemini: { has_key: false }, groq: { has_key: false } }, capabilities: { rag: 'lexical' }, internal_requests_today: 0, internal_daily_limit: 200 },
  '/api/ai/preferences': { profile: 'balanced', automations: false, quiet_start: 22, quiet_end: 8, daily_cap: 3, blocked_tools: [] },
  '/api/ai/memory': [],
  '/api/ai/rag/sources': { editais: [], notebooks: [] },
  '/api/stats/dashboard': { tasks_completed: 4, tasks_total: 7, habits_completed: 3, habits_total: 5, income: 4200, expenses: 1850, balance: 2350, workout_stats: { total_workouts: 3, total_duration_minutes: 150 }, study_stats: { study_time_today_minutes: 75, current_streak: 5, notebooks_count: 5 } },
  '/api/study/areas': [{ area_id: 'area1', name: 'Concursos públicos', color: '#879eff' }],
  '/api/study/v2/targets': [{ target_id: 'target1', program_id: 'demo', kind: 'contest', name: 'Preparação de teste', provenance: 'user_provided' }],
  '/api/study/v2/today': { planned_minutes: 60, studied_minutes: 25, next_session: { notebook_id: 'nb0', program_id: 'demo', topic_key: '0', name: 'Português', minutes: 30, kind: 'Teoria e questões' } },
  '/api/study/v2/library': { notebooks: disciplines, items: [{ id: 'note1', kind: 'note', notebook_id: 'nb0', title: 'Resumo de interpretação', excerpt: 'Material de teste', provenance: 'user_provided' }] },
  '/api/study/v2/performance': { summary: { score: 60, samples: 10 }, topics: [{ notebook_id: 'nb0', topic_key: '0', title: 'Interpretação', score: 60, samples: 10, confidence: 'low', range: [35, 85] }], errors: [], trend: [{ date: '2026-09-26', total: 10, correct: 6, accuracy: 60 }] },
  '/api/study/v2/programs/demo/overview': { coverage: { percent: 20, studied: 1, total: 5 }, mastery: { score: 60, samples: 10 }, study_minutes: 100, questions: 10, accuracy: 60 },
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
    for (const width of [1440, 1024, 768, 390, 320]) {
      const context = await browser.newContext({ viewport: { width, height: width > 500 ? 1000 : 844 }, serviceWorkers: 'block' });
      await context.addInitScript(() => localStorage.setItem('sirius_onboarding_complete', 'true'));
      const drafts = new Map();
      const requests = [];
      const reviewRows = [];
      let actionStatus = 'pending';
      let actionConfirmations = 0;
      let chatFailure = null;
      const chatAttempts = [];
      let activeUser = user;
      await context.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (url.pathname.startsWith('/api/')) {
          requests.push(url.pathname);
          if (url.pathname === '/api/ai/chat') {
            const payload = route.request().postDataJSON(); chatAttempts.push(payload);
            if (chatFailure) {
              const failure = chatFailure; chatFailure = null;
              if (failure === 'network') return route.abort('failed');
              return route.fulfill({ status: failure, contentType: 'application/json', body: JSON.stringify({ detail: 'Synthetic failure' }) });
            }
            return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ user_message: { message_id: 'u-' + payload.request_id, role: 'user', content: payload.message }, ai_message: { message_id: 'a-' + payload.request_id, role: 'assistant', content: 'Resposta de teste ' + payload.message, degraded: true } }) });
          }
          let body = Object.hasOwn(fixtures, url.pathname) ? fixtures[url.pathname] : [];
          if (url.pathname === '/api/auth/me') body = activeUser;
          if (url.pathname === '/api/auth/register' || url.pathname === '/api/auth/login') body = { session_token: 'synthetic-token', user };
          if (url.pathname === '/api/dashboard/panels') body = {panels: {}, errors: []};
          if (url.pathname === '/api/ai/daily') body = { tasks: { completed: 0, total: 1 }, commitments: [{ event_id: 'fixed', date: '2026-10-07', title: 'Compromisso registrado', start_minute: 840, end_minute: 900 }], plan: { date: '2026-10-07', available_minutes: 540, blocks: [{ task_id: 'task', title: 'Estudar Direito Constitucional', start_minute: 480, end_minute: 540, duration_minutes: 60 }], unscheduled: [] } };
          if (url.pathname === '/api/ai/conversation') body = {messages: [{message_id: 'fixture-private', role: 'assistant', content: 'Conversa sintética desta conta', actions: [{ action_id: 'fixture-expense', summary: 'Registrar despesa', reason: 'Pedido explícito', arguments: { amount: 48, category: 'Alimentação', date: '2026-09-26' }, status: actionStatus, expires_at: new Date(Date.now() + 1200000).toISOString() }] }]};
          if (url.pathname === '/api/ai/conversation' && activeUser.user_id !== user.user_id) body = { messages: [] };
          if (url.pathname === '/api/ai/actions/fixture-expense/confirm') { actionConfirmations++; actionStatus = 'executed'; body = { status: actionStatus }; }
          if (url.pathname === '/api/ai/attachments') body = { attachment_id: 'fixture-file', filename: 'material-teste.pdf', provenance: 'extracted', indexed: true };
          if (url.pathname.endsWith('/draft')) {
            const key = url.pathname + url.search;
            if (route.request().method() === 'PUT') { const data = route.request().postDataJSON(); drafts.set(key, { text: data.text, revision: (drafts.get(key)?.revision || 0) + 1 }); }
            body = drafts.get(key) || { text: '', revision: 0 };
          }
          if (url.pathname.endsWith('/reviews')) body = reviewRows;
          if (url.pathname.endsWith('/practice')) { const data = route.request().postDataJSON(); body = { ...data, title: 'Compreensão e interpretação de textos', due_date: '2026-09-27', accuracy: data.correct / data.total * 100 }; reviewRows.splice(0, reviewRows.length, body); }
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
      const cases = [
        ['auth', '/register'],
        ['dashboard', '/dashboard'], ['workouts', '/workouts'], ['studies', '/studies'],
        ['preparation', '/studies?program=demo&view=edital'],
        ['analysis', '/studies?analysis=analysis1'],
        ['syllabus', '/studies?program=demo&view=verticalizado'],
        ['schedule', '/studies?program=demo&view=cronograma'],
        ['session', '/studies?program=demo&view=estudar&notebook=nb0&topic=0&minutes=45'],
        ['tasks', '/tasks'], ['habits', '/habits'], ['goals', '/goals'],
        ['finance', '/finance'], ['nutrition', '/nutrition'], ['reports', '/reports'],
        ['calendar', '/calendar'], ['profile', '/profile'], ['notifications', '/notifications'],
        ['achievements', '/achievements'], ['chat', '/chat'],
        ['agent', '/assistant/settings'],
      ];
      for (const [name, url] of cases) {
        if (process.env.VISUAL_CASES && !process.env.VISUAL_CASES.split(',').includes(name)) continue;
        requests.length = 0;
        const started = performance.now();
        await page.goto(`http://127.0.0.1:4173${url}`);
        await page.locator('h1, h2').first().waitFor();
        const headingMs = Math.round(performance.now() - started);
        await page.waitForTimeout(600);
        if (name === 'dashboard') console.log('DASHBOARD_SYNTHETIC ' + JSON.stringify({ width, headingMs, requests: [...requests] }));
        if (name === 'syllabus') await page.locator('details summary').first().click();
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
        console.log(JSON.stringify({ name, width, overflow, title: await page.locator('h1, h2').first().innerText() }));
        await page.screenshot({ path: path.join(output, `${name}-${width}.png`), fullPage: name === 'syllabus' });
        if (overflow) console.log(await page.evaluate(() => Array.from(document.querySelectorAll('body *')).filter(e => e.getBoundingClientRect().right > innerWidth + 2).slice(0, 10).map(e => ({ tag: e.tagName, cls: e.className }))));
        if (overflow) errors.push({ name, width, error: 'Horizontal overflow' });
        if (name === 'dashboard') {
          assert.equal(requests.filter(p => p === '/api/ai/actions' || p === '/api/ai/insights').length, 0, 'closed suggestions must not fetch');
          await page.getByText('Estudar Direito Constitucional', { exact: true }).waitFor();
          assert.equal(await page.getByText('Capacidade em minutos', { exact: false }).count(), 0);
          assert.equal(await page.getByText('Ver plano de hoje', { exact: true }).count(), 0);
          const launcher = page.getByRole('button', { name: 'Abrir assistente Sirius', exact: true }).filter({ visible: true });
          assert.equal(await launcher.count(), 1, 'one visible Sirius entry point');
          await page.keyboard.press('Control+k');
          await page.getByRole('combobox').fill('Nova tarefa');
          await page.getByRole('option', { name: 'Nova tarefa' }).waitFor();
          await page.keyboard.press('Escape');
          await launcher.click();
          const close = page.getByRole('button', { name: 'Fechar assistente', exact: true }); await close.waitFor();
          await page.getByText('Conversa sintética desta conta', { exact: true }).waitFor();
          await page.getByRole('button', { name: 'Confirmar alteração', exact: true }).click();
          await page.getByText('Executada', { exact: true }).waitFor();
          assert.equal(actionConfirmations, 1, 'confirmation must submit once');
          await page.evaluate(() => window.dispatchEvent(new StorageEvent('storage', { key: 'sirius_session_token' })));
          await page.getByText('Conversa sintética desta conta', { exact: true }).waitFor({ state: 'hidden' });
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
          if (width === 1440) {
            await launcher.click();
            await page.getByLabel('Anexar PDF ou imagem ao Sirius').setInputFiles({ name: 'material-teste.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-fixture') });
            await page.getByText(/material-teste.pdf/).waitFor();
            await page.getByRole('link', { name: 'Abrir Sirius em tela cheia' }).click();
            await page.getByText(/material-teste.pdf/).waitFor();
            await page.evaluate(() => window.dispatchEvent(new Event('sirius-auth-changed')));
            await page.getByText(/material-teste.pdf/).waitFor({ state: 'hidden' });
            await page.goto('http://127.0.0.1:4173/dashboard');
          }
          await page.reload(); await launcher.waitFor();
        }
        if (name === 'auth') {
          await page.getByTestId('register-name-input').fill('Pessoa de teste');
          await page.getByTestId('register-email-input').fill('synthetic@example.test');
          await page.getByTestId('register-password-input').fill('synthetic-password-123');
          await page.getByTestId('register-submit-btn').click();
          await page.waitForURL('**/dashboard');
          await page.getByTestId('dashboard-title').waitFor();
          await page.reload(); await page.getByTestId('dashboard-title').waitFor();
          await page.goto('http://127.0.0.1:4173/profile');
          await page.getByTestId('profile-logout-btn').click();
          await page.waitForURL('**/login');
          assert.equal(await page.evaluate(() => localStorage.getItem('sirius_session_token')), null);
          await page.getByTestId('login-email-input').fill('synthetic@example.test');
          await page.getByTestId('login-password-input').fill('synthetic-password-123');
          await page.getByTestId('login-submit-btn').click();
          await page.waitForURL('**/dashboard');
          await page.getByTestId('dashboard-title').waitFor();
          console.log('AUTH_SMOKE ' + JSON.stringify({ width, signup: true, login: true, reload: true, logout: true }));
        }
        if (name === 'chat') {
          for (const failure of [409, 429, 503, 504, 'network']) {
            await page.getByRole('button', { name: 'Nova conversa', exact: true }).click();
            await page.waitForTimeout(150);
            chatFailure = failure;
            const text = 'Pedido de teste ' + failure;
            await page.getByLabel('Mensagem para o assistente', { exact: true }).fill(text);
            await page.getByRole('button', { name: 'Enviar mensagem', exact: true }).click();
            await page.getByRole('button', { name: 'Tentar novamente', exact: true }).waitFor();
            assert.equal(await page.getByText(text, { exact: true }).count(), 1, 'failed user message preserved');
            const historyBefore = requests.filter(p => p === '/api/ai/conversation').length;
            await page.getByRole('button', { name: 'Tentar novamente', exact: true }).click();
            await page.getByText('Resposta de teste ' + text, { exact: true }).waitFor();
            assert.equal(await page.getByText(text, { exact: true }).count(), 1, 'retry must not duplicate user message');
            assert.deepEqual(chatAttempts.at(-1), chatAttempts.at(-2), 'retry preserves entire request');
            assert.equal(requests.filter(p => p === '/api/ai/conversation').length, historyBefore, 'success must not refetch conversation');
          }
          await page.getByText('Resposta baseada nos dados do Sirius.', { exact: true }).waitFor();
          console.log('CHAT_RETRY ' + JSON.stringify({ width, failures: 5, duplicateMessages: 0, successRefetches: 0 }));
          activeUser = { ...user, user_id: 'another-fixture', name: 'Outra pessoa' };
          await page.evaluate(() => { localStorage.setItem('sirius_session_token', 'other-fixture-token'); window.dispatchEvent(new StorageEvent('storage', { key: 'sirius_session_token' })); });
          await page.getByText('Resposta de teste Pedido de teste network', { exact: true }).waitFor({ state: 'hidden' });
          await page.waitForTimeout(200);
          assert.equal(await page.getByText('Conversa sintética desta conta', { exact: true }).count(), 0);
          activeUser = user;
        }
        if (name === 'studies') {
          const nav = page.getByRole('navigation', { name: 'Áreas de estudos' });
          await nav.getByRole('button', { name: 'Preparações', exact: true }).click();
          await page.getByRole('button', { name: 'Nova preparação' }).click();
          await page.getByRole('dialog').waitFor();
          await page.getByLabel('Tipo de preparação', { exact: true }).selectOption('certification');
          await page.keyboard.press('Escape');
          await nav.getByRole('button', { name: 'Biblioteca', exact: true }).click();
          await page.getByText('Resumo de interpretação', { exact: true }).waitFor();
          await nav.getByRole('button', { name: 'Desempenho', exact: true }).click();
          await page.getByRole('heading', { name: 'Domínio e banco de erros' }).waitFor();
          assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
          await page.screenshot({ path: path.join(output, `studies-performance-${width}.png`) });
        }
        if (name === 'session') {
          await page.getByLabel('Resolvidas', { exact: true }).fill('10');
          await page.getByLabel('Acertos', { exact: true }).fill('5');
          await page.getByRole('button', { name: 'Registrar resultado deste assunto' }).click();
          await page.getByText(/Resultado salvo/).waitFor();
          await page.getByText('Fila de revisão · 1 assuntos').click();
          await page.getByText(/último resultado: 5\/10/).waitFor();
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
