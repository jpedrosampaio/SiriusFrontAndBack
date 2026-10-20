import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

export default function EditalProviderPlan({ plan, state, command, pending }) {
  const [limit, setLimit] = useState('');
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
  return <div className="rounded-xl border border-blue-400/30 p-3 space-y-3 text-sm" aria-label="Previsão e autorização da IA">
    <h3 className="font-semibold">Previsão de chamadas e retomada</h3>
    <p>Mínimo de {plan.minimum_remaining_attempts} chamadas restantes: {plan.stages.inventory} de descoberta, {plan.stages.scope} de associação, {plan.stages.detail} de conteúdo e {plan.stages.verify} de comparação.</p>
    <p>Total mínimo conhecido: {plan.minimum_total_attempts} tentativas, incluindo as já reservadas. Limite autorizado: {state.budget.provider_limit}.</p>
    <p className="text-xs text-slate-400">A previsão não inclui novas falhas ou fallback e não estima faturamento. {plan.unknown_stages.length > 0 ? 'Associações e/ou conteúdo do cargo ainda dependem das próximas etapas; o custo completo permanece desconhecido.' : 'Novas subdivisões podem exigir revisão do orçamento.'} Lotes e tentativas anteriores serão preservados.</p>
    {plan.extension_required && <p role="status" className="text-amber-200">O plano conhecido excede o limite atual. Uma extensão exige sua confirmação; o limite não será aumentado automaticamente.</p>}
    {!plan.live_provider_validated && <p className="text-amber-200">Aguardando homologação do provedor com um lote pequeno. Validação local do schema não confirma aceitação pelo modelo real.</p>}
    {paused && <div className="space-y-3">
      {!plan.live_provider_validated && <Button disabled={pending || cooling || state.budget.reserved_attempts >= plan.maximum_limit} onClick={() => authorize('pilot')}>Executar lote piloto (1 chamada)</Button>}
      {plan.live_provider_validated && <>
        <label className="block text-xs">Limite total a autorizar<Input aria-label="Limite total a autorizar" className="mt-1 max-w-40" type="number" min={state.budget.reserved_attempts + 1} max={plan.maximum_limit} value={limit || proposed} onChange={event => setLimit(event.target.value)} /></label>
        <Button disabled={pending || cooling || !valid || proposed < plan.minimum_total_attempts} onClick={() => authorize('full')}>Autorizar e retomar lotes pendentes</Button>
      </>}
      <p className="text-xs text-slate-400">Retomada usa a análise existente. Nenhum novo upload é necessário.</p>
    </div>}
  </div>;
}
