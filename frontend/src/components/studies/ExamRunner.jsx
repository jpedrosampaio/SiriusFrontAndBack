import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { getApiErrorMessage } from '@/lib/api-errors';
import { questionOriginLabel } from '@/lib/question-origin';
const API = `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000'}/api/study/simulados`;
const optionsFor = q => (q.options || []).map((text, i) => ({ text, value: text.match(/^([A-E])\)/)?.[1] || (q.type === 'certo_errado' ? text : String.fromCharCode(65 + i)) }));
const timer = seconds => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
export default function ExamRunner({ exam, onComplete, onExit }) {
  const [draft, setDraft] = useState(null), [error, setError] = useState(''), [status, setStatus] = useState('Carregando progresso…');
  const [completed, setCompleted] = useState(null), [restart, setRestart] = useState(0);
  const [paused, setPaused] = useState(false), [busy, setBusy] = useState(false), [conflict, setConflict] = useState(false);
  const current = useRef(null), revision = useRef(0), pending = useRef(null), saving = useRef(null), alive = useRef(true);
  const frozen = useRef(false), lastTick = useRef(Date.now()), submit = useRef(null), dirty = useRef(false);
  const functions = useRef({}), hardConflict = useRef(false);
  const url = `${API}/${exam.simulado_id}`;
  const publish = value => { current.current = value; dirty.current = true; setDraft(value); setStatus('Alterações ainda não salvas'); };
  useEffect(() => {
    let canceled = false; alive.current = true;
    window.scrollTo({ top: 0 });
    const load = async () => {
      try {
        let { data } = await axios.get(`${url}/session`);
        if (!data || restart) {
          await axios.post(`${url}/session`, {}, { headers: { 'Idempotency-Key': crypto.randomUUID() } });
          ({ data } = await axios.get(`${url}/session`));
        }
        if (canceled) return;
        if (data?.status === 'completed') {
          const results = await axios.get(`${url}/results`);
          const completed = results.data.find(a => a.attempt_id === data.attempt_id);
          if (!canceled) { if (completed) { setCompleted(completed); setStatus('Resultado salvo'); } else throw new Error('Resultado indisponivel. Tente carregar novamente.'); }
          return;
        }
        if (!data || data.status !== 'active' || typeof data.session_id !== 'string' || !Number.isInteger(data.revision) || !Array.isArray(data.answers) || !Array.isArray(data.marked)) throw new Error('Progresso inválido. Consulte a execução salva.');
        current.current = data; revision.current = data.revision; setDraft(data); lastTick.current = Date.now(); setStatus('Progresso salvo');
      } catch (e) { if (!canceled) setError(getApiErrorMessage(e, 'Não foi possível iniciar ou retomar.')); }
    };
    load();
    return () => { canceled = true; alive.current = false; };
  }, [url, restart]);
  const tick = () => {
    const now = Date.now(), delta = Math.max(0, Math.floor((now - lastTick.current) / 1000));
    lastTick.current += delta * 1000;
    const d = current.current;
    if (!d || frozen.current || paused || document.hidden || !delta) { lastTick.current = now; return; }
    const seconds = Math.min(delta, 86400 - d.elapsed_seconds);
    if (!seconds) return;
    const answers = [...d.answers];
    const i = d.current_question, a = answers.find(x => x.question_idx === i) || { question_idx: i, selected_answer: '', seconds: 0 };
    const next = { ...a, seconds: (a.seconds || 0) + seconds };
    publish({ ...d, answers: [...answers.filter(x => x.question_idx !== i), next], elapsed_seconds: d.elapsed_seconds + seconds });
  };
  const save = async () => {
    if (saving.current) { await saving.current; return save(); }
    if (!current.current || (!dirty.current && !pending.current)) return;
    if (conflict) throw new Error('Recarregue o progresso para resolver o conflito.');
    if (!pending.current) {
      const d = current.current;
      pending.current = { key: crypto.randomUUID(), body: { session_id: d.session_id, revision: revision.current, answers: d.answers, current_question: d.current_question, marked: d.marked, elapsed_seconds: d.elapsed_seconds }, snapshot: d };
    }
    const job = pending.current;
    const promise = (async () => {
      try {
        if (alive.current) setStatus('Salvando…');
        const { data } = await axios.put(`${url}/session`, job.body, { headers: { 'Idempotency-Key': job.key } });
        revision.current = data.revision; pending.current = null;
        dirty.current = current.current !== job.snapshot;
        if (alive.current) { setStatus(dirty.current ? 'Alterações ainda não salvas' : 'Progresso salvo'); setError(''); }
      } catch (e) {
        if (alive.current) { setStatus('Não salvo · tente novamente'); setError(getApiErrorMessage(e, 'Falha ao salvar. Mantenha esta página aberta e tente novamente.')); if (e.response?.status === 409) { hardConflict.current = true; setConflict(true); frozen.current = true; } }
        throw e;
      }
    })();
    saving.current = promise;
    try { await promise; } finally { saving.current = null; }
  };
  useEffect(() => {
    const interval = setInterval(() => functions.current.tick(), 1000);
    return () => clearInterval(interval);
  }, []);
  useEffect(() => {
    const interval = setInterval(() => { if (!frozen.current) functions.current.save().catch(() => {}); }, 5000);
    const before = e => { if (dirty.current || pending.current) { e.preventDefault(); e.returnValue = ''; } };
    const visibility = () => { lastTick.current = Date.now(); };
    window.addEventListener('beforeunload', before);
    document.addEventListener('visibilitychange', visibility);
    return () => { clearInterval(interval); window.removeEventListener('beforeunload', before); document.removeEventListener('visibilitychange', visibility); };
  }, []);
  functions.current = { tick, save, onComplete };
  const edit = fn => { tick(); if (!frozen.current) publish(fn(current.current)); };
  const finish = async () => {
    if (frozen.current || !current.current) return;
    if (!window.confirm('Finalizar esta tentativa? Questões em branco permanecerão sem resposta.')) return;
    tick(); frozen.current = true; setBusy(true);
    try {
      await save(); if (dirty.current) await save();
      submit.current ||= { key: crypto.randomUUID(), body: { session_id: current.current.session_id, revision: revision.current, answers: [], time_spent_seconds: 0 } };
      const { data } = await axios.post(`${url}/submit`, submit.current.body, { headers: { 'Idempotency-Key': submit.current.key } });
      if (alive.current) onComplete(data);
    } catch (e) { setError(getApiErrorMessage(e, 'Conclusão não confirmada. Tente novamente; não será pontuada duas vezes.')); }
    finally { setBusy(false); if (!submit.current && !hardConflict.current) frozen.current = false; }
  };
  const retryFinish = async () => {
    if (busy) return; setBusy(true);
    try { const { data } = await axios.post(`${url}/submit`, submit.current.body, { headers: { 'Idempotency-Key': submit.current.key } }); if (alive.current) onComplete(data); }
    catch (e) { setError(getApiErrorMessage(e, 'Consulte o resultado ou tente confirmar novamente.')); }
    finally { setBusy(false); }
  };
  const exit = async () => {
    if (busy || frozen.current) return; tick(); frozen.current = true; setBusy(true);
    try { await save(); if (dirty.current) await save(); if (alive.current) onExit(); }
    catch { /* Retain unsaved progress in this page. */ }
    finally { setBusy(false); if (!hardConflict.current) frozen.current = false; }
  };
  const recover = async () => {
    const { data } = await axios.get(`${url}/session`);
    if (data?.status === 'completed') {
      const r = await axios.get(`${url}/results`); const result = r.data.find(x => x.attempt_id === data.attempt_id); if (result && alive.current) onComplete(result);
    } else if (window.confirm('Carregar o progresso salvo? Alterações locais não salvas serão descartadas.')) {
      current.current = data; revision.current = data.revision; pending.current = null; dirty.current = false; frozen.current = false; hardConflict.current = false; submit.current = null; setDraft(data); setConflict(false); setError(''); setStatus('Progresso salvo'); lastTick.current = Date.now();
    }
  };
  if (completed) return <section aria-label="Execução da prova" className="space-y-4 p-5"><h2>Resultado salvo</h2><p>Esta tentativa foi concluída. Seu resultado permanece no histórico.</p><div className="flex flex-wrap gap-3"><Button onClick={() => onComplete(completed)}>Ver resultado</Button><Button variant="outline" onClick={() => { if (window.confirm('Iniciar uma nova tentativa? O resultado anterior sera preservado.')) { setCompleted(null); setRestart(v => v + 1); } }}>Iniciar nova tentativa</Button></div></section>;
  const q = draft && exam.questions[draft.current_question];
  const selected = draft?.answers.find(a => a.question_idx === draft.current_question);
  const answer = value => edit(d => {
    const previous = d.answers.find(a => a.question_idx === d.current_question);
    return { ...d, answers: [...d.answers.filter(a => a.question_idx !== d.current_question), { ...previous, question_idx: d.current_question, selected_answer: value, changed_answer: previous?.changed_answer || !!(previous?.selected_answer && previous.selected_answer !== value) }] };
  });
  return <section aria-label="Execução da prova" className="space-y-5 min-w-0 [&_button]:min-h-11">
    <header className="sticky top-0 z-10 bg-slate-950 rounded-xl border border-slate-700 p-4 space-y-3"><h2 className="font-semibold break-words">{exam.title}</h2><div className="flex flex-wrap justify-between gap-3 text-sm"><span role="timer">{timer(draft?.elapsed_seconds || 0)}{exam.duration_minutes ? ` / ${exam.duration_minutes} min` : ' · sem limite informado'}</span><span role="status">{status}</span></div><p className="text-xs text-slate-400">Tempo de interação nesta página; ao ocultar a aba ou pausar, o cronômetro não conta. Progresso salvo a cada 5 segundos. Duração e pontuação de prática não comprovam regras da banca.</p><p className="text-xs text-slate-400">Erro: desconto de {exam.blueprint?.scoring?.wrong_penalty || 0} × peso; branco: {exam.blueprint?.scoring?.blank_penalty || 0} × peso. {exam.blueprint?.scoring?.source ? `Fonte conferida pelo usuário: ${exam.blueprint.scoring.source}` : 'Pontuação padrão de prática, sem penalização.'}</p><div className="flex flex-wrap gap-2"><Button variant="outline" disabled={busy || conflict} onClick={exit}>Salvar e sair</Button><Button variant="outline" disabled={busy || conflict || !!submit.current} onClick={() => { tick(); setPaused(!paused); lastTick.current = Date.now(); }}>{paused ? 'Continuar' : 'Pausar'}</Button><Button disabled={busy || conflict || !draft} onClick={submit.current ? retryFinish : finish}>{busy ? 'Confirmando…' : submit.current ? 'Confirmar conclusão' : 'Finalizar prova'}</Button></div></header>
    {error && <div role="alert" className="rounded-xl border border-amber-600 p-4 space-y-2"><p>{error}</p><Button variant="outline" disabled={busy} onClick={() => recover().catch(e => setError(getApiErrorMessage(e, 'Não foi possível recuperar.')))}>Consultar progresso / resultado salvo</Button></div>}
    {q && <><nav aria-label="Questões" className="flex flex-wrap gap-2">{exam.questions.map((_, i) => <button disabled={busy || conflict || !!submit.current} key={i} aria-label={`Questão ${i + 1}`} aria-current={draft.current_question === i ? 'step' : undefined} className={`w-11 rounded-lg border ${draft.current_question === i ? 'bg-blue-700' : draft.marked.includes(i) ? 'border-amber-400' : draft.answers.find(a => a.question_idx === i)?.selected_answer ? 'border-green-500' : 'border-slate-700'}`} onClick={() => edit(d => ({ ...d, current_question: i }))}>{i + 1}</button>)}</nav><article className="rounded-2xl border border-slate-700 p-5 space-y-4"><p className="text-sm text-slate-400">Questão {draft.current_question + 1} · {q.disciplina || 'Geral'}</p>{q.texto_base && <p className="whitespace-pre-wrap text-sm text-slate-300">{q.texto_base}</p>}<h3 className="whitespace-pre-wrap">{q.question_text}</h3><p className="text-xs text-slate-400">{questionOriginLabel(q.origin)}</p><div className="space-y-2">{optionsFor(q).map(o => <button key={o.value} aria-pressed={selected?.selected_answer === o.value} disabled={busy || conflict || paused || !!submit.current} className={`block w-full text-left p-3 rounded-xl border break-words ${selected?.selected_answer === o.value ? 'border-blue-400 bg-blue-950' : 'border-slate-700'}`} onClick={() => answer(o.value)}>{o.text}</button>)}</div><label className="block text-sm">Confiança <select aria-label="Confiança na questão" disabled={busy || conflict || !!submit.current} value={selected?.confidence || ''} className="block w-full bg-slate-900 p-3 rounded-lg" onChange={e => edit(d => ({ ...d, answers: [...d.answers.filter(a => a.question_idx !== d.current_question), { ...d.answers.find(a => a.question_idx === d.current_question), question_idx: d.current_question, selected_answer: d.answers.find(a => a.question_idx === d.current_question)?.selected_answer || '', confidence: e.target.value || null }] }))}><option value="">Não informar</option><option value="guess">Chute</option><option value="uncertain">Incerto</option><option value="confident">Confiante</option></select></label><div className="flex flex-wrap gap-2"><Button variant="outline" disabled={busy || conflict || !!submit.current} onClick={() => answer('')}>Deixar em branco</Button><Button variant="outline" disabled={busy || conflict || !!submit.current} onClick={() => edit(d => ({ ...d, marked: d.marked.includes(d.current_question) ? d.marked.filter(i => i !== d.current_question) : [...d.marked, d.current_question] }))}>{draft.marked.includes(draft.current_question) ? 'Desmarcar revisão' : 'Revisar depois'}</Button></div></article></>}
  </section>;
}
