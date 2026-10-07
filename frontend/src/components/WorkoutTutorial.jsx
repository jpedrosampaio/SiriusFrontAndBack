import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { cacheKey } from '@/lib/query-cache';

export default function WorkoutTutorial({ exercise }) {
  const [watch, setWatch] = useState(null);
  const name = exercise.name || '';
  const group = exercise.muscle_group || '';
  const { data, isPending, isError, refetch } = useQuery({
    queryKey: cacheKey('tutorial-videos', name.trim().toLocaleLowerCase('pt-BR'), group.trim().toLocaleLowerCase('pt-BR')),
    staleTime: 86400000, retry: false,
    queryFn: async ({ signal }) => (await axios.get(`${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000'}/api/workouts/tutorial-videos`, {
      params: { exercise: name, muscle_group: group }, signal, timeout: 12000,
    })).data,
  });
  return <section className="space-y-3 text-sm" aria-label={`Tutorial de ${name}`}>
    <h3 className="font-medium text-purple-300">Como executar</h3>
    <p className="text-slate-300 whitespace-pre-wrap">{exercise.tutorial || 'Use uma carga confortável, controle o movimento e peça orientação presencial para conferir a execução.'}</p>
    <h4 className="font-medium">Vídeos relacionados</h4>
    {isPending && <p role="status" className="text-xs text-slate-400">Buscando vídeos…</p>}
    {(isError || (data && data.status !== 'ok')) && <p className="text-xs text-slate-400">Vídeos indisponíveis no momento. Seu treino continua disponível. <button type="button" onClick={() => refetch()} className="underline">Tentar buscar novamente</button></p>}
    {data?.status === 'ok' && !data.videos?.length && <p className="text-xs text-slate-400">Nenhum vídeo relacionado encontrado.</p>}
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">{data?.videos?.slice(0, 3).map(video => <article key={video.video_id} className="min-w-0 rounded-lg border border-slate-700 p-2">
      {watch === video.video_id ? <iframe title={`Execução de ${name}: ${video.title}`} src={`https://www.youtube-nocookie.com/embed/${video.video_id}`} loading="lazy" className="aspect-video w-full rounded" allow="fullscreen" allowFullScreen /> : <img src={video.thumbnail} alt={`Prévia de ${video.title}`} loading="lazy" className="aspect-video w-full object-cover rounded" />}
      <p className="mt-2 break-words text-xs">{video.title}</p><p className="text-xs text-slate-400">{video.channel}</p>
      <div className="flex flex-wrap gap-3 mt-2 text-xs"><button type="button" className="text-sky-300 underline" onClick={() => setWatch(watch === video.video_id ? null : video.video_id)}>{watch === video.video_id ? 'Fechar vídeo' : 'Assistir aqui'}</button><a href={video.url} target="_blank" rel="noopener noreferrer" className="underline">Abrir no YouTube</a></div>
    </article>)}</div>
    <p className="text-xs text-slate-500">Conteúdo externo do YouTube. Os vídeos complementam o tutorial textual.</p>
  </section>;
}
