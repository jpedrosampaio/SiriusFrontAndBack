import { useEffect, useState } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { getApiErrorMessage } from '@/lib/api-errors';
import { openSirius } from '@/lib/sirius-context';

const API = `${process.env.REACT_APP_BACKEND_URL}/api/workouts/intelligence`;
const number = value => value == null ? 'Não disponível' : Number(value).toLocaleString('pt-BR', { maximumFractionDigits: 3 });
const input = 'min-h-11 w-full min-w-0 rounded-lg border border-white/15 bg-black/30 px-3';

function Alternatives({ userId, plans }) {
  const [selection, setSelection] = useState(''), [result, setResult] = useState(null), [error, setError] = useState('');
  const [loading, setLoading] = useState(false), [attempt, setAttempt] = useState(0);
  const choices = plans.flatMap(plan => (plan.days || []).flatMap((day, dayIndex) => (day.exercises || []).map((exercise, exerciseIndex) => ({
    key: `${plan.plan_id}:${dayIndex}:${exerciseIndex}`, label: `${plan.name} · ${day.day_label || day.name || `Dia ${dayIndex + 1}`} · ${exercise.name}`,
    body: { plan_id: plan.plan_id, day_index: dayIndex, exercise_index: exerciseIndex },
  }))));
  const selected = choices.find(c => c.key === selection);
  const body = selected ? JSON.stringify(selected.body) : '';
  useEffect(() => { setSelection(''); }, [userId]);
  useEffect(() => {
    const controller = new AbortController(); setResult(null); setError(''); setLoading(false);
    if (!body) return () => controller.abort();
    setLoading(true);
    axios.post(`${API}/substitutions`, JSON.parse(body), { signal: controller.signal, timeout: 20000 }).then(({ data }) => {
      if (!data || !Array.isArray(data.suggestions) || !Array.isArray(data.limitations)) throw new Error('Resposta incompleta.');
      if (!controller.signal.aborted) setResult(data);
    }).catch(e => { if (!controller.signal.aborted) setError(getApiErrorMessage(e, 'Não foi possível consultar alternativas.')); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [body, userId, attempt, plans]);
  return <section aria-label="Alternativas de exercício" className="space-y-3 rounded-xl border border-white/10 p-4">
    <h3 className="font-semibold">Academia cheia? Avalie alternativas</h3>
    <p className="text-sm text-slate-400">Compare exercícios dos seus planos pelo objetivo e grupo registrado. Nenhuma escolha altera a ficha.</p>
    <label className="block text-sm">Exercício da ficha<select className={input} value={selection} onChange={e => setSelection(e.target.value)}>
      <option value="">Selecione um exercício</option>{choices.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}
    </select></label>
    {!choices.length && <p className="text-sm text-slate-400">Cadastre uma ficha com dias e exercícios para consultar alternativas.</p>}
    {loading && <p role="status">Consultando alternativas…</p>}
    {error && <div role="alert">{error}<Button className="min-h-11 mt-2" onClick={() => setAttempt(n => n + 1)}>Tentar alternativas novamente</Button></div>}
    {result && <div className="space-y-3" aria-live="polite">
      {!result.suggestions.length && <p>Nenhuma alternativa compatível encontrada nos planos analisados.</p>}
      {result.suggestions.map(s => <article key={`${s.source_plan_id}:${s.name}`} className="rounded-lg bg-white/5 p-3 space-y-1">
        <h4 className="font-medium break-words">{s.name}</h4><p className="text-sm">{s.reason}</p>
        {!s.movement_confirmed && <p className="text-amber-300 text-sm">Movimento não confirmado: candidato para avaliação.</p>}
      </article>)}
      {result.truncated && <p className="text-amber-300 text-sm">Lista limitada aos planos e candidatos analisados.</p>}
      {result.limitations.map(text => <p key={text} className="text-xs text-slate-400">{text}</p>)}
    </div>}
  </section>;
}

export default function TrainingIntelligence({ userId, plans }) {
  const [days, setDays] = useState(90), [reload, setReload] = useState(0), [state, setState] = useState(null);
  const [loading, setLoading] = useState(true), [error, setError] = useState('');
  useEffect(() => {
    let timer;
    const refresh = () => { clearTimeout(timer); timer = setTimeout(() => setReload(n => n + 1), 100); };
    window.addEventListener('sirius-data-changed', refresh);
    return () => { clearTimeout(timer); window.removeEventListener('sirius-data-changed', refresh); };
  }, [userId]);
  useEffect(() => {
    const controller = new AbortController(); setState(null); setError(''); setLoading(true);
    axios.get(`${API}/state`, { params: { days }, signal: controller.signal, timeout: 20000 }).then(({ data }) => {
      if (!data || !Array.isArray(data.exercises) || !Array.isArray(data.muscle_groups) || !Array.isArray(data.weekly_frequency) || !Array.isArray(data.limitations)) throw new Error('A análise retornou dados incompletos.');
      if (!controller.signal.aborted) setState(data);
    }).catch(e => { if (!controller.signal.aborted) setError(getApiErrorMessage(e, 'Não foi possível analisar o histórico.')); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [userId, days, reload]);
  return <section aria-label="Inteligência de treino" className="min-w-0 space-y-5">
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div><h2 className="text-xl font-semibold">Inteligência de treino</h2><p className="text-sm text-slate-400">Evolução baseada no que você registrou. Sugestões exigem sua decisão.</p></div>
      <div className="flex flex-wrap gap-2"><label className="text-xs">Janela de análise<select className={input} value={days} onChange={e => setDays(Number(e.target.value))}>
        {[30, 90, 180, 365].map(value => <option key={value} value={value}>{value} dias</option>)}
      </select></label><Button variant="outline" className="min-h-11 self-end" disabled={loading} onClick={() => setReload(n => n + 1)}>Atualizar análise</Button></div>
    </header>
    {loading && <p role="status">Analisando registros…</p>}
    {error && <p role="alert" className="text-amber-300">{error}</p>}
    {state && <>
      <p className="text-xs text-slate-400">{state.start} a {state.as_of} · {state.timezone}</p>
      {state.truncated && <p role="status" className="text-amber-300">Histórico limitado: métricas detalhadas cobrem a amostra analisada.</p>}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[['Treinos concluídos na janela', state.completed_workouts], ['Dias com treino na amostra', state.training_days], ['Minutos registrados na amostra', state.recorded_minutes], ['Séries registradas / prescritas', state.set_adherence == null ? 'Não disponível' : `${number(state.set_adherence)}%`]].map(([label, value]) => <div className="min-w-0 rounded-xl border border-white/10 bg-white/5 p-3" key={label}><p className="text-xs text-slate-400">{label}</p><p className="mt-2 text-xl font-semibold break-words">{value}</p></div>)}
      </div>
      {!state.exercises.length && <p className="rounded-xl border border-white/10 p-4">Ainda não há séries analisáveis. Registre suas séries no modo treino; cargas e RPE são opcionais e dados ausentes continuarão desconhecidos.</p>}
      <details className="rounded-xl border border-white/10 p-4"><summary className="min-h-11 cursor-pointer">Frequência por semana e volume por grupo</summary>
        <div className="grid sm:grid-cols-2 gap-4 text-sm"><div>{state.weekly_frequency.map(w => <p key={w.week_start}>Semana de {w.week_start}: {w.workouts} treinos · {w.training_days} dias</p>)}</div><div>{state.muscle_groups.map(g => <p key={g.name}>{g.name}: {g.recorded_sets} séries · {g.volume == null ? `Volume incompleto; subtotal conhecido ${number(g.known_volume)} kg × reps` : `${number(g.volume)} kg × reps`}</p>)}</div></div>
      </details>
      <div className="grid lg:grid-cols-2 gap-4">{state.exercises.map(ex => <article key={ex.key} className="min-w-0 rounded-xl border border-white/10 bg-slate-950/30 p-4 space-y-3">
        <div><h3 className="font-semibold break-words">{ex.name}</h3><p className="text-xs text-slate-400">{ex.muscle_group || 'Grupo não registrado'} · {ex.executions} execuções · {ex.recorded_sets} séries registradas</p></div>
        <dl className="grid grid-cols-2 gap-3 text-sm"><div><dt className="text-slate-400">Volume registrado</dt><dd>{ex.volume == null ? 'Incompleto' : `${number(ex.volume)} kg × reps`}</dd>{ex.volume == null && <dd className="text-xs">Subtotal conhecido: {number(ex.known_volume)} kg × reps</dd>}</div><div><dt className="text-slate-400">RPE médio registrado</dt><dd>{number(ex.average_rpe)} · {ex.rpe_samples} amostras</dd></div></dl>
        <div className={`rounded-lg p-3 text-sm ${ex.progression.action === 'review_increase' ? 'bg-emerald-500/10' : 'bg-white/5'}`}>
          <h4 className="font-medium">{ex.progression.action === 'review_increase' ? 'Aumento para avaliar' : ex.progression.action === 'maintain' ? 'Manter referência' : 'Mais registros necessários'}</h4>
          {ex.progression.suggested_weight != null && <p className="text-emerald-300">{number(ex.progression.current_weight)} → {number(ex.progression.suggested_weight)} kg · proposta, sem aplicação automática</p>}
          <p>{ex.progression.reason}</p><p className="text-xs text-slate-400">{ex.progression.evidence_dates.join(' · ')}</p>
        </div>
        {ex.alerts.map(a => <p className="text-sm text-amber-300" key={a.code}>{a.reason}</p>)}
        <details><summary className="min-h-11 cursor-pointer text-sm">Recordes na janela e últimas execuções</summary>
          <ul className="text-sm space-y-1">{ex.records.map((record, i) => <li key={i}>{record.kind === 'max_load' ? 'Maior carga' : record.kind === 'max_volume' ? 'Maior volume por execução' : `Maior carga para ${record.reps} reps`}: {number(record.value)} {record.kind === 'max_volume' ? 'kg × reps' : 'kg'} · {record.date}</li>)}</ul>
          <ul className="mt-3 text-xs text-slate-400 space-y-2">{ex.history.map(h => <li key={h.log_id}>{h.date} · {h.recorded_sets}/{h.prescribed_sets} séries · maior carga {number(h.max_load)} kg · RPE {number(h.average_rpe)} · {h.volume == null ? 'volume incompleto' : `${number(h.volume)} kg × reps`}</li>)}</ul>
        </details>
      </article>)}</div>
      <details className="text-xs text-slate-400"><summary className="cursor-pointer min-h-11">Critérios e limites da análise</summary>{state.limitations.map(text => <p key={text} className="mb-2">{text}</p>)}</details>
      <Button className="min-h-11 w-full sm:w-auto" variant="outline" onClick={() => openSirius({ surface: 'workouts', draft: 'Explique minha evolução nos treinos usando meus registros. Não altere cargas ou planos.' })}>Conversar sobre minha evolução</Button>
    </>}
    <Alternatives userId={userId} plans={plans} />
  </section>;
}
