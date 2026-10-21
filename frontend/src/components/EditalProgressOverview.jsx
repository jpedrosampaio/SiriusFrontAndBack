import { CheckCircle2, Circle, FileCheck2, Layers3, RefreshCw, Users } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { analysisStages, stageProgress } from '@/lib/edital-diagnostics';
import { EDITAL_PIPELINE_STATUSES } from '@/lib/edital-analysis';
import EditalProviderDiagnostic from '@/components/EditalProviderDiagnostic';

export default function EditalProgressOverview({ data, pending, fetching, onRefresh }) {
  const state = data.manifest;
  const title = state.error_kind === 'provider_probe_accepted' ? 'Diagnóstico técnico aceito · análise pausada' : state.error_kind === 'pilot_review_required' ? 'Piloto validado · aguardando sua autorização' : state.error_kind === 'provider_approval_required' ? 'Aguardando autorização para homologar a IA' : EDITAL_PIPELINE_STATUSES[state.status];
  const paused = ['waiting_provider', 'quota_paused', 'recoverable_failure', 'cancelled'].includes(state.status);
  const failure = paused && state.error_kind && !['pilot_review_required', 'provider_approval_required', 'pilot_limit'].includes(state.error_kind)
    && data.diagnostics?.find(item => item.error_kind === state.error_kind && item.status !== 'completed');
  return <div className="space-y-5">
    <div className="flex flex-wrap items-start justify-between gap-4"><div className="min-w-0"><p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Estado salvo da análise</p><h2 className="mt-2 text-lg sm:text-xl font-semibold text-slate-100">{title}</h2><p className="mt-2 text-sm text-slate-400">{state.status === 'processing' ? 'Os lotes concluídos são salvos conforme o processamento avança.' : 'Você pode sair e voltar. A análise continua disponível em seus editais salvos.'}</p></div><Button variant="outline" disabled={pending || fetching} onClick={onRefresh} className="gap-2 border-slate-700 bg-slate-950/40"><RefreshCw size={14} className={fetching ? 'animate-spin motion-reduce:animate-none' : ''} />Atualizar andamento</Button></div>
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">{[
      [FileCheck2, state.source.pages, 'Páginas extraídas', 'Texto preservado para consulta'],
      [Users, state.inventory.roles.length, 'Cargos identificados', 'Propostas sujeitas à conferência'],
      [Layers3, `${state.budget.reserved_attempts} / ${state.budget.provider_limit}`, 'Tentativas da análise', 'Total reservado, não faturamento'],
    ].map(([Icon, value, label, note]) => <div key={label} className="flex items-start gap-3 rounded-xl border border-slate-700/50 bg-slate-950/50 p-4 last:col-span-2 sm:last:col-span-1"><span className="hidden rounded-lg bg-sky-400/10 p-2 text-sky-300 sm:inline-flex"><Icon size={17} /></span><div className="min-w-0"><p className="text-xl font-semibold tracking-tight text-slate-100">{value}</p><p className="mt-1 text-xs font-medium text-slate-300">{label}</p><p className="mt-1 text-[11px] text-slate-500">{note}</p></div></div>)}</div>
    <ol aria-label="Etapas da análise" className="grid grid-cols-2 gap-3 xl:grid-cols-4">{analysisStages.map(([kind, label], index) => {
      const { done, total, pending: remaining } = stageProgress(data.progress, kind), complete = total > 0 && done === total;
      return <li key={kind} className={`min-w-0 rounded-xl border p-4 ${complete ? 'border-emerald-400/20 bg-emerald-400/[0.03]' : 'border-slate-700/50 bg-slate-950/30'}`}><div className="mb-3 flex items-center justify-between gap-2"><span className="text-[11px] text-slate-500">ETAPA {index + 1}</span>{complete ? <CheckCircle2 size={16} className="text-emerald-300" /> : <Circle size={15} className="text-slate-600" />}</div><h3 className="text-sm font-medium text-slate-200">{label}</h3><p className="mt-2 text-xs leading-relaxed text-slate-400">{done} de {total} lotes concluídos · {remaining} pendentes</p><div aria-hidden="true" className="mt-3 h-1 overflow-hidden rounded-full bg-slate-800"><div className="h-full rounded-full bg-sky-400 transition-[width] duration-300 motion-reduce:transition-none" style={{ width: total ? `${done / total * 100}%` : '0%' }} /></div>{!total && <p className="mt-2 text-[11px] text-slate-500">Nenhum lote planejado nesta etapa</p>}</li>;
    })}</ol>
    {failure && <EditalProviderDiagnostic key={`${failure.unit_id}:${failure.reference}`} item={failure} />}
  </div>;
}
