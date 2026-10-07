import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { fetchEditalCapability, isStorageUnavailable, editalErrorMessage, EDITAL_DIRECT_TIMEOUT, editalJobsKey } from '@/lib/edital-analysis';
import { queryClient } from '@/lib/query-cache';
import { FileText, Loader2, Upload } from 'lucide-react';
import { toast } from 'sonner';

const leaving = 'Uma análise está em andamento. Se você sair agora, talvez seja necessário reabrir o edital depois. Interromper a espera?';

export default function EditalImportDialog({ open, onOpenChange, api, initialForce, onAnalyzed, onQueued }) {
  const [file, setFile] = useState(null);
  const [force, setForce] = useState(false);
  const [capability, setCapability] = useState(null);
  const [capabilityError, setCapabilityError] = useState(false);
  const [retryCapability, setRetryCapability] = useState(0);
  const [busy, setBusy] = useState(false);
  const [direct, setDirect] = useState(false);
  const [phase, setPhase] = useState('upload');
  const [error, setError] = useState('');
  const [elapsed, setElapsed] = useState(0);
  const started = useRef(0), controller = useRef(null), inFlight = useRef(false);
  const fileInput = useRef(null);
  useEffect(() => { if (open) setForce(!!initialForce); }, [open, initialForce]);
  useEffect(() => {
    if (!open) return;
    let live = true;
    setCapabilityError(false);
    fetchEditalCapability(api).then(data => { if (live) setCapability(data); }).catch(() => { if (live) setCapabilityError(true); });
    return () => { live = false; };
  }, [open, api, initialForce, retryCapability]);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    if (!busy) return;
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - started.current) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [busy]);
  useEffect(() => {
    if (!busy || !direct) return;
    const unload = event => { event.preventDefault(); event.returnValue = ''; };
    const click = event => {
      const anchor = event.target.closest?.('a[href]');
      if (!anchor || anchor.target === '_blank') return;
      const url = new URL(anchor.href, location.href);
      if (url.origin !== location.origin || url.pathname !== location.pathname || url.search !== location.search) {
        if (!window.confirm(leaving)) { event.preventDefault(); event.stopPropagation(); }
        else controller.current?.abort();
      }
    };
    window.addEventListener('beforeunload', unload); document.addEventListener('click', click, true);
    return () => { window.removeEventListener('beforeunload', unload); document.removeEventListener('click', click, true); };
  }, [busy, direct]);
  const close = value => {
    if (!value && busy) { if (!window.confirm(leaving)) return; controller.current?.abort(); }
    onOpenChange(value);
  };
  const choose = selected => {
    setError('');
    const rejection = selected && !selected.name.toLowerCase().endsWith('.pdf') ? 'Selecione um PDF válido.' : selected?.size > 20 * 1024 * 1024 ? 'O PDF deve ter no máximo 20 MB.' : '';
    if (rejection) {
      setFile(null); if (fileInput.current) fileInput.current.value = '';
      setError(rejection); return;
    }
    setFile(selected || null);
    if (!selected && fileInput.current) fileInput.current.value = '';
  };
  const submit = async event => {
    event.preventDefault();
    if (!file || !capability || capabilityError || inFlight.current) return;
    inFlight.current = true; setBusy(true); setError(''); setElapsed(0); started.current = Date.now();
    controller.current = new AbortController();
    const requestController = controller.current;
    const requestKey = editalJobsKey();
    const form = new FormData(); form.append('file', file);
    const suffix = force ? '?force=true' : '';
    const analyzeDirect = async () => {
      setDirect(true); setPhase('upload');
      const { data } = await axios.post(`${api}/study/programs/analyze-edital${suffix}`, form, {
        signal: controller.current.signal, timeout: EDITAL_DIRECT_TIMEOUT,
        onUploadProgress: progress => { if (progress.total && progress.loaded >= progress.total) setPhase('analysis'); },
      });
      if (requestController.signal.aborted) return;
      if (!data?.analysis_id || !Array.isArray(data.cargos) || !data.cargos.length) throw { response: { data: { detail: 'A resposta da IA está incompleta. Reanalise o edital.' } } };
      if (data.cached === true) toast.info('Análise anterior reutilizada.');
      setFile(null); onOpenChange(false); onAnalyzed(data);
    };
    try {
      if (capability.upload_available === false) await analyzeDirect();
      else {
        setDirect(false); setPhase('upload');
        try {
          await axios.post(`${api}/study/edital-jobs${suffix}`, form, { signal: controller.current.signal, timeout: 60000 });
          if (requestController.signal.aborted) return;
          setFile(null); onOpenChange(false);
          void queryClient.invalidateQueries({ queryKey: requestKey, refetchType: 'none' });
          onQueued?.();
          window.dispatchEvent(new Event('edital-job-created'));
          toast.success('Edital enviado para análise. Você pode continuar usando o Sirius.');
        } catch (failure) {
          if (!isStorageUnavailable(failure)) throw failure;
          setCapability(prev => ({ ...prev, upload_available: false }));
          queryClient.setQueryData(requestKey, prev => ({ ...prev, upload_available: false }));
          await analyzeDirect();
        }
      }
    } catch (failure) { setError(editalErrorMessage(failure)); }
    finally { inFlight.current = false; setBusy(false); setDirect(false); controller.current = null; }
  };
  return <Dialog open={open} onOpenChange={close}><DialogContent className="bg-[#101014] border-slate-700 w-[calc(100vw-24px)] max-w-lg max-h-[calc(100dvh-24px)] overflow-y-auto text-white">
    <DialogHeader><DialogTitle className="flex gap-2 items-center"><FileText size={20} className="text-purple-300" />Analisar edital</DialogTitle><DialogDescription>O Sirius identificará o concurso, cargos, disciplinas e conteúdo programático. Depois você escolhe o cargo e configura seu plano.</DialogDescription></DialogHeader>
    <form onSubmit={submit} className="space-y-5 min-w-0">
      <label className="block rounded-xl border border-dashed border-slate-600 bg-slate-900/50 p-5 cursor-pointer"><span className="block font-medium text-sm">PDF do Edital *</span><Upload size={26} className="text-purple-300 my-3" /><span className="block text-sm text-slate-300 [overflow-wrap:anywhere]">{file?.name || 'Selecione o PDF do edital'}</span><span className="block text-xs text-slate-400 mt-2">Máximo 20 MB</span><input ref={fileInput} aria-label="PDF do Edital" type="file" accept=".pdf,application/pdf" className="block mt-3 w-full min-w-0 text-xs file:mr-2 file:rounded-lg file:border-0 file:bg-slate-700 file:p-2 file:text-white" disabled={busy} onChange={e => choose(e.target.files?.[0])} /></label>
      {file && <Button type="button" variant="ghost" disabled={busy} onClick={() => choose(null)}>Remover PDF selecionado</Button>}
      <p className="text-xs text-slate-400">Pesos e número de questões serão apresentados quando houver evidência. Trechos incompletos ficam marcados para conferência.</p>
      <details><summary className="cursor-pointer py-3 text-sm text-slate-300">Opções avançadas</summary><label className="flex gap-3 items-start text-sm text-slate-300 py-2"><input type="checkbox" checked={force} disabled={busy} onChange={e => setForce(e.target.checked)} className="mt-1 accent-purple-400" /><span>Reanalisar PDF e ignorar análise salva</span></label></details>
      {capability?.upload_available === false && !busy && <p className="text-sm text-blue-200">Esta análise será feita nesta tela.</p>}
      {!capability && !capabilityError && <p role="status" className="text-sm text-slate-400">Preparando análise…</p>}
      {capabilityError && <div role="alert"><p className="text-sm text-amber-200">Não foi possível preparar a análise. Tente novamente.</p><Button type="button" variant="outline" onClick={() => setRetryCapability(n => n + 1)}>Atualizar disponibilidade</Button></div>}
      {error && <p role="alert" className="rounded-xl bg-amber-500/10 p-3 text-sm text-amber-200">{error}</p>}
      {busy && <div data-testid="edital-analyze-progress" className="space-y-2 rounded-xl bg-blue-500/10 p-4"><p role="status" className="flex gap-2 items-center text-sm"><Loader2 size={18} className="animate-spin" />{phase === 'upload' ? 'Enviando PDF…' : 'Analisando edital…'}</p><p className="text-xs text-slate-300">{elapsed}s decorridos. {direct ? 'Pode levar alguns minutos dependendo do tamanho do edital. Mantenha esta página aberta.' : 'Enviando edital para análise.'}</p></div>}
      <Button data-testid="analyze-edital-btn" disabled={!file || !capability || capabilityError || busy} type="submit" className="w-full min-h-11 bg-purple-600 hover:bg-purple-700">{busy ? 'Aguarde…' : error ? 'Tentar novamente' : 'Analisar edital'}</Button>
      {busy && direct && <Button type="button" variant="ghost" className="w-full min-h-11" onClick={() => close(false)}>Interromper espera</Button>}
    </form>
  </DialogContent></Dialog>;
}
