import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
const API = `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000'}/api/study/v2/programs`;
const events = { registration: 'Inscrições', exemption: 'Isenção', payment: 'Pagamento', exam: 'Prova', location: 'Local de prova', appeal: 'Recurso', result: 'Resultado' };
const categories = { roles: 'Cargos e vagas', syllabus: 'Conteúdo programático', weights: 'Pesos e questões', rules: 'Regras', calendar: 'Calendário' };
export default function EdictRadar({ programId, refresh }) {
  const [data, setData] = useState(null), [error, setError] = useState(''), [retry, setRetry] = useState(0);
  const [history, setHistory] = useState(null), [loading, setLoading] = useState(false);
  const generation = useRef(0), inFlight = useRef(false);
  useEffect(() => {
    const controller = new AbortController(); generation.current += 1; inFlight.current = false;
    setData(null); setHistory(null); setLoading(false); setError('');
    axios.get(`${API}/${programId}/radar`, { signal: controller.signal }).then(r => setData(r.data)).catch(e => {
      if (!controller.signal.aborted) setError('Não foi possível carregar o radar.');
    });
    return () => { controller.abort(); generation.current += 1; };
  }, [programId, refresh, retry]);
  const showHistory = async (source, offset = 0) => {
    if (inFlight.current) return;
    inFlight.current = true; setLoading(true); const current = generation.current;
    try {
      const response = await axios.get(`${API}/${programId}/sources/${source.source_id}/versions`, { params: { offset } });
      if (current === generation.current) { setHistory({ ...response.data, source }); setError(''); }
    } catch { if (current === generation.current) setError('Não foi possível carregar as versões. Tente novamente.'); }
    finally { if (current === generation.current) { inFlight.current = false; setLoading(false); } }
  };
  return <section className="space-y-4 min-w-0" aria-label="Radar de editais">
    <h3 className="font-semibold">Radar de editais</h3>
    {error && <div role="alert"><p className="text-amber-300 text-sm">{error}</p><Button variant="ghost" onClick={() => setRetry(n => n + 1)}>Tentar novamente</Button></div>}
    {data && <><p className="text-xs text-slate-400">Mudanças classificadas por regras, com confirmação necessária. Seu plano permanece sob seu controle.</p>
      <div className="grid sm:grid-cols-2 gap-3">{data.latest_versions.map(v => <article key={v.version_id} className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 min-w-0">
        <p className="font-medium break-words">{v.details.title}</p><p className="text-xs text-slate-400 mt-1">Observada em {new Date(v.detected_at).toLocaleString('pt-BR')}</p>
        <p className="text-sm mt-2">{v.impact.baseline ? 'Primeira versão registrada' : v.details.legacy ? 'Versão anterior recuperada' : 'Nova versão detectada'}</p>
        <p className="text-xs text-slate-400 mt-2">{v.impact.categories?.map(c => categories[c]).join(' · ') || 'Sem classificação de impacto confirmada'}</p>
        {v.partial && <p className="text-amber-300 text-xs mt-2">Extração parcial; confira o documento completo.</p>}
        <Button variant="ghost" disabled={loading} onClick={() => showHistory(data.sources.find(s => s.source_id === v.source_id))}>Ver histórico</Button>
      </article>)}</div>
      {data.latest_versions.length === 0 && <p className="text-sm text-slate-400">O histórico começa na primeira consulta concluída.</p>}
      <div className="border border-slate-800 rounded-xl p-4"><h4 className="font-medium">Datas das fontes oficiais</h4><p className="text-xs text-slate-400 mt-2">{data.date_notice}</p>
        <ol className="space-y-3 mt-4">{data.dates.map((d, i) => <li key={`${d.version_id}-${i}`} className="text-sm break-words">
          <p>{events[d.event]} · {d.date.split('-').reverse().join('/')}</p>
          <blockquote className="text-xs text-slate-400 mt-1">{d.quote}</blockquote>
          <a className="text-xs text-sky-300" href={d.url} target="_blank" rel="noopener noreferrer">Conferir na fonte ↗</a>
          {d.conflicting_candidates && <p className="text-xs text-amber-300">Há mais de uma data candidata para este evento. Confira o período e as retificações.</p>}
        </li>)}</ol>{data.dates.length === 0 && <p className="text-sm text-slate-400 mt-3">Nenhuma data completa vinculada a um evento foi identificada nas fontes oficiais consultadas.</p>}
      </div></>}
    {history && <div className="border border-purple-400/30 rounded-xl p-4"><div className="flex flex-wrap items-center justify-between gap-2"><h4 className="font-medium break-words">Histórico: {history.source.title}</h4><Button variant="ghost" onClick={() => setHistory(null)}>Fechar histórico</Button></div>
      <ol className="space-y-4 mt-3">{history.items.map(v => <li key={v.version_id} className="text-sm"><p>{new Date(v.detected_at).toLocaleString('pt-BR')} · {v.hash_basis === 'document_bytes' ? 'Hash do PDF' : 'Hash do texto extraído'}</p>
        <details className="mt-2"><summary className="cursor-pointer">Mudanças textuais</summary><p className="text-xs text-slate-400 my-2">Classificação inferida; não representa uma interpretação jurídica.{v.impact.partial && ' Comparação parcial.'}</p>
          {v.impact.added?.map((line, i) => <p key={`a${i}`} className="text-xs text-green-300 break-words my-2">+ {line}</p>)}
          {v.impact.removed?.map((line, i) => <p key={`r${i}`} className="text-xs text-rose-300 break-words my-2">− {line}</p>)}
          {v.impact.baseline && <p className="text-xs text-slate-400">Versão inicial, sem comparação anterior.</p>}
        </details></li>)}</ol>
      {history.next_offset !== null && <Button variant="ghost" disabled={loading} onClick={() => showHistory(history.source, history.next_offset)}>Versões anteriores</Button>}
    </div>}
  </section>;
}
