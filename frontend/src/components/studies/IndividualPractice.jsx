import { useRef, useState } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { errorLabels } from '@/lib/study-errors';
import { getApiErrorMessage } from '@/lib/api-errors';
const API = `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000'}/api/study/v2`;
const field = 'block w-full bg-slate-900 border border-slate-700 rounded-lg p-2 mt-1';
export default function IndividualPractice({ notebookId, topicKey, onSaved, previous }) {
  const [form, setForm] = useState({ question: previous?.question || '', question_id: previous?.question_id || null, answer: '', correct: false, error_reason: 'unknown', seconds: 0, source: previous ? 'error_review' : 'manual' });
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const pending = useRef(null);
  const save = async e => {
    e.preventDefault(); if (busy) return; setBusy(true); setError(''); setNotice('');
    const body = { ...form, notebook_id: notebookId, topic_key: topicKey, error_reason: form.correct ? null : form.error_reason };
    const text = JSON.stringify(body);
    if (pending.current?.text !== text) pending.current = { text, key: crypto.randomUUID() };
    try { const { data } = await axios.post(`${API}/attempts`, body, { headers: { 'Idempotency-Key': pending.current.key } }); pending.current = null; setNotice(`Resposta registrada. Revisão sugerida: ${data.review.due_date}.`); setForm(f => ({ ...f, question: '', answer: '' })); onSaved?.(); }
    catch (err) { setError(getApiErrorMessage(err, 'Não foi possível registrar a resposta.')); }
    finally { setBusy(false); }
  };
  return <details className="py-4 border-t border-slate-700"><summary className="cursor-pointer font-medium">Registrar questão individual e motivo do erro</summary><form onSubmit={save} className="space-y-3 mt-4 text-sm"><p className="text-slate-400">Use para questões externas. Não registre novamente respostas já contabilizadas no Sirius.</p><label className="block">Questão ou referência<textarea required maxLength={12000} className={field} value={form.question} onChange={e => setForm({ ...form, question: e.target.value })} /></label><label className="block">Sua resposta<input maxLength={4000} className={field} value={form.answer} onChange={e => setForm({ ...form, answer: e.target.value })} /></label><label className="flex items-center gap-2"><input type="checkbox" checked={form.correct} onChange={e => setForm({ ...form, correct: e.target.checked })} />Acertei esta questão</label>{!form.correct && <label className="block">Motivo<select className={field} value={form.error_reason} onChange={e => setForm({ ...form, error_reason: e.target.value })}>{Object.entries(errorLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>}<label className="block">Tempo em segundos<input type="number" min="0" max="86400" className={field} value={form.seconds} onChange={e => setForm({ ...form, seconds: Number(e.target.value) })} /></label>{error && <p role="alert" className="text-amber-300">{error}</p>}{notice && <p role="status" className="text-green-300">{notice}</p>}<Button disabled={busy || !form.question.trim()} type="submit">{busy ? 'Registrando…' : 'Registrar resposta'}</Button></form></details>;
}
