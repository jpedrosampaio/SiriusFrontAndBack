import { useState } from 'react';
import { AlertTriangle, Check, Copy, ShieldCheck } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { publicDiagnostic, rejectionCategories } from '@/lib/edital-diagnostics';

export default function EditalProviderDiagnostic({ item }) {
  const [copyState, setCopyState] = useState('');
  if (!item) return null;
  const diagnostic = publicDiagnostic(item);
  const copy = async () => {
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(JSON.stringify(diagnostic, null, 2));
      setCopyState('copied');
    } catch { setCopyState('unavailable'); }
  };
  return <section aria-label="Diagnóstico do provedor" className="min-w-0 rounded-2xl border border-amber-400/25 bg-amber-400/[0.04] p-4 sm:p-5 space-y-4">
    <div className="flex flex-wrap items-start justify-between gap-3"><div className="flex min-w-0 items-start gap-3"><span className="rounded-xl bg-amber-400/10 p-2 text-amber-300"><AlertTriangle size={18} /></span><div className="min-w-0">
      <h3 className="font-semibold text-amber-100">{diagnostic.http_status === 400 ? 'A IA recusou a solicitação' : 'A análise aguarda o provedor'}</h3>
      <p className="mt-1 text-sm text-slate-300">{diagnostic.http_status ? `HTTP ${diagnostic.http_status}` : 'Sem resposta HTTP registrada'}{diagnostic.provider_status ? ` · ${diagnostic.provider_status}` : ''} · {rejectionCategories[diagnostic.category] || 'Confira os detalhes públicos da última tentativa'}</p>
    </div></div><Button variant="outline" size="sm" onClick={copy} className="max-w-full gap-2 border-amber-400/20 bg-transparent text-amber-100"><Copy size={14} />Copiar diagnóstico seguro</Button></div>
    <p className="text-sm leading-relaxed text-slate-300">O texto e os checkpoints continuam salvos. Uma recusa não valida cargos ou conteúdo; repetir a mesma solicitação pode consumir outra tentativa sem resolver o bloqueio.</p>
    <div className="grid gap-3 sm:grid-cols-2 text-xs"><div><p className="text-slate-500">Provedor e modelo observados</p><p className="mt-1 break-words text-slate-200">{[diagnostic.provider, diagnostic.model].filter(Boolean).join(' / ') || 'Não informado'}</p></div><div><p className="text-slate-500">Campo rejeitado identificado</p><p className="mt-1 break-words text-slate-200">{diagnostic.fields.join(', ') || 'Ainda não identificado no diagnóstico seguro'}</p></div></div>
    <details className="border-t border-amber-400/15 pt-3"><summary className="cursor-pointer py-1 text-xs text-amber-200">Detalhes técnicos públicos</summary><dl className="mt-3 grid gap-3 text-xs [overflow-wrap:anywhere]">
      <div><dt className="text-slate-500">Referência</dt><dd className="mt-1 font-mono text-slate-200">{diagnostic.reference || 'Não disponível'}</dd></div>
      <div><dt className="text-slate-500">Formato e schema</dt><dd className="mt-1 text-slate-200">{diagnostic.request_format || 'Não registrado'}{diagnostic.schema_bytes ? ` · ${diagnostic.schema_bytes} bytes` : ''}</dd>{diagnostic.schema_sha256 && <dd className="mt-1 font-mono text-slate-400">{diagnostic.schema_sha256}</dd>}</div>
      <div><dt className="text-slate-500">Chamadas reservadas deste lote</dt><dd className="mt-1 text-slate-200">{diagnostic.unit_reserved_calls ?? 'Não informado'} · contador separado do total da análise</dd></div>
    </dl></details>
    <p className="flex items-center gap-2 text-xs text-slate-400"><ShieldCheck size={14} className="shrink-0" />Somente metadados públicos. O diagnóstico não inclui PDF, prompts ou credenciais.</p>
    {copyState && <p role="status" className="text-xs text-amber-100">{copyState === 'copied' ? <span className="inline-flex items-center gap-1"><Check size={13} />Diagnóstico copiado.</span> : 'Não foi possível copiar. Consulte os detalhes técnicos públicos acima.'}</p>}
  </section>;
}
