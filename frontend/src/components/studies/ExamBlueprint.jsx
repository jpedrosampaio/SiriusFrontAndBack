import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { getApiErrorMessage } from '@/lib/api-errors';
const API = `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000'}/api/study/v2/programs`;
export default function ExamBlueprint({ programId, onStart }) {
  const [plan, setPlan] = useState(null), [minutes, setMinutes] = useState(120), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const pending = useRef(null);
  useEffect(() => { axios.get(`${API}/${programId}/blueprint`).then(r => setPlan(r.data)).catch(() => setError('Não foi possível carregar a distribuição.')); }, [programId]);
  const create = async () => {
    if (busy) return; setBusy(true); setError('');
    const body = { title: 'Simulado · distribuição do edital', duration_minutes: minutes };
    const fingerprint = JSON.stringify([programId, body]);
    if (pending.current?.fingerprint !== fingerprint) pending.current = { fingerprint, key: crypto.randomUUID() };
    try { const { data } = await axios.post(`${API}/${programId}/blueprint/simulado`, body, { headers: { 'Idempotency-Key': pending.current.key } }); pending.current = null; onStart(data); }
    catch (e) { setError(getApiErrorMessage(e, 'Não foi possível montar o simulado.')); }
    finally { setBusy(false); }
  };
  return <section className="py-5 border-b border-slate-700 space-y-3"><h3 className="text-lg font-medium">Simulado com a distribuição do edital</h3><p className="text-sm text-slate-400">Reutiliza questões com gabarito dos simulados desta preparação. Não inventa questões para completar uma disciplina.</p>{plan?.distribution?.map(row => <div className="flex justify-between gap-3 text-sm" key={row.notebook_id}><span>{row.name}</span><span>{row.count} questões · peso {row.weight}</span></div>)}<p className="text-xs text-amber-200">{plan?.notice}</p>{!plan?.complete && <p className="text-sm text-slate-400">A análise não informa uma distribuição completa. Confira as quantidades por disciplina.</p>}<label className="block text-sm">Duração em minutos · definida por você <input type="number" min="1" max="600" value={minutes} onChange={e => setMinutes(Number(e.target.value))} className="w-24 ml-2 bg-slate-900 rounded-lg p-2" /></label>{error && <p role="alert" className="text-amber-300 text-sm">{error}</p>}<Button disabled={busy || !plan?.complete || minutes < 1 || minutes > 600} onClick={create}>{busy ? 'Montando…' : `Montar simulado${plan?.total ? ` · ${plan.total} questões` : ''}`}</Button></section>;
}
