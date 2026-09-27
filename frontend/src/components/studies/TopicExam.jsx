import { useRef, useState } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { getApiErrorMessage } from '@/lib/api-errors';
const API = `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000'}/api`;
export default function TopicExam({ programId, notebookId, topic, onStart }) {
  const [count, setCount] = useState(10), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const lock = useRef(false);
  const generate = async () => {
    if (lock.current) return; lock.current = true; setBusy(true); setError('');
    try {
      const { data } = await axios.post(`${API}/study/simulados/generate`, { title: `Questões · ${topic.title}`.slice(0, 180), program_id: programId, notebook_id: notebookId, topic_key: topic.key, num_questions: count, question_type: 'multipla_escolha' }, { timeout: 160000 });
      onStart(data.simulado);
    } catch (e) { setError(getApiErrorMessage(e, 'Não foi possível gerar as questões.')); }
    finally { lock.current = false; setBusy(false); }
  };
  return <section className="rounded-xl bg-slate-900 p-4 space-y-3"><h3 className="font-medium">Praticar este assunto</h3><p className="text-sm text-slate-400">Questões geradas por IA, vinculadas a este tópico. Confira o gabarito; não são questões oficiais.</p><label className="block text-sm">Quantidade <select aria-label="Quantidade de questões do assunto" value={count} onChange={e => setCount(Number(e.target.value))} className="ml-2 rounded bg-slate-800 p-2">{[5, 10, 15, 20].map(n => <option key={n} value={n}>{n}</option>)}</select></label>{error && <p role="alert" className="text-amber-300 text-sm">{error}</p>}<Button disabled={busy} onClick={generate}>{busy ? 'Gerando questões…' : 'Gerar e resolver questões'}</Button></section>;
}
