import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { getApiErrorMessage } from '@/lib/api-errors';

const API = `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000'}/api/life`;
const labels = { preparation: 'Preparação', finance: 'Finanças', training: 'Treinos', nutrition: 'Nutrição', tasks: 'Tarefas', calendar: 'Agenda', habits: 'Hábitos', goals: 'Metas' };
const days = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo'];
const clock = m => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
const minute = s => Number(s.slice(0, 2)) * 60 + Number(s.slice(3));
const input = 'min-h-11 rounded-lg border border-white/15 bg-black/30 px-3 text-sm w-full';

export default function GlobalPlanner({ userId, onAccepted }) {
  const [state, setState] = useState(null), [plan, setPlan] = useState(null), [config, setConfig] = useState(null);
  const [weekday, setWeekday] = useState(0), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const [excluded, setExcluded] = useState([]), [durations, setDurations] = useState({}), [capacity, setCapacity] = useState('');
  const [configOpen, setConfigOpen] = useState(false), [notice, setNotice] = useState('');
  const intent = useRef(null), generation = useRef(0), locked = useRef(false);
  const load = useCallback(async signal => {
    const { data } = await axios.get(`${API}/state`, { signal });
    return data;
  }, []);
  useEffect(() => {
    const c = new AbortController(), gen = ++generation.current;
    setState(null); setPlan(null); setError(''); setExcluded([]); setDurations({}); setNotice(''); intent.current = null; locked.current = false;
    load(c.signal).then(data => { if (generation.current === gen) { setState(data); setConfig(data.availability); } }).catch(e => { if (!c.signal.aborted) setError(getApiErrorMessage(e, 'Não foi possível consultar o estado integrado.')); });
    return () => { c.abort(); generation.current = gen + 1; };
  }, [load, userId]);
  const edit = next => { setConfig(next); intent.current = null; setPlan(null); };
  const run = async (kind, payload) => {
    if (locked.current) return;
    locked.current = true; setBusy(true); setError(''); setNotice(''); const gen = generation.current;
    const signature = JSON.stringify([kind, payload]);
    if (intent.current?.signature !== signature) intent.current = { signature, key: crypto.randomUUID() };
    try {
      if (kind === 'simulate') {
        const { data } = await axios.post(`${API}/simulate`, payload); if (gen !== generation.current) return;
        setState(data.state); setPlan(data.plan); intent.current = null;
      } else {
        if (kind === 'release') await axios.delete(`${API}/allocations/${payload.event_id}`, { params: { confirmed: true }, headers: { 'Idempotency-Key': intent.current.key } });
        else await axios[kind === 'availability' ? 'put' : 'post'](`${API}/${kind}`, payload, { headers: { 'Idempotency-Key': intent.current.key } });
        if (gen !== generation.current) return;
        intent.current = null; const data = await load(); if (gen !== generation.current) return;
        setState(data); setConfig(data.availability); setPlan(null); setExcluded([]); setDurations({});
        setNotice(kind === 'accept' ? 'Horários confirmados na agenda. Os registros dos módulos foram preservados.' : kind === 'release' ? 'Horário flexível liberado. Simule novamente para reorganizar o dia.' : 'Disponibilidade salva. Agora simule o dia.');
        if (kind === 'accept' || kind === 'release') onAccepted?.();
      }
    } catch (e) { if (gen === generation.current) setError(getApiErrorMessage(e, 'A operação não foi confirmada. Tente novamente com os mesmos dados.')); }
    finally { if (gen === generation.current) { locked.current = false; setBusy(false); } }
  };
  if (!state || !config) return <section className="rounded-2xl border border-white/10 p-4 mb-6" aria-label="Planejador global"><p>{error || 'Consultando estado integrado…'}</p></section>;
  const domains = Object.fromEntries(state.domains.map(d => [d.domain, d]));
  const candidates = state.domains.flatMap(d => d.candidates);
  const scenario = { date: state.date, exclude: excluded, durations: Object.fromEntries(Object.entries(durations).filter(([, v]) => v !== '').map(([k, v]) => [k, Number(v)])), capacity_minutes: capacity === '' ? null : Number(capacity) };
  const windowRows = config.weekdays[weekday];
  return <section className="mb-6 rounded-2xl border border-sky-400/20 bg-gradient-to-br from-sky-950/30 to-[#0A0A0A] p-4 md:p-6 space-y-4 min-w-0" aria-label="Planejador global">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-xl font-semibold">Seu dia integrado</h2><p className="text-sm text-slate-400">{state.date} · {state.timezone} · fatos dos seus módulos</p></div><Button variant="outline" className="min-h-11" disabled={busy} onClick={() => setConfigOpen(!configOpen)}>{configOpen ? 'Fechar disponibilidade' : 'Minha disponibilidade'}</Button></div>
    <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
      <div className="rounded-xl bg-black/25 p-3"><p className="text-slate-400">Preparação</p><strong>{domains.preparation.facts.dated_blocks} blocos do dia</strong></div>
      <div className="rounded-xl bg-black/25 p-3"><p className="text-slate-400">Treinos</p><strong>{domains.training.facts.completed_today} concluídos</strong></div>
      <div className="rounded-xl bg-black/25 p-3"><p className="text-slate-400">Hábitos</p><strong>{domains.habits.facts.completed_today}/{domains.habits.facts.recorded} marcados</strong></div>
      <div className="rounded-xl bg-black/25 p-3"><p className="text-slate-400">Nutrição</p><strong>{domains.nutrition.facts.water_ml} ml registrados</strong></div>
    </div>
    <p className="text-xs text-slate-400">Finanças: resultado registrado do mês R$ {domains.finance.facts.recorded_net} (não é saldo bancário). {domains.goals.facts.items.length} metas em andamento. {domains.calendar.facts.commitments} horários reservados.</p>
    {state.warnings.map(w => <p className="text-sm text-amber-200" key={w}>{w}</p>)}
    {(domains.calendar.facts.allocations || []).length > 0 && <details className="rounded-xl border border-white/10 p-3"><summary className="min-h-11 cursor-pointer text-sm">Horários flexíveis já confirmados</summary><p className="text-xs text-slate-400">Para reorganizar, libere explicitamente um horário futuro e simule novamente. Compromissos fixos e históricos permanecem preservados.</p>{domains.calendar.facts.allocations.map(a => <div className="py-3 border-b border-white/10" key={a.event_id}><p className="text-sm break-words">{a.title} · {new window.Intl.DateTimeFormat('pt-BR', { timeZone: state.timezone, hour: '2-digit', minute: '2-digit' }).format(new Date(a.start_at))}</p><Button variant="outline" className="min-h-11 mt-2" disabled={busy || new Date(a.start_at).getTime() <= Date.now()} onClick={() => run('release', { event_id: a.event_id })}>Confirmar liberação deste horário</Button></div>)}</details>}
    {configOpen && <fieldset disabled={busy} className="space-y-3 rounded-xl border border-white/10 p-3"><legend className="text-sm px-1">Disponibilidade real e estimativas pessoais</legend>
      <label className="block text-sm">Dia da semana<select className={input} value={weekday} onChange={e => setWeekday(Number(e.target.value))}>{days.map((d, i) => <option key={d} value={i}>{d}</option>)}</select></label>
      <p className="text-xs text-slate-400">Declare até quatro intervalos livres por dia. Trabalho e outros períodos ocupados ficam fora desses intervalos; compromissos cadastrados também serão descontados.</p>
      {windowRows.map((w, i) => <div key={i} className="grid grid-cols-2 gap-2"><label className="text-sm">Das<input aria-label={`Início ${i + 1}`} className={input} type="time" value={clock(w.start_minute)} onChange={e => { if (e.target.value) edit({ ...config, weekdays: config.weekdays.map((v, k) => k === weekday ? v.map((x, j) => j === i ? { ...x, start_minute: minute(e.target.value) } : x) : v) }); }} /></label><label className="text-sm">Até<input aria-label={`Fim ${i + 1}`} className={input} type="time" value={w.end_minute === 1440 ? '23:59' : clock(w.end_minute)} onChange={e => { if (e.target.value) edit({ ...config, weekdays: config.weekdays.map((v, k) => k === weekday ? v.map((x, j) => j === i ? { ...x, end_minute: minute(e.target.value) } : x) : v) }); }} /></label><Button variant="ghost" className="min-h-11 col-span-2" onClick={() => edit({ ...config, weekdays: config.weekdays.map((v, k) => k === weekday ? v.filter((_, j) => j !== i) : v) })}>Remover intervalo {i + 1}</Button></div>)}
      <Button variant="outline" className="min-h-11" disabled={windowRows.length >= 4} onClick={() => edit({ ...config, weekdays: config.weekdays.map((v, k) => k === weekday ? [...v, { start_minute: 1080, end_minute: 1260 }] : v) })}>Adicionar intervalo</Button>
      <label className="block text-sm">Plano de treino para incluir<select className={input} value={config.training_plan_id || ''} onChange={e => edit({ ...config, training_plan_id: e.target.value || null })}><option value="">Não incluir automaticamente</option>{domains.training.facts.available_plans.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
      <div className="flex flex-wrap gap-3">{days.map((d, i) => <label className="text-sm inline-flex min-h-11 items-center gap-2" key={d}><input type="checkbox" checked={(config.training_weekdays || []).includes(i)} onChange={e => edit({ ...config, training_weekdays: e.target.checked ? [...(config.training_weekdays || []), i] : (config.training_weekdays || []).filter(k => k !== i) })} />Treino: {d}</label>)}</div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">{['tasks', 'training', 'habits', 'finance', 'nutrition', 'goals'].map(d => <label className="text-sm" key={d}>{labels[d]}: estimativa (min)<input className={input} type="number" min="5" max="720" value={config.duration_estimates[d] ?? ''} onChange={e => { const estimates = { ...config.duration_estimates }; if (e.target.value === '') delete estimates[d]; else estimates[d] = Number(e.target.value); edit({ ...config, duration_estimates: estimates }); }} /></label>)}</div>
      <Button className="min-h-11" onClick={() => run('availability', config)}>Salvar disponibilidade</Button>
    </fieldset>}
    <details className="rounded-xl border border-white/10 p-3"><summary className="cursor-pointer min-h-11 text-sm">Candidatos e cenário do dia</summary><p className="text-xs text-slate-400 mb-3">A simulação não grava atividades. Você pode comparar capacidade, estimativas e atividades flexíveis. Blocos protegidos permanecem na data.</p>
      <label className="block text-sm">Limite de minutos flexíveis (opcional)<input className={input} type="number" min="0" max="1440" value={capacity} disabled={busy} onChange={e => { setCapacity(e.target.value); setPlan(null); }} /></label>
      {candidates.map(c => <div key={c.id} className="py-3 border-b border-white/10 space-y-2"><label className="flex gap-2 items-start"><input className="mt-1" type="checkbox" disabled={busy || c.date_locked} checked={!excluded.includes(c.id)} onChange={e => { setExcluded(e.target.checked ? excluded.filter(id => id !== c.id) : [...excluded, c.id]); setPlan(null); }} /><span className="text-sm break-words min-w-0">{c.title} · {labels[c.domain]}{c.date_locked ? ' · data protegida' : ''}</span></label><p className="text-xs text-slate-400 break-words">{c.reasons.join(' · ')}</p><label className="block text-xs">Duração (min) · {c.duration_origin === 'recorded' ? 'registrada' : c.duration_origin === 'user_estimate' ? 'estimada por você' : 'não informada'}<input className={input} type="number" min="5" max="720" disabled={busy || c.date_locked} value={durations[c.id] ?? c.duration_minutes ?? ''} onChange={e => { setDurations({ ...durations, [c.id]: e.target.value }); setPlan(null); }} /></label></div>)}
      {!candidates.length && <p className="text-sm mt-3 text-slate-400">Nenhuma atividade elegível neste dia. Cadastre tarefas, use o cronograma de estudo ou selecione um plano de treino.</p>}
    </details>
    <Button className="min-h-11" disabled={busy} onClick={() => run('simulate', scenario)}>{busy ? 'Processando…' : 'Simular meu dia'}</Button>
    {error && <p role="alert" className="text-sm text-red-300 break-words">{error}</p>}{notice && <p role="status" className="text-sm text-emerald-300">{notice}</p>}
    {plan && <div role="region" className="space-y-3" aria-label="Resultado da simulação"><h3 className="font-medium">Distribuição proposta · {plan.available_minutes} min livres</h3><p className="text-xs text-slate-400">Compromissos fixos permanecem nos horários registrados. Nada foi alterado.</p>
      {plan.conflicts.length > 0 && <p className="text-amber-200 text-sm">{plan.conflicts_truncated ? 'Ao menos ' : ''}{plan.conflicts.length} conflito(s) entre horários fixos. Revise-os manualmente.</p>}
      {plan.constraints.map(c => <p key={c.id} className="text-sm text-slate-400 break-words">{c.civil_time_ambiguous ? `${c.elapsed_minutes} min reais · mudança de horário; confira a agenda` : `${clock(c.start_minute)}–${clock(c.end_minute)}`} · {c.title} · fixo</p>)}
      {plan.blocks.map(b => <div key={b.candidate_id} className="rounded-xl border border-sky-400/20 p-3"><p className="text-sm font-medium break-words">{clock(b.start_minute)}–{clock(b.end_minute)} · {b.title}</p><p className="text-xs text-slate-400 my-2">{b.reason} {b.duration_estimated ? 'Duração estimada por você.' : ''}</p><Link className="text-sm text-sky-300 underline inline-flex min-h-11 items-center" to={b.link}>Abrir {labels[b.domain]}</Link></div>)}
      {plan.unscheduled.map(b => <p className="text-sm text-amber-200 break-words" key={b.candidate_id}>{b.title}: {b.reason}</p>)}
      <Button className="min-h-11 w-full sm:w-auto" disabled={busy || !plan.planning_safe || !plan.blocks.length} onClick={() => run('accept', { scenario: plan.scenario, fingerprint: plan.fingerprint, blocks: plan.blocks, confirmed: true })}>Confirmar estes horários na agenda</Button>
    </div>}
  </section>;
}
