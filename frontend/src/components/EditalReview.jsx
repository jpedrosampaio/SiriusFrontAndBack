import { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { getApiErrorMessage } from '@/lib/api-errors';

function linesOf(discipline) {
  return (discipline.conteudo_programatico?.length ? discipline.conteudo_programatico : (discipline.topicos || []).map(assunto => ({ assunto })))
    .map(t => typeof t === 'string' ? t : [t.assunto, ...(Array.isArray(t.subtopicos) ? t.subtopicos : t.subtopicos ? [t.subtopicos] : []).map(s => `  - ${s}`)].join('\n')).join('\n');
}
function parseLines(value) {
  const rows = [];
  value.split('\n').filter(line => line.trim()).forEach(line => {
    if (/^\s*-\s+/.test(line) && rows.length) rows[rows.length - 1].subtopicos.push(line.replace(/^\s*-\s+/, '').trim());
    else rows.push({ assunto: line.trim(), subtopicos: [] });
  });
  return rows;
}

export function SourceEvidence({ api, analysisId, sources = [] }) {
  const [page, setPage] = useState(null);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState('');
  const show = async number => {
    setOpen(true); setPage(null); setError('');
    try { setPage((await axios.get(`${api}/study/programs/editais/${analysisId}/source/${number}`)).data); }
    catch (e) { setError(getApiErrorMessage(e, 'Não foi possível abrir a página.')); }
  };
  return <div className="space-y-2 mt-3">
    <p className="text-xs text-slate-400">{sources.length ? 'Nome localizado nestas páginas do PDF. Confira o cargo e o contexto antes de usar os dados.' : 'Página de origem não identificada nesta análise. Confira o PDF original ou reanalise para registrar as fontes.'}</p>
    {sources.map(source => <details key={source.page} className="text-xs rounded-lg border border-slate-700 p-3"><summary className="cursor-pointer">Página {source.page} · trecho do edital</summary><blockquote className="whitespace-pre-wrap text-slate-300 mt-2">{source.quote}</blockquote>{analysisId && <Button size="sm" variant="ghost" onClick={() => show(source.page)}>Ler texto da página</Button>}</details>)}
    <Dialog open={open} onOpenChange={setOpen}><DialogContent className="max-w-3xl"><DialogHeader><DialogTitle>Fonte · página {page?.page || '…'}</DialogTitle><DialogDescription>Texto extraído do PDF. Tabelas podem perder a disposição original durante a extração.</DialogDescription></DialogHeader><div className="max-h-[65dvh] overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed">{error || page?.text || 'Carregando…'}</div></DialogContent></Dialog>
  </div>;
}

export default function EditalReview({ api, analysis, cargoIndex, onSaved, onEditingChange }) {
  const [editing, setEditing] = useState(false);
  const [subjects, setSubjects] = useState([]);
  const [saving, setSaving] = useState(false);
  const begin = () => {
    setSubjects((analysis.cargos[cargoIndex]?.disciplinas || []).map(d => ({ nome: d.nome, peso: d.peso ?? '', num_questoes: d.num_questoes ?? '', lines: linesOf(d) })));
    setEditing(true); onEditingChange?.(true);
  };
  const change = (index, field, value) => setSubjects(old => old.map((s, i) => index === i ? { ...s, [field]: value } : s));
  const save = async () => {
    setSaving(true);
    try {
      const { data } = await axios.put(`${api}/study/programs/editais/${analysis.analysis_id}/cargos/${cargoIndex}`, { revision: analysis.revision || 0, disciplinas: subjects.map(s => ({ nome: s.nome.trim(), peso: s.peso === '' ? null : Number(s.peso), num_questoes: s.num_questoes === '' ? null : Number(s.num_questoes), conteudo_programatico: parseLines(s.lines) })) });
      onSaved({ ...analysis, ...data }); setEditing(false); onEditingChange?.(false); toast.success('Conteúdo revisado. Confira os dados antes de criar seu programa.');
    } catch (e) { toast.error(getApiErrorMessage(e, 'Confira os nomes, pesos e assuntos antes de salvar.')); }
    finally { setSaving(false); }
  };
  if (!editing) return <Button variant="outline" onClick={begin}>Revisar e corrigir disciplinas</Button>;
  return <section className="rounded-2xl border border-blue-400/40 p-5 space-y-4"><h2 className="text-lg font-semibold">Conferência do conteúdo</h2><p className="text-sm text-slate-400">Um assunto por linha. Use “- ” no início para subtópicos. Deixe peso e questões em branco quando o edital não informar. Ajustes ficam identificados como informados por você.</p>{subjects.map((subject, index) => <div className="space-y-3 rounded-xl border border-slate-700 p-4" key={index}><div className="grid sm:grid-cols-[2fr_1fr_1fr] gap-3"><label className="text-sm">Disciplina<Input value={subject.nome} onChange={e => change(index, 'nome', e.target.value)} /></label><label className="text-sm">Peso<Input type="number" min={0.01} step="any" value={subject.peso} onChange={e => change(index, 'peso', e.target.value)} /></label><label className="text-sm">Questões<Input type="number" min={0} value={subject.num_questoes} onChange={e => change(index, 'num_questoes', e.target.value)} /></label></div><Textarea aria-label={`Assuntos de ${subject.nome || 'nova disciplina'}`} rows={6} value={subject.lines} onChange={e => change(index, 'lines', e.target.value)} /><Button variant="ghost" size="sm" onClick={() => setSubjects(old => old.filter((_, i) => i !== index))}>Remover desta revisão</Button></div>)}<div className="flex flex-wrap gap-3"><Button variant="outline" onClick={() => setSubjects(old => [...old, { nome: '', peso: '', num_questoes: '', lines: '' }])}>Adicionar disciplina</Button><Button disabled={saving || !subjects.length} onClick={save}>{saving ? 'Salvando…' : 'Salvar revisão'}</Button><Button variant="ghost" disabled={saving} onClick={() => { setEditing(false); onEditingChange?.(false); }}>Descartar revisão</Button></div></section>;
}
