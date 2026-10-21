import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

const diagnosticCases = { text: 'Texto simples', json: 'JSON mínimo', inventory: 'Contrato de inventário' };
export default function EditalProviderPlan({ plan, diagnostics = [], state, command, pending }) {
  const [limit, setLimit] = useState('');
  const [diagnosticCase, setDiagnosticCase] = useState('text');
  if (!plan) return null;
  const proposed = Number(limit || Math.max(state.budget.provider_limit, plan.minimum_total_attempts));
  const valid = Number.isInteger(proposed) && proposed >= state.budget.reserved_attempts + 1 && proposed <= plan.maximum_limit;
  const paused = ['waiting_provider', 'quota_paused', 'recoverable_failure', 'cancelled'].includes(state.status);
  const cooling = !!state.retry_at && Date.parse(state.retry_at) > Date.now();
  const authorize = mode => {
    const total = mode === 'pilot' ? Math.max(state.budget.provider_limit, state.budget.reserved_attempts + 1) : proposed;
    const message = mode === 'pilot'
      ? `Autorizar um lote piloto com no máximo uma chamada real de IA? ${total > state.budget.provider_limit ? `Isso aumenta explicitamente o limite total de ${state.budget.provider_limit} para ${total} tentativas. ` : ''}Ele usará o texto já salvo e pausará antes dos demais lotes. A proposta será validada localmente e continuará parcial.`
      : `Conferi o piloto e autorizo os lotes pendentes com limite total de ${total} tentativas, incluindo as ${state.budget.reserved_attempts} já reservadas. A previsão mínima conhecida é ${plan.minimum_total_attempts}; etapas ainda desconhecidas e novas falhas podem exigir outra confirmação.`;
    if (window.confirm(message)) command('resume', { mode, ...(total > state.budget.provider_limit ? { provider_limit: total } : {}) });
  };
  return <div className="rounded-2xl border border-sky-400/20 bg-gradient-to-br from-sky-400/[0.04] to-indigo-400/[0.03] p-4 sm:p-5 space-y-4 text-sm" aria-label="Previsão e autorização da IA">
    <div><p className="mb-1 text-[11px] uppercase tracking-[0.16em] text-sky-300">Uso da inteligência artificial</p><h3 className="font-semibold text-slate-100">Previsão de chamadas e retomada</h3></div>
    <div className="grid grid-cols-2 gap-3"><div className="rounded-xl border border-slate-700/50 bg-slate-950/30 p-3"><p className="text-xl font-semibold text-slate-100">{plan.minimum_total_attempts}</p><p className="mt-1 text-xs text-slate-400">Mínimo total conhecido, incluindo tentativas anteriores</p></div><div className="rounded-xl border border-slate-700/50 bg-slate-950/30 p-3"><p className="text-xl font-semibold text-slate-100">{state.budget.provider_limit}</p><p className="mt-1 text-xs text-slate-400">Limite total autorizado</p></div></div>
    <details><summary className="cursor-pointer py-1 text-xs text-sky-200">Como esta previsão é calculada</summary><div className="mt-3 space-y-2"><p className="text-xs leading-relaxed text-slate-300">Mínimo de {plan.minimum_remaining_attempts} chamadas restantes: {plan.stages.inventory} de descoberta, {plan.stages.scope} de associação, {plan.stages.detail} de conteúdo e {plan.stages.verify} de comparação.</p>
    <p className="text-xs leading-relaxed text-slate-400">A previsão não inclui novas falhas ou fallback e não estima faturamento. {plan.unknown_stages.length > 0 ? 'Associações e/ou conteúdo do cargo ainda dependem das próximas etapas; o custo completo permanece desconhecido.' : 'Novas subdivisões podem exigir revisão do orçamento.'} Lotes e tentativas anteriores serão preservados.</p></div></details>
    {plan.extension_required && <p role="status" className="text-amber-200">O plano conhecido excede o limite atual. Uma extensão exige sua confirmação; o limite não será aumentado automaticamente.</p>}
    {!plan.live_provider_validated && <p className="text-amber-200">Aguardando homologação do provedor com um lote pequeno. Validação local do schema não confirma aceitação pelo modelo real.</p>}
    {state.error_kind === 'provider_probe_accepted' && <p role="status" className="rounded-xl border border-emerald-400/20 bg-emerald-400/5 p-3 text-emerald-200">Solicitação técnica aceita. Isso não valida cargos, não conclui lotes do edital e não libera os demais lotes.</p>}
    {paused && !plan.live_provider_validated && plan.diagnostic_cases?.length > 0 && <details className="rounded-xl border border-slate-700/60 bg-slate-950/30 p-3"><summary className="cursor-pointer text-xs text-sky-200">Diagnóstico isolado (sem texto do PDF)</summary><div className="mt-3 space-y-3">
      <p className="text-xs leading-relaxed text-slate-400">Isola a conexão, o formato JSON ou o contrato de inventário no Gemini 3.8 Flash com dados fixos sintéticos. Cada confirmação autoriza somente uma chamada real, consome o mesmo orçamento e pausa a execução. Nenhum resultado sintético vira cargo, conteúdo, pontuação ou XP.</p>
      <label className="block text-xs">Tipo de diagnóstico<select aria-label="Tipo de diagnóstico" value={diagnosticCase} onChange={e => setDiagnosticCase(e.target.value)} className="mt-2 w-full min-w-0 rounded-lg border border-slate-600 bg-slate-950 p-2 text-slate-200">{plan.diagnostic_cases.filter(kind => diagnosticCases[kind]).map(kind => <option key={kind} value={kind}>{diagnosticCases[kind]}</option>)}</select></label>
      <Button variant="outline" className="max-w-full whitespace-normal" disabled={pending || cooling || state.budget.reserved_attempts >= state.budget.provider_limit} onClick={() => window.confirm(`Autorizar UMA chamada real de diagnóstico: ${diagnosticCases[diagnosticCase]}, no Gemini 3.8 Flash? Usará apenas conteúdo sintético fixo, sem texto do PDF, e consumirá uma tentativa dentro do limite atual de ${state.budget.provider_limit}. Não valida cargos nem libera os demais lotes.`) && command('resume', { mode: 'pilot', diagnostic_case: diagnosticCase })}>Executar diagnóstico (1 chamada, sem PDF)</Button>
    </div></details>}
    {diagnostics.some(item => item.provider_probes?.length) && <details><summary className="cursor-pointer py-1 text-xs text-slate-300">Resultados dos diagnósticos técnicos</summary><ul className="mt-2 space-y-2 text-xs text-slate-400">{diagnostics.flatMap(item => (item.provider_probes || []).map((entry, index) => <li key={`${item.unit_id}:${index}`} className="rounded-lg border border-slate-700/50 p-2">{diagnosticCases[entry.case] || 'Diagnóstico'} · {entry.outcome === 'accepted' ? 'solicitação aceita; não valida cargos' : 'não concluído'}{entry.http_status ? ` · HTTP ${entry.http_status}` : ''}</li>))}</ul></details>}
    {paused && <div className="space-y-3">
      {state.error_kind === 'invalid_request' && <p className="text-xs leading-relaxed text-amber-200">Confira a configuração e o diagnóstico antes de autorizar outra tentativa. Repetir uma solicitação recusada não garante a recuperação.</p>}
      {!plan.live_provider_validated && <Button className="max-w-full whitespace-normal bg-sky-400 text-slate-950 hover:bg-sky-300" disabled={pending || cooling || state.budget.reserved_attempts >= plan.maximum_limit} onClick={() => authorize('pilot')}>Executar lote piloto (1 chamada)</Button>}
      {plan.live_provider_validated && <>
        <label className="block text-xs">Limite total a autorizar<Input aria-label="Limite total a autorizar" className="mt-1 max-w-40" type="number" min={state.budget.reserved_attempts + 1} max={plan.maximum_limit} value={limit || proposed} onChange={event => setLimit(event.target.value)} /></label>
        <Button disabled={pending || cooling || !valid || proposed < plan.minimum_total_attempts} onClick={() => authorize('full')}>Autorizar e retomar lotes pendentes</Button>
      </>}
      <p className="text-xs text-slate-400">Retomada usa a análise existente. Nenhum novo upload é necessário.</p>
    </div>}
  </div>;
}
