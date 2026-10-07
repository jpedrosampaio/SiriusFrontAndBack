import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { editalJobsKey, queryEditalJobs, activeEditalJobs, EDITAL_CAPABILITY_STALE } from '@/lib/edital-analysis';
import { Button } from '@/components/ui/button';

export default function EditalJobs({ api, onOpen, onRetry }) {
  const [hidden, setHidden] = useState(document.hidden);
  const query = useQuery({ queryKey: editalJobsKey(), queryFn: ({ signal }) => queryEditalJobs(api, signal), staleTime: EDITAL_CAPABILITY_STALE,
    retry: false, refetchInterval: state => activeEditalJobs(state.state.data) ? (hidden ? 15000 : 5000) : false,
    refetchIntervalInBackground: true, refetchOnWindowFocus: false });
  const { refetch } = query;
  useEffect(() => {
    const refresh = () => { void refetch(); };
    const visibility = () => { setHidden(document.hidden); if (!document.hidden && Date.now() - query.dataUpdatedAt >= EDITAL_CAPABILITY_STALE) refresh(); };
    window.addEventListener('edital-job-created', refresh);
    document.addEventListener('visibilitychange', visibility);
    return () => { window.removeEventListener('edital-job-created', refresh); document.removeEventListener('visibilitychange', visibility); };
  }, [refetch, query.dataUpdatedAt]);
  const jobs = [...(query.data?.jobs || [])].sort((a, b) => Number(['queued', 'running'].includes(b.status)) - Number(['queued', 'running'].includes(a.status)));
  if (!jobs.length && !query.isError) return null;
  const status = job => ({ queued: 'Na fila', running: job.phase || 'Analisando edital', completed: 'Análise pronta', failed: job.phase || 'Não foi possível concluir a análise.' }[job.status] || 'Atualizando análise');
  return <section className="rounded-2xl border border-blue-400/30 bg-blue-500/5 p-4 mb-6 space-y-3" aria-label="Análises de edital"><div className="flex flex-wrap gap-3 justify-between items-center"><h2 className="font-semibold">Análises de edital</h2><Button variant="ghost" disabled={query.isFetching} onClick={() => refetch()}>Atualizar análises</Button></div>{activeEditalJobs(query.data) && <p className="text-xs text-slate-400">Você pode continuar usando o Sirius. As análises em andamento ficam disponíveis aqui.</p>}{query.isError && <p role="status" className="text-sm text-amber-300">Sem conexão para atualizar o andamento. Use Atualizar análises para tentar novamente.</p>}{jobs.slice(0, 5).map(job => <div key={job.job_id} className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-700 pt-3"><div className="min-w-0 flex-1"><p className="text-sm [overflow-wrap:anywhere]">{job.filename}</p><p className={`text-xs mt-1 ${job.status === 'failed' ? 'text-amber-300' : 'text-slate-400'}`}>{status(job)}</p></div>{job.status === 'completed' && <Button size="sm" variant="outline" onClick={() => onOpen(job.analysis_id)}>Conferir análise</Button>}{job.status === 'failed' && <Button size="sm" variant="outline" onClick={() => onRetry?.()}>Tentar novamente</Button>}</div>)}</section>;
}
