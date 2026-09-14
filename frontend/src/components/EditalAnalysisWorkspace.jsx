import { useEffect, useState } from 'react';
import axios from 'axios';
import { ArrowLeft, Calendar, FileText, Loader2 } from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import MobileNav from '@/components/MobileNav';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { EditalOverview } from '@/components/StudyProgramWorkspace';
import { getApiErrorMessage } from '@/lib/api-errors';
import { topicRows } from '@/lib/study-workspace';

const field = 'w-full h-10 rounded-lg border border-[#27272A] bg-[#101014] px-3 text-sm';

export default function EditalAnalysisWorkspace({ user, api, analysisId, initialAnalysis, areas, defaultAreaId, form, onFormChange, creating, onCreate, onBack, onReanalyze }) {
  const [analysis, setAnalysis] = useState(initialAnalysis?.analysis_id === analysisId ? initialAnalysis : null);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState(0);
  const [areaId, setAreaId] = useState(defaultAreaId || '');
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError(''); setSelected(0); setAnalysis(null);
    axios.get(`${api}/study/programs/editais/${analysisId}`, { withCredentials: true, signal: controller.signal })
      .then(r => { if (!controller.signal.aborted) setAnalysis(r.data); })
      .catch(e => { if (!controller.signal.aborted) setError(getApiErrorMessage(e, 'Não foi possível abrir a análise.')); });
    return () => controller.abort();
  }, [api, analysisId, reload]);
  const cargo = analysis?.cargos?.[selected];
  const incomplete = !cargo?.disciplinas?.length || cargo.disciplinas_status === 'incompleto';
  return <div className="min-h-screen bg-[#050505] text-white flex"><Sidebar user={user} /><main className="flex-1 min-w-0 md:ml-64 px-4 md:px-8 pt-[84px] md:pt-8 pb-24"><div className="max-w-6xl mx-auto space-y-6">
    <Button variant="ghost" className="-ml-3 text-[#A1A1AA]" onClick={onBack}><ArrowLeft className="h-4 w-4 mr-2" />Meus estudos</Button>
    <header><span className="text-xs text-purple-300">EDITAL ANALISADO</span><h1 className="text-2xl md:text-3xl font-semibold mt-2">{analysis?.concurso?.nome || 'Análise do edital'}</h1><p className="text-sm text-[#A1A1AA] mt-3">Confira o resumo e o conteúdo do cargo antes de organizar seu plano.</p></header>
    {error && <div role="alert" className="text-amber-300"><p>{error}</p><Button variant="outline" className="mt-3" onClick={() => setReload(n => n + 1)}>Tentar novamente</Button></div>}
    {!analysis ? !error && <Loader2 className="animate-spin mx-auto my-12" /> : <>
      <section className="rounded-2xl border border-[#27272A] bg-[#101014] p-5 space-y-3"><label htmlFor="analysis-cargo" className="block text-sm font-medium">Cargo / especialidade</label><select id="analysis-cargo" className={field} value={selected} onChange={e => setSelected(Number(e.target.value))}>{(analysis.cargos || []).map((c, index) => <option key={index} value={index}>{c.nome}{c.disciplinas_status === 'incompleto' ? ' — extração incompleta' : ''}</option>)}</select><p className="text-xs text-[#71717A]">{analysis.cargos?.length || 0} cargos identificados. O conteúdo abaixo corresponde ao cargo selecionado.</p></section>
      <EditalOverview concurso={analysis.concurso} cargo={cargo} filename={analysis.pdf_filename} />
      <Button variant="outline" onClick={onReanalyze}>Atualizar análise enviando o PDF novamente</Button>
      <section className="space-y-4"><h2 className="text-xl font-semibold flex items-center gap-2"><FileText className="h-5 w-5 text-purple-400" />Edital verticalizado · {incomplete ? 'extração incompleta' : `${cargo.disciplinas.length} disciplinas`}</h2>
        {incomplete && <div role="alert" className="rounded-xl border border-amber-500/30 p-4 text-sm text-amber-300">{cargo?.disciplinas_aviso || 'Não foi possível identificar todas as disciplinas deste cargo.'}<Button variant="outline" className="block mt-3" onClick={onReanalyze}>Reanalisar PDF completo</Button></div>}
        {(cargo?.disciplinas || []).map((discipline, index) => <details key={`${selected}:${index}`} className="rounded-xl border border-[#27272A] bg-[#101014]"><summary className="p-4 cursor-pointer"><span className="font-medium text-sm">{discipline.nome}</span><span className="block sm:inline sm:ml-3 text-xs text-[#A1A1AA]">Peso {discipline.peso ?? 'não informado'}{discipline.num_questoes > 0 ? ` · ${discipline.num_questoes} questões` : ''}</span></summary><div className="border-t border-[#27272A] p-4"><p className="text-xs text-[#71717A] mb-3">{discipline.grupo}{discipline.peso_fonte ? ` · Fonte do peso: ${discipline.peso_fonte}` : ' · Peso pendente de conferência no edital'}</p><ol className="space-y-3">{topicRows(discipline).map(row => <li key={row.key} className={`text-sm ${row.depth ? 'ml-6 text-[#A1A1AA]' : 'font-medium'}`}>{row.title}</li>)}</ol></div></details>)}
      </section>
      <section className="rounded-2xl border border-[#27272A] bg-[#101014] p-5 space-y-5"><h2 className="text-xl font-semibold flex items-center gap-2"><Calendar className="h-5 w-5 text-purple-400" />Organizar meu plano</h2><div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <label className="text-sm space-y-2"><span className="block">Área de estudos</span><select className={field} value={areaId} onChange={e => setAreaId(e.target.value)}><option value="">Selecione uma área</option>{areas.map(a => <option key={a.area_id} value={a.area_id}>{a.name}</option>)}</select></label>
        <label className="text-sm space-y-2"><span className="block">Data da prova / meta</span><Input type="date" className={field} value={form.target_date} onChange={e => onFormChange({ ...form, target_date: e.target.value })} /></label>
        <label className="text-sm space-y-2"><span className="block">Horas por dia</span><select className={field} value={form.hours_per_day} onChange={e => onFormChange({ ...form, hours_per_day: Number(e.target.value) })}>{[1, 2, 3, 4, 5, 6, 8, 10, 12].map(h => <option key={h} value={h}>{h}h</option>)}</select></label>
        <label className="text-sm space-y-2"><span className="block">Dias por semana</span><select className={field} value={form.days_per_week} onChange={e => onFormChange({ ...form, days_per_week: Number(e.target.value) })}>{[1, 2, 3, 4, 5, 6, 7].map(d => <option key={d} value={d}>{d} dias</option>)}</select></label>
      </div><Button disabled={creating || incomplete || !areaId} onClick={() => onCreate(analysisId, selected, areaId)} className="bg-purple-600 hover:bg-purple-700">{creating ? <><Loader2 className="animate-spin h-4 w-4 mr-2" />Criando plano…</> : 'Criar programa e cronograma'}</Button><p className="text-xs text-[#71717A]">Será criado um programa para o cargo selecionado. Os programas existentes continuam disponíveis em Meus estudos.</p></section>
    </>}
  </div></main><MobileNav user={user} /></div>;
}
