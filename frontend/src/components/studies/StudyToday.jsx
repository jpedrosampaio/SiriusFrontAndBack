import { useEffect, useState } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { openSirius } from '@/lib/sirius-context';
import IndividualPractice from './IndividualPractice';
const API = `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000'}/api/study/v2`;
export default function StudyToday({ onSession, onPrepare, onFreeSession, onReviewCards }) {
  const [today, setToday] = useState(null), [reviews, setReviews] = useState([]), [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([axios.get(`${API}/today`, { signal: controller.signal }), axios.get(`${API}/reviews`, { signal: controller.signal })])
      .then(([t, r]) => { setToday(t.data); setReviews(r.data.items || []); })
      .catch(() => { if (!controller.signal.aborted) setError('Não foi possível carregar sua próxima atividade.'); });
    return () => controller.abort();
  }, []);
  const next = today?.next_session;
  return <div className="space-y-8">
    {error && <p role="alert">{error}</p>}
    <section className="sirius-hero p-5 sm:p-7 rounded-2xl">
      <p className="sirius-eyebrow">Sua próxima sessão</p><h2 className="text-xl sm:text-2xl font-semibold mt-2">{next?.name || 'Um momento para aprender'}</h2>
      <p className="text-slate-300 text-sm mt-2 mb-5">{next ? `${next.minutes} minutos · ${next.kind}` : 'Comece uma sessão livre ou organize uma preparação.'}</p>
      <Button onClick={() => next ? onSession(next) : onFreeSession()}>Começar</Button><Button variant="ghost" onClick={onPrepare}>Ver preparações</Button>
    </section>
    <div className="flex flex-wrap gap-8 text-sm"><div><p className="text-slate-400">Planejado hoje</p><strong className="text-xl">{today?.planned_minutes ?? '—'} min</strong></div><div><p className="text-slate-400">Estudado hoje</p><strong className="text-xl">{today?.studied_minutes ?? '—'} min</strong></div><div><p className="text-slate-400">Revisões pendentes</p><strong className="text-xl">{reviews.length}</strong></div></div>
    <section><h2 className="text-lg font-medium mb-3">Revisões de hoje</h2>{reviews.length === 0 && <p className="text-sm text-slate-400">Nenhuma revisão vencida registrada.</p>}{reviews.slice(0, 20).map((r, i) => <div key={`${r.notebook_id}-${i}`} className="flex flex-wrap items-center justify-between gap-3 py-4 border-b border-slate-800"><div><span className="text-xs text-purple-300">{r.kind === 'flashcard' ? 'Flashcard' : 'Assunto'}</span><p>{r.title}</p><p className="text-xs text-slate-400 mt-1">{r.reason}</p></div><Button variant="secondary" onClick={() => r.kind === 'flashcard' ? onReviewCards(r) : onSession({ ...r, minutes: 25 })}>Revisar</Button></div>)}</section>
    <button className="text-sm text-purple-300" onClick={() => openSirius({ surface: 'studies', draft: 'O que devo priorizar nos estudos hoje?' })}>Perguntar ao Sirius sobre meus estudos</button>
    {reviews.filter(r => r.kind === 'wrong_question').slice(0, 10).map(r => <section key={r.attempt_id}><h3 className="text-sm text-purple-300">Refazer questão · {r.title}</h3><IndividualPractice previous={r} notebookId={r.notebook_id} topicKey={r.topic_key} onSaved={() => setReviews(rows => rows.filter(row => row.attempt_id !== r.attempt_id))} /></section>)}
  </div>;
}
