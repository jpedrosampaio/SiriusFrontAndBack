// Account transitions exercise the built product; all APIs/providers are synthetic.
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const root = path.join(process.cwd(), 'build');
const server = http.createServer((req, res) => {
  let file = path.join(root, new URL(req.url, 'http://localhost').pathname);
  if (!file.startsWith(root + path.sep)) { res.writeHead(403); return res.end(); }
  if (!fs.existsSync(file) || fs.statSync(file).isDirectory()) file = path.join(root, 'index.html');
  res.setHeader('Content-Type', ({ '.js': 'application/javascript', '.css': 'text/css', '.html': 'text/html' })[path.extname(file)] || 'application/octet-stream');
  fs.createReadStream(file).pipe(res);
});
const respond = (route, data, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
const aliceMemory = { memory_id: '11111111-1111-4111-8111-111111111111', category: 'fact', content: 'Alice private memory', version: 'a'.repeat(64), provenance: { origin: 'user_declared' } };

(async () => {
  await new Promise(resolve => server.listen(4191, '127.0.0.1', resolve));
  const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
  let lastPage;
  try {
    fs.mkdirSync('test-results/integrated-hardening', { recursive: true });
    for (const width of [320, 390, 768, 1024, 1440]) {
      const context = await browser.newContext({ viewport: { width, height: 900 }, serviceWorkers: 'block', reducedMotion: 'reduce' });
      await context.addInitScript(() => {
        if (!localStorage.getItem('hardening-initialized')) {
          localStorage.setItem('hardening-initialized', 'true');
          localStorage.setItem('sirius_session_token', 'alice');
          localStorage.setItem('sirius_onboarding_complete', 'true');
        }
      });
      const page = await context.newPage(); lastPage = page;
      const errors = [], requests = [], vendorRequests = []; page.on('pageerror', error => errors.push(error.message));
      let holdMemory = false, releaseMemory, memoryStarted, homeFailure = false;
      const memoryWaiting = new Promise(resolve => { memoryStarted = resolve; });
      const memoryGate = new Promise(resolve => { releaseMemory = resolve; });
      await context.route('**/*', async route => {
        const request = route.request(), url = new URL(request.url()), p = url.pathname;
        if (/^(?:assets\.emergent\.sh|cdn\.tailwindcss\.com)$/.test(url.hostname) || url.hostname.endsWith('.posthog.com')) {
          vendorRequests.push(url.hostname); return route.abort();
        }
        if (!p.startsWith('/api/')) return url.hostname === '127.0.0.1' ? route.continue() : route.abort();
        requests.push(p);
        const owner = request.headers().authorization?.replace('Bearer ', '');
        if (!['alice', 'bob'].includes(owner)) return respond(route, { detail: 'Expired synthetic session' }, 401);
        if (p === '/api/auth/me') return respond(route, { user_id: owner, name: owner === 'alice' ? 'Alice' : 'Bob', rank: 'Recruta', timezone: 'America/Sao_Paulo' });
        if (p === '/api/command/home') return respond(route, homeFailure ? { detail: 'Synthetic unavailable' } : {
          date: '2026-10-13', timezone: 'America/Sao_Paulo', next_action: null, today: [], today_count: 0,
          attention: [], areas: [], warnings: [], unscheduled_count: 0,
        }, homeFailure ? 503 : 200);
        if (p === '/api/command/memory') {
          if (owner === 'alice' && holdMemory) { memoryStarted(); await memoryGate; }
          return respond(route, owner === 'alice' ? [aliceMemory] : []);
        }
        if (p === '/api/ai/conversation') return respond(route, { messages: [] });
        if (p === '/api/ai/conversations') return respond(route, []);
        if (p === '/api/ai/status') return respond(route, { agent: true });
        if (p === '/api/ai/preferences') return respond(route, { event_automation: { enabled: false } });
        return respond(route, []);
      });
      await page.goto('http://127.0.0.1:4191/dashboard');
      await page.getByRole('heading', { name: 'Seu próximo passo, Alice', exact: true }).waitFor();
      assert.equal(requests.filter(p => p === '/api/auth/me').length, 1, 'Profile requests must remain deduplicated');
      assert.equal(requests.filter(p => p === '/api/command/home').length, 1);
      const memoryButton = page.getByRole('button', { name: 'Memória explícita', exact: true });
      await memoryButton.click(); await page.getByText('Alice private memory', { exact: true }).waitFor();
      holdMemory = true;
      await page.evaluate(() => window.dispatchEvent(new Event('sirius-data-changed')));
      await Promise.race([memoryWaiting, new Promise((_, reject) => setTimeout(() => reject(new Error('Memory refresh did not start')), 10000))]);
      await page.evaluate(() => sessionStorage.setItem('sirius-conversation', 'alice-private-conversation'));
      // Real storage event from another same-origin tab, not a synthetic dispatch.
      const otherTab = await context.newPage(); await otherTab.goto('http://127.0.0.1:4191/');
      await otherTab.evaluate(() => localStorage.setItem('sirius_session_token', 'bob'));
      await page.getByRole('heading', { name: 'Seu próximo passo, Bob', exact: true }).waitFor();
      await page.bringToFront();
      releaseMemory();
      await memoryButton.click(); await page.getByText('Nenhuma memória explícita cadastrada.', { exact: true }).waitFor();
      assert.equal(await page.getByText('Alice private memory', { exact: true }).count(), 0);
      assert.equal(await page.evaluate(() => sessionStorage.getItem('sirius-conversation')), null);
      assert.equal(await page.evaluate(() => localStorage.getItem('sirius_session_token')), 'bob');

      const launcher = page.getByRole('button', { name: 'Abrir assistente Sirius', exact: true });
      await launcher.click();
      const close = page.getByRole('button', { name: 'Fechar assistente', exact: true });
      await close.waitFor(); const bounds = await close.boundingBox();
      assert.ok(bounds.width >= 44 && bounds.height >= 44, 'Assistant close touch target must be at least 44px');
      const contrast = await page.getByText('Assistente completo do Sirius.', { exact: false }).evaluate(node => {
        const rgb = value => value.match(/[\d.]+/g).map(Number);
        const foreground = rgb(getComputedStyle(node).color);
        let background, parent = node;
        while (parent) {
          const value = rgb(getComputedStyle(parent).backgroundColor);
          if (value.length === 3 || value[3] === 1) { background = value; break; }
          parent = parent.parentElement;
        }
        if (!background) throw new Error('Opaque assistant background not found');
        const luminance = color => color.slice(0, 3).map(channel => channel / 255).map(channel => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4).reduce((sum, channel, i) => sum + channel * [0.2126, 0.7152, 0.0722][i], 0);
        const a = luminance(foreground), b = luminance(background);
        return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
      });
      assert.ok(contrast >= 4.5, `Assistant explanatory text contrast: ${contrast.toFixed(2)} must be >=4.5`);
      await close.click(); await page.waitForFunction(() => document.activeElement?.getAttribute('aria-label') === 'Abrir assistente Sirius');
      await page.keyboard.press('Control+k');
      await page.getByRole('combobox', { name: 'Buscar registros e ações' }).waitFor();
      await page.keyboard.press('Escape');
      await page.getByRole('combobox', { name: 'Buscar registros e ações' }).waitFor({ state: 'hidden' });
      assert.equal(await page.getByRole('combobox', { name: 'Buscar registros e ações' }).count(), 0);
      await page.waitForFunction(() => document.activeElement?.getAttribute('aria-label') === 'Abrir assistente Sirius', null, { timeout: 5000 });
      await page.keyboard.press('Control+k');
      await page.getByRole('combobox', { name: 'Buscar registros e ações' }).fill('Perguntar ao Sirius');
      await page.getByRole('option', { name: 'Perguntar ao Sirius', exact: true }).click();
      await close.waitFor(); await close.click();
      await page.waitForFunction(() => document.activeElement?.getAttribute('aria-label') === 'Abrir assistente Sirius');
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      await page.screenshot({ path: `test-results/integrated-hardening/session-${width}.png`, fullPage: true });

      homeFailure = true; await page.reload();
      await page.getByRole('alert').filter({ hasText: 'Não foi possível atualizar o Command Center.' }).waitFor();
      homeFailure = false; await page.getByRole('button', { name: 'Tentar novamente', exact: true }).click();
      await page.getByRole('heading', { name: 'Seu próximo passo, Bob', exact: true }).waitFor();
      await otherTab.evaluate(() => localStorage.removeItem('sirius_session_token'));
      await page.waitForURL('**/login');
      assert.equal(await page.getByText('Alice private memory', { exact: true }).count(), 0);
      const viewport = await page.locator('meta[name="viewport"]').getAttribute('content');
      assert(!/user-scalable\s*=\s*(?:no|0)|maximum-scale\s*=\s*1(?:\s|,|$)/i.test(viewport), 'Mobile zoom must remain available');
      assert.deepEqual(vendorRequests, [], 'Legacy editor/telemetry scripts must not run in personal views');
      assert.deepEqual(errors, []);
      await context.close(); console.log(`Integrated hardening ${width}: passed`);
    }
  } catch (error) {
    if (lastPage && !lastPage.isClosed()) {
      console.error(await lastPage.evaluate(() => ({ active: document.activeElement?.tagName, label: document.activeElement?.getAttribute('aria-label'), foreground: document.hasFocus(), panel: !!document.getElementById('sirius-assistant-panel') })));
      await lastPage.screenshot({ path: 'test-results/integrated-hardening/failure.png', fullPage: true });
    }
    throw error;
  } finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
})().catch(error => { console.error(error); process.exitCode = 1; });
