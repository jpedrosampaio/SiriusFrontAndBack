import { useState } from 'react';
import { Check, Copy } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { publicDiagnostic, rejectionCategories, validationStages, validationRules } from '@/lib/edital-diagnostics';

export default function EditalProviderDiagnostic({ item }) {
  const [copyState, setCopyState] = useState('');
  if (!item) return null;
  const diagnostic = publicDiagnostic(item);
  const validation = diagnostic.response_validation;
  const copy = async () => {
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(JSON.stringify(diagnostic, null, 2));
      setCopyState('copied');
    } catch { setCopyState('unavailable'); }
  };
  return <section aria-label="Diagnóstico do provedor" className="min-w-0 space-y-3 border-t border-white/[0.07] pt-4">
    <div className="flex items-start justify-between gap-3"><h3 className="text-xs font-medium text-amber-200">{validation || diagnostic.category === 'output_validation' ? 'A resposta da IA não passou na validação' : diagnostic.http_status === 400 ? 'A IA recusou a solicitação' : 'A análise aguarda o provedor'}</h3>{diagnostic.http_status && <span className="shrink-0 rounded bg-amber-200/10 px-1.5 py-0.5 font-mono text-[10px] text-amber-200">HTTP {diagnostic.http_status}</span>}</div>
    <p className="text-xs leading-relaxed text-zinc-400">Seu documento continua salvo. O diagnóstico abaixo registra a tentativa e não confirma a identificação de cargos.</p>
    <details><summary className="cursor-pointer text-xs text-zinc-400 hover:text-white">Ver detalhes técnicos</summary><dl className="mt-3 grid gap-3 text-xs [overflow-wrap:anywhere]">
      <div><dt className="text-zinc-500">Provedor e modelo observados</dt><dd className="mt-1 text-zinc-300">{[diagnostic.provider, diagnostic.model].filter(Boolean).join(' / ') || 'Não informado'}</dd></div>
      <div><dt className="text-zinc-500">Motivo sanitizado</dt><dd className="mt-1 text-zinc-300">{diagnostic.provider_status || diagnostic.provider_code || 'Sem status registrado'} · {rejectionCategories[diagnostic.category] || 'Sem categoria registrada'}</dd></div>
      {validation && <>
        <div><dt className="text-zinc-500">Etapa da validação</dt><dd className="mt-1 text-zinc-300">{validationStages[validation.stage]} · {validation.code}</dd></div>
        <div><dt className="text-zinc-500">Primeiro campo rejeitado</dt><dd className="mt-1 font-mono text-zinc-300">{validation.path}</dd></div>
        <div><dt className="text-zinc-500">Regra identificada</dt><dd className="mt-1 text-zinc-300">{validationRules[validation.rule] || 'Regra específica não informada'}</dd></div>
      </>}
      <div><dt className="text-zinc-500">Campo rejeitado pelo provedor</dt><dd className="mt-1 text-zinc-300">{diagnostic.fields.join(', ') || 'Ainda não identificado no diagnóstico seguro'}</dd></div>
      <div><dt className="text-zinc-500">Referência</dt><dd className="mt-1 font-mono text-zinc-300">{diagnostic.reference || 'Não disponível'}</dd></div>
      <div><dt className="text-zinc-500">Formato e schema</dt><dd className="mt-1 text-zinc-300">{diagnostic.request_format || 'Não registrado'}{diagnostic.schema_bytes ? ` · ${diagnostic.schema_bytes} bytes` : ''}</dd>{diagnostic.schema_sha256 && <dd className="mt-1 font-mono text-zinc-500">{diagnostic.schema_sha256}</dd>}</div>
      <div><dt className="text-zinc-500">Chamadas reservadas deste lote</dt><dd className="mt-1 text-zinc-300">{diagnostic.unit_reserved_calls ?? 'Não informado'} · separado do total da análise</dd></div>
    </dl></details>
    <Button variant="ghost" size="sm" onClick={copy} className="max-w-full gap-2 px-0 text-xs text-zinc-400 hover:bg-transparent hover:text-white"><Copy size={13} />Copiar diagnóstico seguro</Button>
    {copyState && <p role="status" className="text-xs text-zinc-300">{copyState === 'copied' ? <span className="inline-flex items-center gap-1"><Check size={13} />Diagnóstico copiado.</span> : 'Não foi possível copiar. Consulte os detalhes técnicos acima.'}</p>}
  </section>;
}
