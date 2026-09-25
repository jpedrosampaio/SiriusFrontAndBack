import { useEffect, useState } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';

export default function EditalJobs({ api, onOpen }) {
  const [jobs, setJobs] = useState([]);
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true, timer;
    const load = async () => {
      try { const { data } = await axios.get(`${api}/study/edital-jobs`); if (active) { setJobs(data.jobs || []); setError(false); } }
      catch { if (active) setError(true); }
      finally { if (active) timer = setTimeout(load, document.hidden ? 15000 : 5000); }
    };
    load();
    const refresh = () => { clearTimeout(timer); load(); };
    window.addEventListener('edital-job-created', refresh);
    return () => { active = false; clearTimeout(timer); window.removeEventListener('edital-job-created', refresh); };
  }, [api]);
  if (!jobs.length && !error) return null;
  return <section className="rounded-2xl border border-blue-400/30 bg-blue-500/5 p-4 mb-6 space-y-3" aria-label="Análises de edital"><h2 className="font-semibold">Análises de edital</h2><p className="text-xs text-slate-400">Você pode sair desta tela. As análises continuam no servidor e ficam disponíveis aqui.</p>{error && <p role="status" className="text-sm text-amber-300">Sem conexão para atualizar o andamento. Tentando novamente…</p>}{jobs.slice(0, 5).map(job => <div key={job.job_id} className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-700 pt-3"><div className="min-w-0"><p className="text-sm break-words">{job.filename}</p><p className={`text-xs mt-1 ${job.status === 'failed' ? 'text-amber-300' : 'text-slate-400'}`}>{job.phase}</p></div>{job.status === 'completed' && <Button size="sm" variant="outline" onClick={() => onOpen(job.analysis_id)}>Conferir análise</Button>}</div>)}</section>;
}
