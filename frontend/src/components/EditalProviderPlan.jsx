import { useRef, useState } from 'react';
import { ArrowRight, Check, ShieldCheck } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription, AlertDialogFooter, AlertDialogCancel } from '@/components/ui/alert-dialog';

const diagnosticCases = { text: 'Texto simples', json: 'JSON mínimo', inventory: 'Contrato de inventário' };
const diagnosticButtons = { text: 'Testar IA sem PDF (1 chamada)', json: 'Testar JSON mínimo (1 chamada)', inventory: 'Testar contrato sem PDF (1 chamada)' };
export default function EditalProviderPlan({ plan, diagnostics = [], state, command, pending, contextKey }) {
  const [limit, setLimit] = useState('');
  const [diagnosticCase, setDiagnosticCase] = useState('text');
  const [confirmation, setConfirmation] = useState(null);
  const submitting = useRef(false);
  if (!plan) return null;
  const proposed = Number(limit || Math.max(state.budget.provider_limit, plan.minimum_total_attempts));
  const valid = Number.isInteger(proposed) && proposed >= state.budget.reserved_attempts + 1 && proposed <= plan.maximum_limit;
  const paused = ['waiting_provider', 'quota_paused', 'recoverable_failure', 'cancelled'].includes(state.status);
  const cooling = !!state.retry_at && Date.parse(state.retry_at) > Date.now();
  const accepted = state.error_kind === 'provider_probe_accepted';
  const lastCase = state.provider_approval?.diagnostic_case;
  const failedProbe = !accepted && !!diagnosticCases[lastCase];
  const nextCase = failedProbe ? lastCase : accepted ? (lastCase === 'text' ? 'json' : null) : 'text';
  const offered = plan.diagnostic_cases?.includes(nextCase);
  const diagnosticDisabled = pending || cooling || state.budget.reserved_attempts >= state.budget.provider_limit;
  const extractionUnavailable = Array.isArray(plan.extraction_route) && !plan.extraction_route.length;
  const confirmationAllowed = !!confirmation && confirmation.key === contextKey && paused && !pending && !cooling &&
    (confirmation?.payload.diagnostic_case
      ? !diagnosticDisabled && plan.diagnostic_cases?.includes(confirmation.payload.diagnostic_case)
      : !extractionUnavailable && state.budget.reserved_attempts < plan.maximum_limit &&
        (confirmation?.payload.mode !== 'full' || plan.live_provider_validated));
  const confirm = async () => {
    if (!confirmationAllowed || submitting.current) return;
    submitting.current = true;
    const payload = confirmation.payload;
    setConfirmation(null);
    try { await command('resume', payload); }
    finally { submitting.current = false; }
  };
  const authorizeDiagnostic = kind => {
    if (diagnosticDisabled || !plan.diagnostic_cases?.includes(kind)) return;
    setConfirmation({ key: contextKey, title: 'Confirmar diagnóstico sem PDF',
      message: `Autorizar UMA chamada real de diagnóstico: ${diagnosticCases[kind]}, no Gemini 3.8 Flash? Usará apenas conteúdo sintético fixo, sem texto do PDF, e consumirá uma tentativa dentro do limite atual de ${state.budget.provider_limit}. Não valida cargos nem libera os demais lotes.`,
      label: 'Autorizar uma chamada', payload: { mode: 'pilot', diagnostic_case: kind } });
  };
  const authorize = mode => {
    const total = mode === 'pilot' ? Math.max(state.budget.provider_limit, state.budget.reserved_attempts + 1) : proposed;
    const message = mode === 'pilot'
      ? `Autorizar um lote piloto com no máximo uma chamada real de IA? ${total > state.budget.provider_limit ? `Isso aumenta explicitamente o limite total de ${state.budget.provider_limit} para ${total} tentativas. ` : ''}Ele usará o texto já salvo e pausará antes dos demais lotes. A proposta será validada localmente e continuará parcial.`
      : `Conferi o piloto e autorizo os lotes pendentes com limite total de ${total} tentativas, incluindo as ${state.budget.reserved_attempts} já reservadas. A previsão mínima conhecida é ${plan.minimum_total_attempts}; etapas ainda desconhecidas e novas falhas podem exigir outra confirmação.`;
    if (pending || cooling || extractionUnavailable || !paused || total > plan.maximum_limit ||
      (mode === 'full' && (!plan.live_provider_validated || !valid || total < plan.minimum_total_attempts))) return;
    setConfirmation({ key: contextKey, title: mode === 'pilot' ? 'Confirmar lote piloto' : 'Confirmar retomada dos lotes',
      message, label: mode === 'pilot' ? 'Autorizar uma chamada' : 'Autorizar retomada',
      payload: { mode, ...(total > state.budget.provider_limit ? { provider_limit: total } : {}) } });
  };
  return <aside className="edital-surface space-y-5" aria-label="Previsão e autorização da IA">
    <div className="flex items-center justify-between gap-3"><p className="edital-kicker">Próximo passo</p><span className="rounded-full border border-white/10 px-2.5 py-1 text-[10px] text-zinc-400">{paused ? 'Aguardando sua decisão' : state.status === 'processing' ? 'Em andamento' : 'Conferência'}</span></div>
    {plan.extraction_route?.length > 0 && <p className="break-words text-xs leading-relaxed text-zinc-400">Rota da próxima tentativa: {plan.extraction_route.map(model => `${model.provider} / ${model.model}`).join(' → ')}. Disponibilidade e cota serão verificadas ao executar.</p>}
    {extractionUnavailable && <p role="status" className="text-xs leading-relaxed text-amber-200">Configure um modelo compatível para a extração antes de autorizar uma tentativa.</p>}
    {cooling && <p role="status" className="text-xs leading-relaxed text-amber-200">Nova tentativa a partir de {new Date(state.retry_at).toLocaleString('pt-BR')}. A cota ainda não está confirmada.</p>}
    {paused && !plan.live_provider_validated ? <>
      <div><h2 className="text-xl font-semibold tracking-tight text-zinc-100">{failedProbe ? 'A IA ainda precisa de correção' : !offered ? 'Confira um trecho do seu edital' : accepted ? 'Vamos conferir o formato da resposta' : 'Vamos testar a resposta da IA'}</h2>
        <p className="mt-3 text-sm leading-relaxed text-zinc-400">{failedProbe ? 'O diagnóstico também não foi concluído. Confira o motivo salvo e aguarde orientação antes de repetir a solicitação.' : accepted && !offered ? 'O último teste técnico foi aceito. Agora, um lote do seu documento precisa passar pela validação antes de liberar os demais.' : accepted ? 'O último diagnóstico técnico foi aceito. Cada próximo teste exige uma nova confirmação e pausa ao terminar.' : !offered ? 'Autorize apenas um lote do documento salvo. Ele precisa passar pelas validações de conteúdo e fontes antes de continuar.' : state.error_kind === 'invalid_request' ? 'A última tentativa com o edital foi recusada. Antes de repetir, verifique se a IA aceita uma solicitação curta sem o documento.' : 'Comece com uma solicitação curta à IA. O texto extraído permanece salvo enquanto você confere a conexão.'}</p></div>
      {accepted && <p role="status" className="flex items-start gap-2 text-xs leading-relaxed text-lime-200"><Check size={15} className="mt-0.5 shrink-0" />{diagnosticCases[lastCase] || 'Diagnóstico'} aceito. Isso não confirma cargos nem libera o edital.</p>}
      {offered ? <div className="space-y-3"><p className="text-xs text-zinc-300">{diagnosticCases[nextCase]} · Gemini 3.8 Flash · dados sintéticos · sem texto do PDF</p><Button data-testid="edital-next-action" className="edital-primary w-full justify-between gap-3 px-4 py-3" disabled={diagnosticDisabled || failedProbe} onClick={() => authorizeDiagnostic(nextCase)}>{diagnosticButtons[nextCase]}<ArrowRight size={16} className="shrink-0" /></Button><p className="text-[11px] leading-relaxed text-zinc-500">Usa uma tentativa do orçamento atual. Não analisa o documento, não gera cargos e não executa os demais lotes.</p></div>
        : <Button data-testid="edital-next-action" className="edital-primary" disabled={pending || cooling || extractionUnavailable || state.budget.reserved_attempts >= plan.maximum_limit} onClick={() => authorize('pilot')}>Executar lote piloto (1 chamada)</Button>}
      {(plan.diagnostic_cases?.length > 0 || offered) && <details className="border-t border-white/[0.07] pt-4"><summary className="cursor-pointer text-xs text-zinc-500 hover:text-zinc-200">Outras opções de diagnóstico e teste do edital</summary><div className="mt-4 space-y-5">
        {plan.diagnostic_cases?.length > 0 && <div className="space-y-3"><label className="block text-xs text-zinc-400">Tipo de diagnóstico<select aria-label="Tipo de diagnóstico" value={diagnosticCase} onChange={e => setDiagnosticCase(e.target.value)} className="mt-2 w-full min-w-0 rounded-lg border border-white/10 bg-zinc-950 p-2.5 text-zinc-200">{plan.diagnostic_cases.filter(kind => diagnosticCases[kind]).map(kind => <option key={kind} value={kind}>{diagnosticCases[kind]}</option>)}</select></label><Button variant="outline" className="max-w-full whitespace-normal" disabled={diagnosticDisabled} onClick={() => authorizeDiagnostic(diagnosticCase)}>Executar diagnóstico (1 chamada, sem PDF)</Button></div>}
        {offered && <div className="space-y-3 border-t border-white/[0.07] pt-4"><p className="text-xs leading-relaxed text-zinc-400">O lote piloto usa o texto e o contrato completos do edital. É diferente do diagnóstico acima; repetir a mesma solicitação recusada pode consumir outra tentativa sem resolver o bloqueio.</p><Button variant="outline" className="max-w-full whitespace-normal" disabled={pending || cooling || state.budget.reserved_attempts >= plan.maximum_limit} onClick={() => authorize('pilot')}>Executar lote piloto (1 chamada)</Button></div>}
      </div></details>}
    </> : plan.live_provider_validated && paused ? <>
      <div><h2 className="text-xl font-semibold tracking-tight text-zinc-100">Seu piloto foi validado</h2><p className="mt-3 text-sm leading-relaxed text-zinc-400">Confira a previsão antes de autorizar os lotes restantes. O processamento continua parcial até a revisão das fontes.</p></div>
      <label className="block text-xs text-zinc-400">Limite total a autorizar<Input aria-label="Limite total a autorizar" className="mt-2 max-w-40 border-white/10 bg-zinc-950" type="number" min={state.budget.reserved_attempts + 1} max={plan.maximum_limit} value={limit || proposed} onChange={event => setLimit(event.target.value)} /></label>
      <Button className="edital-primary max-w-full whitespace-normal" disabled={pending || cooling || extractionUnavailable || !valid || proposed < plan.minimum_total_attempts} onClick={() => authorize('full')}>Autorizar e retomar lotes pendentes</Button>
    </> : <div><h2 className="text-xl font-semibold tracking-tight text-zinc-100">{state.status === 'processing' ? 'Analisando seu edital' : 'Continue a conferência'}</h2><p className="mt-3 text-sm leading-relaxed text-zinc-400">{state.status === 'processing' ? 'Os resultados são salvos a cada lote. Você pode acompanhar as etapas ao lado.' : 'Escolha o cargo, consulte as fontes e confira o conteúdo antes de criar seu programa de estudos.'}</p></div>}
    <div className="space-y-3 border-t border-white/[0.07] pt-4">
      <div className="flex items-center justify-between gap-3 text-xs"><span className="text-zinc-500">Orçamento atual</span><span className="tabular-nums text-zinc-300">{state.budget.reserved_attempts} / {state.budget.provider_limit} tentativas</span></div>
      {plan.extension_required && <p role="status" className="text-xs leading-relaxed text-amber-200/90">O plano completo exige ao menos {plan.minimum_total_attempts} tentativas, acima do limite atual. A ampliação depende de outra confirmação.</p>}
      <details><summary className="cursor-pointer text-xs text-zinc-500 hover:text-zinc-200">Ver previsão completa de etapas e chamadas</summary><div className="mt-3 space-y-2 text-xs leading-relaxed text-zinc-400"><p>Mínimo total conhecido: {plan.minimum_total_attempts}, incluindo as tentativas anteriores. Restam ao menos {plan.minimum_remaining_attempts} chamadas: {plan.stages.inventory} de descoberta, {plan.stages.scope} de associação, {plan.stages.detail} de conteúdo e {plan.stages.verify} de comparação.</p><p>A previsão não inclui novas falhas ou fallback e não estima faturamento. {plan.unknown_stages.length > 0 ? 'Associação e conteúdo ainda podem exigir etapas não conhecidas.' : 'Novas subdivisões podem exigir revisão do orçamento.'} O limite não será aumentado automaticamente.</p><p>O consumo inclui somente tokens reportados pelo provedor; {state.budget.usage_incomplete ? 'há tentativas com consumo desconhecido.' : 'não representa faturamento.'}</p></div></details>
    </div>
    {diagnostics.some(item => item.provider_probes?.length) && <details><summary className="cursor-pointer text-xs text-zinc-500 hover:text-zinc-200">Resultados dos diagnósticos técnicos</summary><ul className="mt-3 space-y-2 text-xs text-zinc-400">{diagnostics.flatMap(item => (item.provider_probes || []).map((entry, index) => <li key={`${item.unit_id}:${index}`}>{diagnosticCases[entry.case] || 'Diagnóstico'} · {entry.outcome === 'accepted' ? 'solicitação aceita; não valida cargos' : 'não concluído'}{entry.http_status ? ` · HTTP ${entry.http_status}` : ''}</li>))}</ul></details>}
    <p className="flex items-center gap-2 text-[11px] text-zinc-500"><ShieldCheck size={14} className="shrink-0" />Nenhum teste é executado sem sua confirmação.</p>
    <AlertDialog open={!!confirmation && confirmation.key === contextKey} onOpenChange={open => { if (!open) setConfirmation(null); }}>
      <AlertDialogContent overlayStyle={{ animation: 'none' }} style={{ animation: 'none' }} className="w-[calc(100%_-_2rem)] max-h-[85dvh] overflow-y-auto rounded-2xl border-white/10 bg-zinc-900 text-zinc-100">
        <AlertDialogHeader>
          <AlertDialogTitle>{confirmation?.title}</AlertDialogTitle>
          <AlertDialogDescription className="leading-relaxed text-zinc-400">{confirmation?.message}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancelar</AlertDialogCancel>
          <Button className="bg-lime-200 text-zinc-950 hover:bg-lime-100" disabled={!confirmationAllowed} onClick={confirm}>{confirmation?.label}</Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </aside>;
}
