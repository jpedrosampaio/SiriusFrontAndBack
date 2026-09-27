import { useEffect, useState } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
const API = `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000'}/api/study/v2/programs`;
export default function StudyRecommendations({ programId, onStudy }) {
  const [data, setData] = useState(null), [error, setError] = useState('');
  useEffect(() => { const controller = new AbortController(); axios.get(`${API}/${programId}/recommendations`, { signal: controller.signal }).then(r => setData(r.data)).catch(() => { if (!controller.signal.aborted) setError('Recomendações indisponíveis. Sua agenda continua disponível abaixo.'); }); return () => controller.abort(); }, [programId]);
  return <section className="space-y-3"><h2 className="text-lg font-medium">O que merece mais atenção</h2>{error && <p role="status" className="text-sm text-slate-400">{error}</p>}<p className="text-sm text-slate-400">{data?.notice}</p>{(data?.items || []).slice(0, 4).map(item => <div key={`${item.notebook_id}:${item.topic_key}`} className="flex flex-wrap gap-3 justify-between border-b border-slate-800 py-3"><div><p className="text-xs text-purple-300">{item.discipline}</p><h3 className="text-sm font-medium">{item.title}</h3><p className="text-xs text-slate-400 mt-1">{item.reasons.join(' · ')}</p></div><Button variant="ghost" onClick={() => onStudy(item)}>Estudar agora</Button></div>)}</section>;
}
