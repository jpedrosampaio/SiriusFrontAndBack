
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { AgentMessageDetails } from './AgentControls';
import { cacheKey } from '@/lib/query-cache';
const API = `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000'}/api/ai`;
const button = 'rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm hover:border-sky-500 disabled:opacity-40';
const clock = v => `${String(Math.floor(v / 60)).padStart(2, '0')}:${String(v % 60).padStart(2, '0')}`;
const duration = v => v >= 60 ? `${Math.floor(v / 60)}h${v % 60 ? String(v % 60).padStart(2, '0') : ''}` : `${v} min`;
export default function DailyWorkspace() {
  const [opened, setOpened] = useState(false);
  const [busy, setBusy] = useState(false), [feedbackError, setFeedbackError] = useState('');
  const daily = useQuery({ queryKey: cacheKey('daily-plan'), queryFn: async ({ signal }) => (await axios.get(`${API}/daily`, { signal, timeout: 20000 })).data });
  const suggestions = useQuery({ queryKey: cacheKey('agent-suggestions'), enabled: opened, queryFn: async ({ signal }) => {
    const [a, i] = await Promise.all([axios.get(`${API}/actions`, { signal, timeout: 20000 }), axios.get(`${API}/insights`, { signal, timeout: 20000 })]);
    return { actions: a.data, insights: i.data };
  } });
  const plan = daily.data?.plan;
  const items = [...(plan?.blocks || []).map(b => ({ ...b, key: b.task_id, fixed: false })), ...(daily.data?.commitments || []).filter(c => c.date === plan?.date).map(c => ({ ...c, key: c.event_id, fixed: true }))].sort((a, b) => a.start_minute - b.start_minute);
  const run = async (id, feedback) => {
    setBusy(true); setFeedbackError('');
    try { await axios.post(`${API}/insights/${id}/feedback`, { feedback }); await suggestions.refetch(); }
    catch { setFeedbackError('Não foi possível salvar sua avaliação. Tente novamente.'); }
    finally { setBusy(false); }
  };
  return <section aria-label="Seu dia com Sirius" className="mb-8 space-y-4 rounded-xl border border-slate-700/60 p-4">
    <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-medium">Seu dia</h2><button className={button} disabled={daily.isFetching} onClick={() => daily.refetch()}>{daily.isFetching ? 'Organizando…' : 'Reorganizar meu dia'}</button></div>
    {daily.isPending && <p role="status" className="text-sm text-slate-400">Consultando sua agenda e prioridades…</p>}
    {daily.isError && <p role="alert" className="text-sm text-amber-300">Não foi possível atualizar seu dia. {daily.data ? 'A última prévia continua visível.' : 'Tente reorganizar novamente.'}</p>}
    {plan && <>
      <p className="text-sm text-sky-200">Disponibilidade estimada hoje: {duration(plan.available_minutes ?? plan.remaining_minutes)}</p>
      <p className="text-xs text-slate-400">Janela estimada de 08h a 18h, descontando os compromissos registrados. Tarefas sem duração usam 30 minutos. Confira se os horários combinam com sua rotina.</p>
      <ol className="space-y-2">{items.map((item, index) => <li key={item.key} className="rounded-lg bg-slate-900/70 p-3 text-sm">
        <span className="text-xs text-sky-300">{clock(item.start_minute)}–{clock(item.end_minute)} · {item.fixed ? 'Compromisso fixo' : index === 0 ? 'Primeiro passo' : 'Depois'}</span>
        <p className="mt-1 break-words">{item.title}</p>{!item.fixed && <p className="text-xs text-slate-400">{item.duration_minutes} min{item.duration_estimated ? ' · duração estimada' : ''}</p>}
      </li>)}</ol>
      {!items.length && <p className="text-sm text-slate-400">Nenhuma tarefa ou compromisso registrado para hoje. <Link to="/tasks" className="underline">Organizar prioridades</Link></p>}
      {plan.unscheduled?.length > 0 && <p className="text-sm text-amber-200">{plan.unscheduled.length} tarefa(s) não couberam nos horários livres.</p>}
      <p className="text-xs text-slate-400">Prévia determinística: nenhum horário ou tarefa foi alterado.</p>
      <Link to="/calendar" className="inline-block text-xs text-sky-300 underline">Conferir minha agenda</Link>
    </>}
    <details onToggle={e => setOpened(e.currentTarget.open)}><summary className="cursor-pointer text-sm text-slate-300">Propostas e sugestões do Sirius</summary>
      {suggestions.isPending && opened && <p role="status" className="py-3 text-xs">Carregando sugestões…</p>}
      {suggestions.isError && <p role="alert" className="text-sm text-amber-300">Não foi possível carregar as sugestões. <button onClick={() => suggestions.refetch()} className="underline">Tentar novamente</button></p>}
      <AgentMessageDetails message={{ actions: suggestions.data?.actions || [] }} />
      {suggestions.data?.actions?.length === 0 && <p className="py-3 text-xs text-slate-400">Nenhuma proposta registrada ainda.</p>}
      {feedbackError && <p role="alert" className="text-amber-300">{feedbackError}</p>}
      {suggestions.data?.insights?.map(i => <div className="border-t border-slate-800 pt-3 space-y-2" key={i.insight_id}><p>{i.title}</p><Link to={i.link} className="text-sm text-sky-400">Ver módulo</Link><div className="flex flex-wrap gap-2">{[['helpful', 'Útil'], ['dismiss', 'Dispensar'], ['snooze', 'Adiar um dia'], ['never', 'Não sugerir mais']].map(([feedback, label]) => <button key={feedback} className={button} disabled={busy} onClick={() => run(i.insight_id, feedback)}>{label}</button>)}</div></div>)}
    </details>
  </section>;
}
