import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { readSaved, writeSaved, remainingSeconds, newSessionId } from '@/lib/session-storage';

export default function usePersistentFocus({ userId, storageId, initialNotebookId, initialMinutes, topic, onComplete }) {
  const key = `sirius-focus:${userId}:${storageId || initialNotebookId || 'general'}`;
  const defaults = { isRunning: false, isPaused: false, isBreak: false, timeLeft: initialMinutes * 60,
    focusMinutes: initialMinutes, breakMinutes: 5, selectedNb: initialNotebookId, sessionsCompleted: 0, deadline: null, request: null };
  const [state, setState] = useState(() => ({ ...defaults, ...readSaved(key) }));
  const stateRef = useRef(state);
  const [storageError, setStorageError] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(false);
  const busy = useRef(false);
  const callback = useRef(onComplete); callback.current = onComplete;
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const commit = change => {
    const next = { ...stateRef.current, ...(typeof change === 'function' ? change(stateRef.current) : change) };
    stateRef.current = next;
    const persisted = writeSaved(key, next);
    if (mounted.current) { setState(next); setStorageError(!persisted); }
    return next;
  };
  const finish = async () => {
    if (busy.current) return;
    busy.current = true; setSaving(true); setSaveError(false);
    const snapshot = stateRef.current;
    const request = snapshot.request || { id: snapshot.sessionId || newSessionId(), data: {
      notebook_id: snapshot.selectedNb && snapshot.selectedNb !== 'none' ? snapshot.selectedNb : null,
      focus_minutes: snapshot.focusMinutes, break_minutes: snapshot.breakMinutes, notes: topic || null,
    } };
    commit({ request, isPaused: true, timeLeft: 0, deadline: null });
    try {
      await axios.post(`${process.env.REACT_APP_BACKEND_URL}/api/study/focus/complete`, request.data,
        { headers: { 'Idempotency-Key': request.id }, withCredentials: true });
      commit({ request: null, isBreak: true, isRunning: false, isPaused: false,
        sessionsCompleted: snapshot.sessionsCompleted + 1, timeLeft: snapshot.breakMinutes * 60, deadline: null });
      if (mounted.current) { toast.success('Sessão registrada. Hora de descansar.'); callback.current?.(); }
    } catch { if (mounted.current) setSaveError(true); }
    finally { busy.current = false; if (mounted.current) setSaving(false); }
  };
  const finishRef = useRef(finish); finishRef.current = finish;
  useEffect(() => {
    const tick = () => {
      const snapshot = stateRef.current;
      if (!snapshot.isRunning || snapshot.isPaused) return;
      const left = remainingSeconds(snapshot);
      if (left !== snapshot.timeLeft) commit({ timeLeft: left });
      if (left === 0) {
        if (snapshot.isBreak) { commit({ isBreak: false, isRunning: false, deadline: null, timeLeft: snapshot.focusMinutes * 60 }); toast.success('Pausa concluída.'); }
        else finishRef.current();
      }
    };
    tick(); const interval = setInterval(tick, 500);
    document.addEventListener('visibilitychange', tick);
    return () => { clearInterval(interval); document.removeEventListener('visibilitychange', tick); };
    // commit operates on the latest snapshot, independent of render timing.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  const startTimer = () => {
    if (stateRef.current.request) { finish(); return; }
    const snapshot = stateRef.current;
    const seconds = (snapshot.isBreak ? snapshot.breakMinutes : snapshot.focusMinutes) * 60;
    commit({ isRunning: true, isPaused: false, timeLeft: seconds, deadline: Date.now() + seconds * 1000, sessionId: newSessionId() });
  };
  const togglePause = () => commit(s => s.isPaused
    ? { isPaused: false, deadline: Date.now() + s.timeLeft * 1000 }
    : { isPaused: true, timeLeft: remainingSeconds(s), deadline: null });
  const resetTimer = () => { if (!stateRef.current.request) commit({ isRunning: false, isPaused: false, isBreak: false, deadline: null, timeLeft: stateRef.current.focusMinutes * 60 }); };
  return { ...state, storageError, saving, saveError, startTimer, togglePause, resetTimer, retry: finish,
    setFocusMinutes: value => commit({ focusMinutes: value, timeLeft: value * 60 }),
    setBreakMinutes: value => commit({ breakMinutes: value }), setSelectedNb: value => commit({ selectedNb: value }) };
}
