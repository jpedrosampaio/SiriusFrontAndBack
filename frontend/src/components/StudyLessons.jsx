import { useEffect, useState } from "react";
import axios from "axios";
import { Button } from "@/components/ui/button";

export default function StudyLessons({ notebookId, topic, api }) {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setResult(null);
    setError(false);
    setLoading(true);
    axios.get(`${api}/study/notebooks/${notebookId}/lessons`, {
      params: { topic: (topic || "").slice(0, 300) }, withCredentials: true, signal: controller.signal,
    }).then(response => { if (!controller.signal.aborted) setResult(response.data); })
      .catch(() => { if (!controller.signal.aborted) setError(true); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [api, notebookId, topic, reload]);

  return <div className="space-y-3 rounded-lg border border-[#27272A] p-4">
    <h3 className="font-medium">Aulas relacionadas no YouTube</h3>
    {loading && <p role="status" className="text-sm text-[#A1A1AA]">Buscando aulas…</p>}
    {error && <div role="alert" className="text-sm text-amber-300"><p>Não foi possível carregar as aulas.</p><Button variant="outline" className="mt-2" onClick={() => setReload(n => n + 1)}>Tentar novamente</Button></div>}
    {result?.message && <p className="text-sm text-[#A1A1AA]">{result.message}</p>}
    {result?.status === "ok" && !result.videos?.length && <p className="text-sm text-[#A1A1AA]">Nenhuma aula encontrada para este assunto.</p>}
    {result?.videos?.map(video => <a key={video.video_id} href={video.url} target="_blank" rel="noopener noreferrer" className="block rounded border border-[#27272A] p-3 hover:bg-[#1A1A1A]">
      {/^[A-Za-z0-9_-]{11}$/.test(video.video_id) && <img loading="lazy" src={`https://i.ytimg.com/vi/${video.video_id}/mqdefault.jpg`} alt="" className="w-full aspect-video object-cover rounded mb-3" />}
      <p className="text-sm text-blue-300">{video.title}</p>
      <p className="text-xs text-[#A1A1AA]">{video.channel} · Assistir no YouTube ↗</p>
    </a>)}
    {result?.search_url && <Button variant="outline" asChild><a href={result.search_url} target="_blank" rel="noopener noreferrer">Pesquisar no YouTube ↗</a></Button>}
  </div>;
}
