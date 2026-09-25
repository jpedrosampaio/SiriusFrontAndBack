import { useEffect, useState } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';

export default function StudyPerformance({ api, notebookId, onPractice }) {
  const [result, setResult] = useState(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    const controller = new AbortController(); setResult(null); setError(false);
    axios.get(`${api}/study/notebooks/${notebookId}/learning-summary`, { signal: controller.signal })
      .then(r => { if (!controller.signal.aborted) setResult(r.data); })
      .catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [api, notebookId]);
  return <section className="rounded-2xl border border-slate-700 p-5 space-y-3"><h3 className="font-semibold">Conferir meu aprendizado</h3>{error ? <p className="text-sm text-amber-300">Não foi possível consultar seu desempenho agora.</p> : !result ? <p role="status" className="text-sm text-slate-400">Carregando desempenho…</p> : result.answered ? <p className="text-sm text-slate-300"><strong className="text-2xl text-blue-300">{result.accuracy}%</strong> de acertos em {result.answered} questões registradas nesta disciplina.</p> : <p className="text-sm text-slate-400">Ainda não há questões registradas nesta disciplina. Resolva questões para acompanhar sua evolução.</p>}<p className="text-xs text-slate-400">O indicador reúne a disciplina inteira. Marcar um assunto como dominado não altera a taxa de acertos.</p><Button variant="outline" onClick={onPractice}>Questões, quiz e materiais</Button></section>;
}
