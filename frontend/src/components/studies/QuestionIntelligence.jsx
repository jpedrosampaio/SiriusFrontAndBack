import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { errorLabels } from '@/lib/study-errors';
import { getApiErrorMessage } from '@/lib/api-errors';
const API = `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000'}/api/study/v2/programs`;
export default function QuestionIntelligence({ programId, refresh, onStudy }) {
  const [data, setData] = useState(null), [error, setError] = useState(''), [busy, setBusy] = useState(false), [retry, setRetry] = useState(0);
  const generation = useRef(0), lock = useRef(false), receipt = useRef(null);
  useEffect(() => {
    const controller = new AbortController(); generation.current += 1; receipt.current = null; lock.current = false; setBusy(false); setData(null); setError('');
    axios.get(`${API}/${programId}/question-intelligence`, { signal: controller.signal }).then(r => { if (!controller.signal.aborted) setData(r.data); }).catch(() => {
      if (!controller.signal.aborted) setError('Não foi possível carregar a análise de questões.');
    });
    return () => { controller.abort(); generation.current += 1; };
  }, [programId, refresh, retry]);
  const mutate = async (intent, url, body) => {
    if (lock.current) return; lock.current = true; setBusy(true); setError(''); const current = generation.current;
    if (receipt.current?.intent !== intent) receipt.current = { intent, key: crypto.randomUUID() };
    try {
      await axios({ method: body ? 'patch' : 'post', url, data: body, headers: { 'Idempotency-Key': receipt.current.key } });
      const response = await axios.get(`${API}/${programId}/question-intelligence`);
      if (current === generation.current) { setData(response.data); receipt.current = null; }
    } catch (e) { if (current === generation.current) setError(getApiErrorMessage(e, 'Não foi possível concluir a análise.')); }
    finally { if (current === generation.current) { lock.current = false; setBusy(false); } }
  };
  return <section className="space-y-4 min-w-0" aria-label="Inteligência de questões"><h3 className="font-semibold">Inteligência de questões</h3>
    <p className="text-sm text-slate-400">Recuperação usa uma resposta correta posterior à última falha na mesma questão. Os agrupamentos salvos são sugestões, preservando suas respostas.</p>
    {error && <div role="alert"><p className="text-amber-300 text-sm">{error}</p><Button variant="ghost" onClick={() => setRetry(n => n + 1)}>Recarregar análise</Button></div>}
    {data && <><div className="rounded-xl border border-slate-700 p-4"><p>Questões com erros: {data.error_bank?.question_count || 0} · Recuperadas: {data.error_bank?.recovered_questions || 0}</p><p className="text-sm text-slate-400 mt-2">Taxa de recuperação: {data.error_bank?.recovery_rate == null ? 'sem amostra' : `${data.error_bank.recovery_rate}%`}</p>
      <ul className="space-y-3 mt-4">{data.error_bank?.items?.slice(0, 20).map((item, i) => <li key={item.question_id || i} className="border-t border-slate-800 pt-3"><p className="text-sm break-words">{item.title} · {item.errors} erros · {errorLabels[item.error_cause] || 'Sem classificação'}</p><p className="text-xs text-slate-400">Última falha: {item.last_error_at.slice(0, 10)} · {item.recovered ? 'Há evidência posterior de recuperação' : 'Sem recuperação registrada'}</p>
        <details className="text-xs mt-2"><summary className="cursor-pointer py-2">Evidências</summary><p className="break-all">Erros: {item.error_evidence_ids.join(', ')}</p><p className="break-all">Acertos posteriores: {item.later_evidence_ids.join(', ') || 'nenhum'}</p></details><Button variant="ghost" onClick={() => onStudy?.(item)}>Revisar assunto</Button></li>)}</ul></div>
      {(data.truncated || data.error_bank?.partial) && <p className="text-amber-300 text-xs">Amostra limitada; confira os limites e o histórico completo.</p>}
      <div className="flex flex-wrap gap-3 items-center"><Button disabled={busy} onClick={() => mutate('analyze', `${API}/${programId}/question-intelligence/analyze`)}>{busy ? 'Processando…' : 'Analisar recorrência dos erros'}</Button><span className="text-xs text-slate-400">Regras determinísticas, sem chamada de IA.</span></div>
      {!!data.related_reviews?.length && <details className="rounded-xl border border-slate-700 p-4"><summary className="cursor-pointer py-2">Revisões relacionadas</summary><ul className="space-y-3 mt-3">{data.related_reviews.map(r => <li key={r.review_id} className="text-sm break-words">{r.title} · {r.due_date || 'Sem data'}<Button variant="ghost" onClick={() => onStudy?.(r)}>Estudar revisão</Button></li>)}</ul></details>}
      {data.suggestions?.map(s => <article key={s.insight_id} className="rounded-xl border border-purple-400/30 p-4"><p className="font-medium">Sugestão · {s.question_count} questões diferentes</p><p className="text-sm mt-2">{errorLabels[s.reason] || 'Sem classificação'} · {s.terms.length ? `Termos recorrentes: ${s.terms.join(', ')}` : 'Confira o conceito comum no assunto'}</p><p className="text-xs text-slate-400 mt-2">{s.notice}</p>{s.computed_at && <p className="text-xs text-slate-400">Análise salva em {s.computed_at.slice(0, 10)} · reanalise após novas respostas.</p>}<details className="text-xs mt-2"><summary className="cursor-pointer py-2">Ver evidências da sugestão</summary><p className="break-all">{s.attempt_ids.join(', ')}</p></details><Button variant="ghost" disabled={busy} onClick={() => mutate(`dismiss:${s.insight_id}`, `${API}/${programId}/question-intelligence/${s.insight_id}`, { status: 'dismissed' })}>Descartar sugestão</Button></article>)}
      {!data.suggestions?.length && <p className="text-xs text-slate-400">Nenhum agrupamento salvo. A análise requer pelo menos três questões diferentes com erros no mesmo assunto e motivo.</p>}
    </>}
  </section>;
}
