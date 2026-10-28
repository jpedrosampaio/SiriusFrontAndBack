import { Check, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { analysisStages, stageProgress } from '@/lib/edital-diagnostics';
import { EDITAL_PIPELINE_STATUSES } from '@/lib/edital-analysis';
import EditalProviderDiagnostic from '@/components/EditalProviderDiagnostic';

export default function EditalProgressOverview({ data, pending, fetching, onRefresh }) {
  const state = data.manifest;
  const title = state.error_kind === 'evidence_invalid' ? 'Resposta rejeitada na conferência documental' : state.error_kind === 'provider_probe_accepted' ? 'Diagnóstico técnico aceito · análise pausada' : state.error_kind === 'pilot_review_required' ? 'Piloto validado · aguardando sua autorização' : state.error_kind === 'provider_approval_required' ? 'Aguardando autorização para homologar a IA' : EDITAL_PIPELINE_STATUSES[state.status];
  const paused = ['waiting_provider', 'quota_paused', 'recoverable_failure', 'cancelled'].includes(state.status);
  const failure = paused && state.error_kind && !['pilot_review_required', 'provider_approval_required', 'pilot_limit'].includes(state.error_kind)
    && data.diagnostics?.find(item => item.error_kind === state.error_kind && item.status !== 'completed');
  return <div className="edital-surface h-full space-y-5">
    <div className="flex items-start justify-between gap-3"><div><p className="edital-kicker">Seu documento</p><h2 className="mt-2 text-sm font-medium leading-relaxed text-zinc-200">{title}</h2></div><Button size="icon" variant="ghost" aria-label="Atualizar andamento" title="Atualizar andamento" disabled={pending || fetching} onClick={onRefresh} className="shrink-0 text-zinc-400 hover:text-white"><RefreshCw size={15} className={fetching ? 'animate-spin motion-reduce:animate-none' : ''} /></Button></div>
    <dl className="grid grid-cols-3 gap-3 border-y border-white/[0.07] py-4">{[
      [state.source.pages, 'Páginas extraídas'], [state.inventory.roles.length, 'Cargos identificados'],
      [`${state.budget.reserved_attempts}/${state.budget.provider_limit}`, 'Tentativas da análise'],
    ].map(([value, label]) => <div key={label} className="min-w-0"><dd className="text-xl font-semibold tracking-tight tabular-nums text-zinc-100">{value}</dd><dt className="mt-1 text-[11px] leading-relaxed text-zinc-400">{label}</dt></div>)}</dl>
    <ol aria-label="Etapas da análise" className="space-y-4">{analysisStages.map(([kind, label], index) => {
      const { done, total, pending: remaining } = stageProgress(data.progress, kind), complete = total > 0 && done === total;
      return <li key={kind} className="flex items-start gap-3"><span className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[10px] ${complete ? 'bg-lime-200/10 text-lime-200' : total ? 'bg-white/10 text-zinc-200' : 'border border-white/10 text-zinc-500'}`}>{complete ? <Check size={13} /> : String(index + 1).padStart(2, '0')}</span><div className="min-w-0 flex-1"><h3 className={`text-xs font-medium ${total ? 'text-zinc-200' : 'text-zinc-500'}`}>{label}</h3><p className="mt-1 text-[11px] leading-relaxed text-zinc-500">{done} de {total} lotes concluídos · {remaining} pendentes</p>{total > 0 && <div aria-hidden="true" className="mt-2 h-0.5 overflow-hidden rounded-full bg-white/[0.06]"><div className="h-full bg-lime-200/70 motion-safe:transition-[width]" style={{ width: `${done / total * 100}%` }} /></div>}{!total && <p className="sr-only">Nenhum lote planejado nesta etapa</p>}</div></li>;
    })}</ol>
    {failure && <EditalProviderDiagnostic key={`${failure.unit_id}:${failure.reference}`} item={failure} />}
    <p className="text-[11px] leading-relaxed text-zinc-500">{state.status === 'processing' ? 'O progresso é salvo a cada lote.' : 'Progresso salvo. Você pode sair e voltar sem reenviar o PDF.'}</p>
  </div>;
}
