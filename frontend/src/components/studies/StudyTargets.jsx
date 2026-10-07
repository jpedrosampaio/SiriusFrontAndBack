import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { getApiErrorMessage } from '@/lib/api-errors';
const API = `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000'}/api/study/v2`;
const types = { contest: 'Concurso', certification: 'Certificação', academic: 'Acadêmico', course: 'Curso', custom: 'Objetivo pessoal' };
const input = 'bg-slate-900 border border-slate-700 rounded-lg p-2 w-full mt-1';
export default function StudyTargets({ onOpen, onImport, onCreated }) {
  const [targets, setTargets] = useState([]), [open, setOpen] = useState(false), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ name: '', kind: 'contest', institution: '', board: '', position: '', edition: '', exam_date: '' });
  const pending = useRef(null), saving = useRef(false);
  const primaryPending = useRef(null), primarySaving = useRef(false);
  const [primaryBusy, setPrimaryBusy] = useState(false);
  const load = () => axios.get(`${API}/targets`).then(r => setTargets(Array.isArray(r.data) ? r.data : []));
  useEffect(() => { load().catch(() => setError('Não foi possível carregar as preparações.')); }, []);
  const makePrimary = async t => {
    if (primarySaving.current) return;
    primarySaving.current = true; setPrimaryBusy(true); setError('');
    if (primaryPending.current?.id !== t.program_id) primaryPending.current = { id: t.program_id, key: crypto.randomUUID() };
    try {
      await axios.put(`${API}/programs/${t.program_id}/primary`, {}, { headers: { 'Idempotency-Key': primaryPending.current.key } });
      await load(); primaryPending.current = null;
    } catch (err) { setError(getApiErrorMessage(err, 'Não foi possível definir a preparação principal.')); }
    finally { primarySaving.current = false; setPrimaryBusy(false); }
  };
  const save = async e => {
    e.preventDefault(); if (saving.current) return; saving.current = true; setBusy(true); setError('');
    const payload = { ...form, exam_date: form.exam_date || null }, fingerprint = JSON.stringify(payload);
    if (pending.current?.fingerprint !== fingerprint) pending.current = { fingerprint, key: crypto.randomUUID() };
    try { const { data } = await axios.post(`${API}/targets`, payload, { headers: { 'Idempotency-Key': pending.current.key } }); await load(); await onCreated(); pending.current = null; setOpen(false); onOpen(data); }
    catch (err) { setError(getApiErrorMessage(err, 'Não foi possível criar a preparação.')); }
    finally { saving.current = false; setBusy(false); }
  };
  return <section><div className="flex flex-wrap gap-3 items-center justify-between mb-5"><div><h2 className="text-xl font-semibold">Suas preparações</h2><p className="text-sm text-slate-400 mt-1">Um espaço para cada prova, curso ou objetivo.</p></div><div className="flex gap-2"><Button variant="ghost" onClick={onImport}>Analisar edital</Button><Button onClick={() => setOpen(true)}>Nova preparação</Button></div></div>
    {error && <p role="alert" className="text-amber-300 my-3">{error}</p>}
    {!targets.length && <p className="text-slate-400 py-8">Crie sua primeira preparação ou importe um edital.</p>}
    <div className="grid md:grid-cols-2 gap-4">{targets.map(t => <div key={t.target_id} className="rounded-xl bg-slate-900/70 p-5 min-w-0"><button onClick={() => onOpen(t)} className="text-left w-full break-words hover:text-purple-200 transition-colors"><span className="text-xs text-purple-300">{types[t.kind]}{t.is_primary ? ' · Principal' : ''}</span><h3 className="text-lg font-medium mt-2">{t.name}</h3><p className="text-sm text-slate-400 mt-2">{[t.institution, t.board, t.position].filter(Boolean).join(' · ') || 'Abrir plano e materiais'}</p>{t.exam_date && <p className="text-xs mt-3">Data/meta: {t.exam_date.slice(0, 10)}</p>}<span className="block text-xs text-slate-500 mt-3">{t.provenance === 'extracted' ? 'Dados extraídos · confira o edital' : 'Informado pelo usuário'}</span></button>{!t.is_primary && <Button variant="ghost" className="mt-3 min-h-[44px] whitespace-normal" disabled={primaryBusy} onClick={() => makePrimary(t)}>Definir como principal</Button>}</div>)}</div>
    <Dialog open={open} onOpenChange={setOpen}><DialogContent><DialogTitle>Nova preparação</DialogTitle><DialogDescription>Você pode associar materiais e organizar o plano depois.</DialogDescription><form onSubmit={save} className="space-y-3"><label className="block text-sm">Nome<input required maxLength={180} className={input} value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} /></label><label className="block text-sm">Tipo<select aria-label="Tipo de preparação" className={input} value={form.kind} onChange={e => setForm({ ...form, kind: e.target.value })}>{Object.entries(types).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>{[['institution', 'Órgão / instituição'], ['board', 'Banca'], ['position', 'Cargo / objetivo'], ['edition', 'Edição']].map(([key, label]) => <label className="block text-sm" key={key}>{label}<input maxLength={key === 'edition' ? 80 : key === 'board' ? 100 : 180} className={input} value={form[key]} onChange={e => setForm({ ...form, [key]: e.target.value })} /></label>)}<label className="block text-sm">Data da prova ou meta<input type="date" className={input} value={form.exam_date} onChange={e => setForm({ ...form, exam_date: e.target.value })} /></label>{error && <p role="alert" className="text-amber-300">{error}</p>}<Button type="submit" disabled={busy}>{busy ? 'Criando…' : 'Criar preparação'}</Button></form></DialogContent></Dialog>
  </section>;
}
