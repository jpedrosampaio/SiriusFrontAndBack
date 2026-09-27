import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { AgentMessageDetails } from './AgentControls';
import { getApiErrorMessage } from '@/lib/api-errors';
const API = `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000'}/api/ai`;
const control = 'rounded-lg border border-slate-700 bg-slate-900 p-2 text-sm min-w-0';
const button = `${control} hover:border-sky-500 disabled:opacity-40`;
const panel = 'space-y-3 py-5 border-b border-slate-700/60';
const time = value => `${String(Math.floor(value / 60)).padStart(2, '0')}:${String(value % 60).padStart(2, '0')}`;
export default function DailyWorkspace() {
  const [daily, setDaily] = useState(null), [weekly, setWeekly] = useState(null), [capacity, setCapacity] = useState(240);
  const [actions, setActions] = useState([]), [insights, setInsights] = useState([]);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const load = useCallback(async () => {
    const [a, i] = await Promise.all([axios.get(`${API}/actions`), axios.get(`${API}/insights`)]);
    setActions(a.data); setInsights(i.data);
  }, []);
  useEffect(() => { load().catch(() => setError('Não foi possível carregar as sugestões.')); }, [load]);
  const run = async operation => { setBusy(true); setError(''); try { await operation(); await load(); } catch (e) { setError(getApiErrorMessage(e, 'Não foi possível concluir.')); } finally { setBusy(false); } };
  return <section aria-label="Seu dia com Sirius" className="mb-8">{error && <p role="alert" className="text-amber-300">{error}</p>}
      <section className={panel}><h2 className="text-lg font-medium">Planeje o dia</h2><p className="text-sm text-slate-400">Prévia calculada entre 08h e 18h, respeitando compromissos fixos registrados no assistente. Durações não informadas usam 30 minutos.</p><label className="block text-sm">Capacidade em minutos <input className={`${control} w-24 ml-2`} type="number" min="0" max="600" value={capacity} onChange={e => setCapacity(Number(e.target.value))} /></label><div className="flex flex-wrap gap-2"><button className={button} disabled={busy} onClick={() => run(async () => setDaily((await axios.get(`${API}/daily`, { params: { capacity } })).data))}>Ver plano de hoje</button><button className={button} disabled={busy} onClick={() => run(async () => setWeekly((await axios.get(`${API}/weekly`)).data))}>Revisão semanal</button></div>
        {daily && <div className="space-y-2 text-sm"><p>{daily.tasks.completed} de {daily.tasks.total} tarefas concluídas.</p>{daily.plan.blocks.map(b => <div className="rounded-lg bg-slate-900 p-3" key={b.task_id}><span className="text-sky-300">{time(b.start_minute)}–{time(b.end_minute)}</span> · {b.title}{b.duration_estimated && <span className="text-xs text-slate-500"> · duração estimada</span>}</div>)}{daily.plan.unscheduled.length > 0 && <p className="text-amber-300">{daily.plan.unscheduled.length} tarefa(s) não couberam no tempo disponível.</p>}<p className="text-slate-400">Prévia: nenhum horário ou tarefa foi alterado.</p></div>}
        {weekly && <div className="text-sm space-y-2"><p>Comparação com os mesmos dias da semana anterior.</p><div className="overflow-x-auto"><table className="w-full text-left"><thead><tr><th>Indicador</th><th>Atual</th><th>Anterior</th></tr></thead><tbody>{[['study_minutes', 'Minutos estudados'], ['tasks_completed', 'Tarefas concluídas'], ['workouts', 'Treinos'], ['income', 'Receitas (R$)'], ['expenses', 'Despesas (R$)'], ['questions_correct', 'Questões corretas']].map(([key, label]) => <tr key={key}><td className="py-1">{label}</td><td>{weekly.current[key]}</td><td>{weekly.previous_same_weekdays[key]}</td></tr>)}</tbody></table></div>{weekly.adjustments.map(t => <p key={t} className="text-sky-200">• {t}</p>)}</div>}
      </section>
<details className="mt-3"><summary className="cursor-pointer text-sm text-slate-300">Propostas e sugestões do Sirius</summary>      <section className={panel}><h2 className="text-lg font-medium">Propostas e sugestões</h2><p className="text-sm text-slate-400">Confira o que está pendente e o resultado das últimas ações.</p><AgentMessageDetails message={{ actions }} />{actions.length === 0 && <p className="text-sm text-slate-500">Nenhuma proposta registrada ainda.</p>}{insights.map(i => <div className="border-t border-slate-800 pt-3 space-y-2" key={i.insight_id}><p>{i.title}{i.dry_run && <span className="text-xs text-slate-500"> · simulação</span>}</p><Link to={i.link} className="text-sm text-sky-400">Ver módulo</Link><div className="flex flex-wrap gap-2">{[['helpful', 'Útil'], ['dismiss', 'Dispensar'], ['snooze', 'Adiar um dia'], ['never', 'Não sugerir mais']].map(([feedback, label]) => <button key={feedback} className={button} disabled={busy} onClick={() => run(() => axios.post(`${API}/insights/${i.insight_id}/feedback`, { feedback }))}>{label}</button>)}</div></div>)}</section>
</details></section>;
}
