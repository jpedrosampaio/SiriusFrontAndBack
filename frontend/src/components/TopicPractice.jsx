import { useEffect, useRef, useState } from 'react';
import axios from '@/lib/module-requests';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { getApiErrorMessage } from '@/lib/api-errors';
import { displayStudyDate } from '@/lib/study-workspace';

export default function TopicPractice({ api, notebookId, topic }) {
  const [reviews, setReviews] = useState([]);
  const [total, setTotal] = useState(10);
  const [correct, setCorrect] = useState(0);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const pending = useRef(null);
  useEffect(() => {
    const controller = new AbortController();
    axios.get(`${api}/study/notebooks/${notebookId}/reviews`, { signal: controller.signal })
      .then(r => setReviews(r.data)).catch(e => { if (!controller.signal.aborted) setMessage(getApiErrorMessage(e, 'Não foi possível carregar as revisões.')); });
    return () => controller.abort();
  }, [api, notebookId]);
  const save = async () => {
    if (busy || !topic) return;
    const body = { topic_key: topic.key, total: Number(total), correct: Number(correct) };
    const fingerprint = JSON.stringify(body);
    if (pending.current?.fingerprint !== fingerprint) pending.current = { fingerprint, key: crypto.randomUUID() };
    setBusy(true); setMessage('');
    try {
      const { data } = await axios.post(`${api}/study/notebooks/${notebookId}/practice`, body, { headers: { 'Idempotency-Key': pending.current.key } });
      setReviews(old => [...old.filter(r => r.topic_key !== data.topic_key), data].sort((a, b) => a.due_date.localeCompare(b.due_date)));
      pending.current = null;
      window.dispatchEvent(new Event('sirius-study-performance'));
      setMessage(`Resultado salvo. Próxima revisão sugerida: ${displayStudyDate(data.due_date)}.`);
    } catch (e) { setMessage(getApiErrorMessage(e, 'Não foi possível salvar. Tente novamente.')); }
    finally { setBusy(false); }
  };
  return <section className="rounded-2xl border border-slate-700 p-5 space-y-4">
    <h3 className="font-semibold">Questões e revisões por assunto</h3>
    {topic ? <><p className="text-sm text-slate-300">{topic.title}</p><div className="grid grid-cols-2 gap-3"><label className="text-sm">Resolvidas<Input type="number" min="1" max="1000" value={total} disabled={busy} onChange={e => setTotal(e.target.value)} /></label><label className="text-sm">Acertos<Input type="number" min="0" max={total} value={correct} disabled={busy} onChange={e => setCorrect(e.target.value)} /></label></div><Button disabled={busy || Number(total) < 1 || Number(correct) < 0 || Number(correct) > Number(total)} onClick={save}>{busy ? 'Salvando…' : 'Registrar resultado deste assunto'}</Button></> : <p className="text-sm text-slate-400">Selecione um assunto no edital verticalizado para registrar questões.</p>}
    <p className="text-xs text-slate-400">Registre cada resolução uma vez. Este registro alimenta os indicadores, sem conceder XP. Sugestão de revisão: 1 dia abaixo de 60% de acertos, 7 dias abaixo de 85% e 21 dias nos demais casos.</p>
    {message && <p role="status" className="text-sm text-blue-200">{message}</p>}
    {reviews.length > 0 && <details><summary className="cursor-pointer text-sm">Fila de revisão · {reviews.length} assuntos</summary><ul className="mt-3 space-y-3">{reviews.map(r => <li key={r.topic_key} className="text-sm border-t border-slate-700 pt-3"><strong>{r.title}</strong><p className="text-slate-400">{displayStudyDate(r.due_date)} · último resultado: {r.correct}/{r.total} ({r.accuracy}%)</p></li>)}</ul></details>}
  </section>;
}
