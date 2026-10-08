import FinalSprint from './FinalSprint';
import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { getApiErrorMessage } from '@/lib/api-errors';

const API = `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000'}/api/study/programs`;
const modes = { A: 'Ideal', B: 'Mínimo', C: 'Emergencial' };
const riskLabels = { coverage: 'Conteúdo não iniciado', mastery_gap: 'Lacuna de domínio estimado', recent_errors: 'Erros nas últimas respostas', review_due: 'Revisão devida', evidence_age: 'Idade das evidências', insufficient_evidence: 'Amostra insuficiente', declining_accuracy: 'Queda de acertos' };
export default function AdaptiveStrategy({ programId, onStudy }) {
  const [data, setData] = useState(null), [settings, setSettings] = useState(null);
  const [error, setError] = useState(''), [busy, setBusy] = useState(false), [mode, setMode] = useState('A');
  const [missedDays, setMissedDays] = useState(0), [refresh, setRefresh] = useState(0);
  const generation = useRef(0), lock = useRef(false);
  useEffect(() => {
    const controller = new AbortController(); generation.current += 1; lock.current = false;
    setData(null); setSettings(null); setBusy(false); setError(''); setMissedDays(0);
    axios.get(`${API}/${programId}/strategy`, { signal: controller.signal }).then(r => {
      if (!r.data?.scenarios || !Array.isArray(r.data.candidates)) throw new Error('Resposta de estratégia inválida. Tente atualizar.');
      if (!controller.signal.aborted) { setData(r.data); setSettings(r.data.settings); }
    }).catch(e => { if (!controller.signal.aborted) setError(getApiErrorMessage(e, 'Não foi possível carregar a estratégia.')); });
    return () => { controller.abort(); generation.current += 1; };
  }, [programId, refresh]);
  const simulate = async () => {
    if (lock.current || !settings) return;
    lock.current = true; setBusy(true); setError(''); const current = generation.current;
    try {
      const r = await axios.post(`${API}/${programId}/strategy/simulate`, { ...settings, missed_days: missedDays });
      if (!r.data?.scenarios || !Array.isArray(r.data.candidates)) throw new Error('Resposta de simulação inválida. Tente novamente.');
      if (current === generation.current) setData(r.data);
    } catch (e) { if (current === generation.current) setError(getApiErrorMessage(e, 'Não foi possível simular.')); }
    finally { if (current === generation.current) { lock.current = false; setBusy(false); } }
  };
  const scenario = data?.scenarios?.[mode];
  return <section aria-label="Estratégia adaptativa" className="sirius-study-panel min-w-0 rounded-2xl border p-5 space-y-5 [&_button]:min-h-11 [&_input]:min-h-11">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-xl font-semibold">Estratégia adaptativa</h2><p className="text-sm text-slate-400 mt-2">Escolha o que estudar pelo risco e retorno sugeridos. A agenda distribui o tempo; esta simulação não altera seus registros.</p></div><Button variant="outline" disabled={busy} onClick={() => setRefresh(n => n + 1)}>Atualizar estratégia</Button></div>
    <FinalSprint programId={programId} />
    {error && <p role="alert" className="text-amber-300 text-sm">{error}</p>}
    {!data && !error && <p role="status">Calculando prioridades…</p>}
    {data && <>
      {data.truncated && <p className="text-sm text-amber-300">Amostra limitada; o ranking pode omitir evidências mais antigas.</p>}
      {data.coverage_partial && <p className="text-sm text-amber-300">{data.topicless_disciplines?.length || 0} disciplinas ainda sem assuntos cadastrados recebem carga provisória por disciplina. A cobertura projetada considera somente os assuntos cadastrados.</p>}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-sm">{[['Revisões vencidas', data.debt.overdue_reviews.length], ['Críticos não iniciados', data.debt.critical_unstarted.length], ['Blocos atrasados', data.debt.missed_blocks.length], ['Metas atrasadas', data.debt.late_milestones.length]].map(([label, count]) => <div key={label} className="rounded-xl bg-slate-900 p-3"><p className="text-xs text-slate-400">{label}</p><strong className="text-xl">{count}</strong></div>)}</div>
      {!!data.debt.missed_blocks.length && <p className="text-sm text-blue-200">Recuperação: {data.debt.missed_minutes} min de pendências identificadas. Reorganize dentro da disponibilidade, preservando seus blocos manuais, fixos e concluídos.</p>}
      <details className="rounded-xl border border-slate-700 p-4"><summary className="cursor-pointer py-2">Simular disponibilidade e dias perdidos</summary>{settings && <div className="space-y-4 mt-3">
        <div className="grid sm:grid-cols-3 gap-3"><label className="text-sm">Início da simulação<Input type="date" value={settings.start_date} disabled={busy} onChange={e => setSettings(s => ({ ...s, start_date: e.target.value }))} /></label><label className="text-sm">Fim da simulação<Input type="date" value={settings.end_date} disabled={busy} onChange={e => setSettings(s => ({ ...s, end_date: e.target.value }))} /></label><label className="text-sm">Dias iniciais sem estudo<Input type="number" min={0} max={181} value={missedDays} disabled={busy} onChange={e => setMissedDays(Number(e.target.value))} /></label></div>
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">{['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'].map((day, i) => <label className="text-sm" key={day}>{day} · min simulados<Input type="number" min={0} max={720} step={15} value={settings.availability[i]} disabled={busy} onChange={e => setSettings(s => ({ ...s, availability: s.availability.map((m, index) => index === i ? Number(e.target.value) : m) }))} /></label>)}</div>
        <Button disabled={busy} onClick={simulate}>{busy ? 'Simulando…' : 'Simular sem alterar agenda'}</Button>
      </div>}</details>
      <div className="flex flex-wrap gap-2" role="group" aria-label="Cenário de estudo">{Object.entries(modes).map(([key, label]) => <Button key={key} variant={mode === key ? 'default' : 'outline'} aria-pressed={mode === key} onClick={() => setMode(key)}>{key} · {label}</Button>)}</div>
      {scenario && <div className="rounded-xl border border-blue-400/30 p-4 space-y-3"><p>Plano {mode} · {scenario.minutes} min no período</p><p className="text-sm text-slate-400">Cobertura dos assuntos cadastrados: {scenario.projected_coverage == null ? 'sem assuntos cadastrados' : `${scenario.projected_coverage}%`} · {scenario.new_topics_assuming_completion} novos assuntos, supondo conclusão. É uma estimativa de contato, sem previsão de aprovação.</p><p className="text-xs text-slate-400">{scenario.protected_minutes} min preservados · {scenario.unaddressed_due_reviews.length} revisões vencidas sem bloco sugerido · {scenario.unaddressed_critical_topics.length} críticos sem carga inicial suficiente.</p>{scenario.load_guard.warnings.map(w => <p key={w.code} className="text-amber-300 text-sm">{w.message}</p>)}<p className="text-xs text-slate-400">Pausa sugerida após 50 min de foco. Para salvar, use os ajustes da agenda abaixo.</p><details><summary className="cursor-pointer py-2 text-sm">Ver blocos simulados</summary><ul className="space-y-2 mt-2">{scenario.entries.slice(0, 20).map(e => <li key={e.entry_id} className="text-xs break-words">{e.date} · {e.name} · {e.minutes} min{e.manual || e.fixed || e.completed ? ' · preservado' : ''}</li>)}</ul>{scenario.entries_count > 20 && <p className="text-xs text-slate-400 mt-2">Exibindo 20 de {scenario.entries_count} blocos.</p>}</details></div>}
      <h3 className="font-medium">Prioridades e motivos</h3><ul className="space-y-3">{data.candidates.slice(0, 10).map(c => <li key={c.id} className="rounded-xl border border-slate-700 p-4 space-y-2"><div className="flex flex-wrap gap-3 justify-between"><div className="min-w-0"><p className="font-medium break-words">{c.title}</p><p className="text-xs text-slate-400 break-words">{c.discipline}{c.scope === 'discipline' ? ' · prioridade provisória da disciplina' : ''} · risco operacional {c.risk}/100 · retorno sugerido {c.expected_return}</p></div><Button onClick={() => onStudy?.({ ...c, minutes: Math.min(c.cost_minutes, mode === 'C' ? 25 : mode === 'B' ? 45 : c.cost_minutes) })}>Estudar prioridade</Button></div><p className="text-xs text-slate-400 break-words">{c.reasons.join(' · ')}</p><details className="text-xs"><summary className="cursor-pointer py-2">Como foi calculado</summary><p className="break-words">Componentes: {Object.entries(c.risk_components).map(([key, value]) => `${riskLabels[key] || key}: ${value}`).join(' · ')}. Urgência: ×{c.urgency_multiplier}.</p><p className="mt-2">Retorno = impacto {c.impact} × risco/100 ÷ {c.cost_minutes} min sugeridos. {c.scope === 'discipline' ? 'Sem intervalo por assunto: conteúdo ainda não detalhado.' : <>Revisão sugerida: {c.review_interval_days} dias. {c.review_reason}</>}</p><p className="break-all mt-2">Evidências: {c.evidence_ids.join(', ') || 'sem respostas individuais'}</p></details></li>)}</ul>
      {!data.candidates.length && <p className="text-sm text-slate-400">Adicione assuntos ao edital verticalizado para receber prioridades.</p>}
      <details className="text-xs text-slate-400"><summary className="cursor-pointer py-2">Premissas e limites</summary><ul className="space-y-2 mt-2">{data.assumptions.map(a => <li key={a}>{a}</li>)}</ul><p className="mt-2">{data.notice}</p></details>
    </>}
  </section>;
}
