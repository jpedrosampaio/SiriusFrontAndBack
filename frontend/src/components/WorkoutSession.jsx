import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import WorkoutTutorial from '@/components/WorkoutTutorial';
import WorkoutComparison from '@/components/WorkoutComparison';
import { readSaved, writeSaved } from '@/lib/session-storage';
import { getApiErrorMessage } from '@/lib/api-errors';
import { setDefaults, validateSet, workoutSummary, sessionTime } from '@/lib/workout-session';
import { ArrowRight, Check, Dumbbell, Loader2, Timer } from 'lucide-react';
import './WorkoutSession.css';

function useWorkoutWakeLock(active) {
  useEffect(() => {
    if (!active || !navigator.wakeLock?.request) return;
    let closed = false, sentinel = null, acquiring = false;
    const acquire = async () => {
      if (closed || acquiring || sentinel || document.visibilityState !== 'visible') return;
      acquiring = true;
      try {
        const lock = await navigator.wakeLock.request('screen');
        if (closed || document.visibilityState !== 'visible') await lock.release();
        else { sentinel = lock; lock.addEventListener('release', () => { if (sentinel === lock) sentinel = null; }); }
      } catch { /* Optional screen wake lock must never block training. */ }
      finally { acquiring = false; }
    };
    const visibility = () => { if (document.visibilityState === 'visible') acquire(); };
    acquire(); document.addEventListener('visibilitychange', visibility);
    return () => { closed = true; document.removeEventListener('visibilitychange', visibility); sentinel?.release().catch(() => {}); };
  }, [active]);
}

function HistoryPreview({ exercise, history, loading, error, onRetry }) {
  if (loading) return <p className="ws-muted" role="status">Carregando histórico…</p>;
  if (error) return <div role="status"><p className="ws-muted">Histórico indisponível. Você pode continuar treinando.</p><Button variant="outline" onClick={onRetry}>Tentar histórico novamente</Button></div>;
  if (!history?.length) return <p className="ws-muted">Nenhum histórico registrado para este exercício.</p>;
  const recent = history[0];
  const renderSets = entry => (entry.sets_data || []).map((set, index) => <li key={index}>{set.weight !== '' && set.weight != null ? `${set.weight} kg` : 'Carga não registrada'} × {set.reps ?? '—'} reps{set.rpe !== '' && set.rpe != null ? ` · RPE ${set.rpe}` : ''}</li>);
  return <div className="ws-history">
    <p className="ws-eyebrow">Último treino · {recent.date?.slice(0, 10)}</p>
    <ul>{renderSets({ sets_data: recent.sets_data?.slice(0, 3) })}</ul>
    <details><summary>Ver histórico completo</summary>
      {history.map((entry, index) => <div key={index} className="ws-history-entry"><p>{entry.date?.slice(0, 10)}</p><ul>{renderSets(entry)}</ul>{!entry.sets_data?.length && <p className="ws-muted">Séries detalhadas não registradas.</p>}</div>)}
      <WorkoutComparison current={exercise} previous={recent} />
    </details>
  </div>;
}

export default function WorkoutSession({ session, userId, elapsed, saving, onSave, onFinish, onAbandon, onHistory, nextLoads, loadError }) {
  const namespace = `sirius-workout-ux2:${userId}:${session.session_id}`;
  const [saved] = useState(() => {
    const current = readSaved(namespace);
    if (current && typeof current === 'object') return current;
    // Preserve unsaved input when a session created before UX2 is resumed.
    const legacy = readSaved(`sirius-workout-draft:${userId}:${session.session_id}`);
    if (legacy && Number.isInteger(legacy.index) && legacy.index >= 0 && legacy.index < session.exercises.length) return {
      index: legacy.index, drafts: { [legacy.index]: { weight: String(legacy.weight ?? ''), reps: String(legacy.reps ?? ''), rpe: String(legacy.rpe ?? '') } },
    };
    return {};
  });
  const [index, setIndex] = useState(() => Math.max(0, Math.min(session.exercises.length - 1, saved.index ?? session.current_exercise_idx ?? 0)));
  const [drafts, setDrafts] = useState(saved.drafts || {});
  const [attempt, setAttempt] = useState(saved.attempt || null);
  const [error, setError] = useState('');
  const [undo, setUndo] = useState(null);
  const [tutorial, setTutorial] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [histories, setHistories] = useState({});
  const [historyStates, setHistoryStates] = useState({});
  const historyBusy = useRef(new Set());
  const [abandon, setAbandon] = useState(false);
  const [abandonError, setAbandonError] = useState('');
  const [deadline, setDeadline] = useState(() => readSaved(`sirius-rest:${userId}:${session.session_id}`, null));
  const [now, setNow] = useState(Date.now());
  const [restDone, setRestDone] = useState(false);
  const busy = useRef(false);
  const exerciseHeading = useRef(null);
  const rest = Math.max(0, Math.ceil(((deadline || 0) - now) / 1000));
  const exercise = session.exercises[index];
  const values = drafts[index] || setDefaults(exercise);
  const progress = workoutSummary(session);
  const next = session.exercises.findIndex((ex, idx) => idx > index && !ex.completed);
  const nextPending = next >= 0 ? next : session.exercises.findIndex((ex, idx) => idx !== index && !ex.completed);
  const suggestion = nextLoads?.suggestions?.find?.(item => item.name === exercise?.name);
  const pending = saving || !!attempt;
  useWorkoutWakeLock(session.status === 'active');

  useEffect(() => { writeSaved(namespace, { index, drafts, attempt }); }, [namespace, index, drafts, attempt]);
  useEffect(() => {
    if (!undo) return;
    const timeout = setTimeout(() => setUndo(null), Math.max(0, undo.expires - Date.now()));
    return () => clearTimeout(timeout);
  }, [undo]);
  useEffect(() => { writeSaved(`sirius-rest:${userId}:${session.session_id}`, deadline); }, [userId, session.session_id, deadline]);
  useEffect(() => {
    if (!deadline) return;
    const tick = () => setNow(Date.now());
    tick(); const timer = setInterval(tick, 500);
    return () => clearInterval(timer);
  }, [deadline]);
  useEffect(() => {
    if (deadline && now >= deadline) {
      setDeadline(null); setRestDone(true);
      try { navigator.vibrate?.(100); } catch { /* Optional one-time feedback. */ }
    }
  }, [deadline, now]);

  const selectExercise = idx => {
    if (pending || busy.current) return;
    // Persist synchronously before navigation/unmount; inputs belong to each exercise.
    writeSaved(namespace, { index: idx, drafts, attempt });
    setIndex(idx); setTutorial(false); setHistoryOpen(false); setError(''); setUndo(null);
    requestAnimationFrame(() => exerciseHeading.current?.focus({ preventScroll: true }));
  };
  const change = (field, value) => {
    const updated = { ...drafts, [index]: { ...values, [field]: value } };
    writeSaved(namespace, { index, drafts: updated, attempt }); setDrafts(updated);
  };
  const save = async (event, undoOperation) => {
    event?.preventDefault();
    if (busy.current || saving) return;
    let operation = attempt || undoOperation;
    try {
      if (!operation) {
        const set = validateSet(values);
        const sets = [...(exercise.sets_data || []), set];
        operation = { index, key: crypto.randomUUID(), body: { sets_data: sets, completed: sets.length >= (exercise.sets || 1), current_exercise_idx: index, revision: session.revision || 0 } };
        // Save the exact request before sending: an uncertain retry replays its receipt.
      }
      writeSaved(namespace, { index, drafts, attempt: operation }); setAttempt(operation);
      busy.current = true; setError('');
      const result = await onSave(operation);
      if (operation.kind === 'undo') setUndo(null);
      else setUndo({ index: operation.index, expires: Date.now() + 20000, body: { sets_data: operation.body.sets_data.slice(0, -1), completed: false, current_exercise_idx: operation.index, revision: result.revision } });
      const updated = { ...drafts }; delete updated[operation.index];
      writeSaved(namespace, { index, drafts: updated, attempt: null });
      setAttempt(null); setDrafts(updated);
      const duration = Number(session.exercises[operation.index].rest_seconds ?? session.rest_timer_seconds ?? 60);
      setRestDone(false); setNow(Date.now()); setDeadline(operation.kind !== 'undo' && duration > 0 ? Date.now() + duration * 1000 : null);
    } catch (failure) {
      const status = failure.response?.status;
      // Definitive rejections did not commit. Allow editing after reconciliation.
      if (status && status >= 400 && status < 500 && ![408, 429].includes(status)) {
        setAttempt(null); writeSaved(namespace, { index, drafts, attempt: null });
      }
      setError(!operation ? failure.message : getApiErrorMessage(failure, 'Não foi possível confirmar a série. Seus dados estão preservados. Tente novamente.'));
    } finally { busy.current = false; }
  };
  const loadHistory = async () => {
    const name = exercise.name;
    if (historyBusy.current.has(name)) return;
    historyBusy.current.add(name); setHistoryStates(prev => ({ ...prev, [name]: 'loading' }));
    try { const result = await onHistory(name); setHistories(prev => ({ ...prev, [name]: result })); setHistoryStates(prev => ({ ...prev, [name]: 'ready' })); }
    catch { setHistoryStates(prev => ({ ...prev, [name]: 'error' })); }
    finally { historyBusy.current.delete(name); }
  };
  const openHistory = () => { setHistoryOpen(!historyOpen); if (!historyOpen && !Object.hasOwn(histories, exercise.name)) loadHistory(); };
  const adjustRest = seconds => { setNow(Date.now()); setDeadline(Math.max(Date.now(), (deadline || Date.now()) + seconds * 1000)); };

  if (!exercise) return <div className="ws-panel"><p>Nenhum exercício disponível nesta sessão.</p><Button onClick={onFinish}>Finalizar treino</Button></div>;
  return <section className="workout-session" aria-label="Modo treino">
    <header className="ws-header">
      <div><p className="ws-eyebrow">Modo treino</p><p className="ws-plan-name">{session.plan_name}</p></div>
      <div className="ws-header-metrics"><span aria-label="Tempo de treino"><Timer size={16} /> {sessionTime(elapsed)}</span><span>{progress.exercises}/{progress.total} exercícios · {progress.total - progress.exercises} restantes</span></div>
      <div className="ws-progress" role="progressbar" aria-label="Progresso do treino" aria-valuemin={0} aria-valuemax={progress.total || 1} aria-valuenow={progress.exercises}><span style={{ width: `${progress.total ? progress.exercises / progress.total * 100 : 0}%` }} /></div>
    </header>
    <div className="ws-layout">
      <div className="ws-focus ws-panel">
        <p className="ws-eyebrow">Exercício {index + 1} de {progress.total}{exercise.muscle_group ? ` · ${exercise.muscle_group}` : ''}</p>
        <h2 ref={exerciseHeading} tabIndex={-1} className="ws-exercise-name">{exercise.name}</h2>
        <p className="ws-prescription">{exercise.sets} séries · {exercise.reps} reps · {exercise.rest_seconds ?? session.rest_timer_seconds ?? 60}s de descanso</p>
        {exercise.notes && <p className="ws-muted">{exercise.notes}</p>}
        <div className="ws-set-track" aria-label="Séries do exercício">{Array.from({ length: Math.min(100, exercise.sets || 1) }, (_, idx) => <span key={idx} className={idx < (exercise.sets_completed || 0) ? 'done' : ''}>{idx < (exercise.sets_completed || 0) ? <Check size={14} /> : idx + 1}</span>)}</div>
        {suggestion?.next_weight != null && <p className="ws-load">Sugestão de carga: <strong>{suggestion.next_weight} kg</strong>{suggestion.current_weight !== '' && suggestion.current_weight != null ? ` · Prescrita: ${suggestion.current_weight} kg` : ''}</p>}
        {loadError && <p className="ws-muted">Sugestão de carga indisponível. Use a carga adequada ao seu treino.</p>}
        {(rest > 0 || restDone) && <div className="ws-rest">
          <div><p className="ws-eyebrow">Descanso</p><strong className="ws-rest-time">{rest > 0 ? sessionTime(rest) : 'Pronto para continuar'}</strong></div>
          {rest > 0 && <div className="ws-rest-actions"><Button variant="outline" aria-label="Diminuir descanso em 15 segundos" onClick={() => adjustRest(-15)}>-15s</Button><Button variant="ghost" onClick={() => { setDeadline(null); setRestDone(true); }}>Pular</Button><Button variant="outline" aria-label="Aumentar descanso em 15 segundos" onClick={() => adjustRest(15)}>+15s</Button></div>}
          <p className="ws-muted">{exercise.completed ? 'Exercício concluído. Continue quando estiver pronto.' : `Próxima: série ${(exercise.sets_completed || 0) + 1} de ${exercise.sets} · ${values.weight ? `${values.weight} kg · ` : ''}${exercise.reps} reps`}</p>
        </div>}
        <p className="ws-announcement" role="status">{restDone ? 'Descanso finalizado.' : ''}</p>
        {!exercise.completed || attempt ? <form onSubmit={save} className="ws-set-form">
          <h3>Série {Math.min((exercise.sets_completed || 0) + 1, exercise.sets || 1)} de {exercise.sets}</h3>
          <div className="ws-inputs">
            <label htmlFor="ws-weight">Carga <span>kg · opcional</span><input id="ws-weight" aria-label="Carga da série" inputMode="decimal" type="text" maxLength={14} value={values.weight} disabled={pending} onChange={e => change('weight', e.target.value)} placeholder="—" /></label>
            <label htmlFor="ws-reps">Repetições<input id="ws-reps" aria-label="Repetições da série" inputMode="numeric" type="number" min="1" max="999" value={values.reps} disabled={pending} onChange={e => change('reps', e.target.value)} /></label>
            <label htmlFor="ws-rpe">RPE <span>1–10 · opcional</span><input id="ws-rpe" aria-label="Esforço percebido da série (RPE)" inputMode="decimal" type="text" maxLength={4} value={values.rpe} disabled={pending} onChange={e => change('rpe', e.target.value)} placeholder="—" /></label>
          </div>
          {error && <p role="alert" className="ws-error">{error}</p>}
          {attempt && !saving && !error && <p role="status" className="ws-muted">Existe um registro pendente de confirmação. Tente novamente antes de continuar.</p>}
          <div className="ws-primary-action"><p>{values.weight ? `${values.weight} kg · ` : ''}{values.reps || '—'} reps{values.rpe ? ` · RPE ${values.rpe}` : ''}</p><Button type="submit" disabled={saving} className="ws-complete-set">{saving ? <Loader2 className="animate-spin" size={20} /> : <Check size={20} />}{attempt && !saving ? 'Tentar salvar novamente' : saving ? 'Salvando série…' : 'Concluir série'}</Button></div>
        </form> : <div className="ws-completed" role="status"><Check size={24} /><h3>Exercício concluído</h3>{nextPending >= 0 ? <Button className="ws-next" onClick={() => selectExercise(nextPending)}>Ir para próximo <ArrowRight size={18} /></Button> : <Button className="ws-next" disabled={saving} onClick={onFinish}>Finalizar treino</Button>}</div>}
        {!!exercise.sets_data?.length && <details className="ws-recorded"><summary>Séries registradas ({exercise.sets_data.length})</summary><ol>{exercise.sets_data.map((set, idx) => <li key={idx}>Série {idx + 1}: {set.weight !== '' && set.weight != null ? `${set.weight} kg` : 'Carga não registrada'} × {set.reps} reps{set.rpe !== '' && set.rpe != null ? ` · RPE ${set.rpe}` : ''}</li>)}</ol></details>}
        {undo && !pending && <div className="ws-undo"><span role="status">Série registrada.</span><Button variant="ghost" onClick={() => { if (Date.now() < undo.expires) save(null, { index: undo.index, body: undo.body, key: crypto.randomUUID(), kind: 'undo' }); else setUndo(null); }}>Desfazer última série</Button></div>}
        <div className="ws-secondary-actions"><Button variant="outline" aria-label={`Ver tutorial de ${exercise.name}`} aria-expanded={tutorial} onClick={() => setTutorial(!tutorial)}>Como executar</Button><Button variant="outline" aria-expanded={historyOpen} onClick={openHistory}>Histórico</Button></div>
        {tutorial && <div className="ws-tutorial"><WorkoutTutorial key={exercise.name} exercise={exercise} /></div>}
        {historyOpen && <HistoryPreview exercise={exercise} history={histories[exercise.name]} loading={historyStates[exercise.name] === 'loading'} error={historyStates[exercise.name] === 'error'} onRetry={loadHistory} />}
        <details className="ws-rest-settings"><summary>Configurar descanso</summary><div className="ws-rest-presets">{[30, 60, 90, 120].map(seconds => <Button key={seconds} variant="outline" onClick={() => { setRestDone(false); setNow(Date.now()); setDeadline(Date.now() + seconds * 1000); }}>{seconds}s</Button>)}</div></details>
      </div>
      <aside className="ws-queue ws-panel" aria-label="Fila de exercícios"><h3><Dumbbell size={18} /> Treino de hoje</h3><ol>{session.exercises.map((ex, idx) => <li key={idx}><button type="button" aria-current={idx === index ? 'step' : undefined} aria-label={`Selecionar exercício ${idx + 1}: ${ex.name}`} disabled={pending} onClick={() => selectExercise(idx)}><span className={`ws-queue-marker ${ex.completed ? 'done' : ''}`}>{ex.completed ? <Check size={16} /> : idx + 1}</span><span className="ws-queue-name">{ex.name}<small>{ex.completed ? 'Concluído' : idx === index ? 'Atual' : 'Pendente'} · {ex.sets_completed || 0}/{ex.sets} séries</small></span></button></li>)}</ol></aside>
    </div>
    <footer className="ws-footer"><Button disabled={pending} className="ws-finish" onClick={onFinish}>Finalizar treino</Button><Button disabled={pending} variant="ghost" onClick={() => setAbandon(true)}>Abandonar sessão</Button></footer>
    <Dialog open={abandon} onOpenChange={value => { if (!saving) { setAbandon(value); setAbandonError(''); } }}><DialogContent className="ws-dialog"><DialogHeader><DialogTitle>Abandonar sessão?</DialogTitle><DialogDescription>Você registrou {progress.sets} séries e concluiu {progress.exercises} exercícios. A sessão será encerrada sem a recompensa de conclusão.</DialogDescription></DialogHeader>{abandonError && <p role="alert" className="ws-error">{abandonError}</p>}<div className="ws-dialog-actions"><Button variant="outline" disabled={saving} onClick={() => setAbandon(false)}>Continuar treino</Button><Button disabled={saving} onClick={async () => { try { await onAbandon(); } catch (failure) { setAbandonError(getApiErrorMessage(failure, 'Não foi possível abandonar. Tente novamente.')); } }}>Confirmar abandono</Button></div></DialogContent></Dialog>
  </section>;
}
