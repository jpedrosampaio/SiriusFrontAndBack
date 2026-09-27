import { useRef, useState } from 'react';
import axios from 'axios';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { getApiErrorMessage } from '@/lib/api-errors';
const API = `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000'}/api`;
export default function QuickStudySession({ open, onClose, notebooks, onSaved }) {
  const [notebook, setNotebook] = useState(''), [minutes, setMinutes] = useState(30), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const pending = useRef(null);
  const save = async e => {
    e.preventDefault(); if (busy) return; setBusy(true); setError('');
    const now = new Date(), date = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;
    const body = { notebook_id: notebook, duration_minutes: minutes, date, notes: '' }, fingerprint = JSON.stringify(body);
    if (pending.current?.fingerprint !== fingerprint) pending.current = { fingerprint, id: crypto.randomUUID() };
    try { await axios.post(`${API}/study/sessions`, body, { headers: { 'Idempotency-Key': pending.current.id } }); pending.current = null; await onSaved(); onClose(); }
    catch (e) { setError(getApiErrorMessage(e, 'Não foi possível registrar.')); }
    finally { setBusy(false); }
  };
  return <Dialog open={open} onOpenChange={value => { if (!value && !busy) onClose(); }}><DialogContent><DialogTitle>Registrar estudo</DialogTitle><DialogDescription>Registre o tempo estudado hoje em uma matéria existente.</DialogDescription><form onSubmit={save} className="space-y-4"><label className="block text-sm">Matéria<select required className="block w-full p-2 mt-1 bg-slate-900 border border-slate-700 rounded-lg" value={notebook} onChange={e => setNotebook(e.target.value)}><option value="">Escolha a matéria</option>{notebooks.map(n => <option value={n.notebook_id} key={n.notebook_id}>{n.name}</option>)}</select></label><label className="block text-sm">Minutos estudados<input type="number" required min="1" max="720" className="block w-full p-2 mt-1 bg-slate-900 border border-slate-700 rounded-lg" value={minutes} onChange={e => setMinutes(Number(e.target.value))} /></label>{!notebooks.length && <p className="text-sm text-amber-300">Adicione uma matéria na Biblioteca antes de registrar estudo.</p>}{error && <p role="alert">{error}</p>}<Button type="submit" disabled={busy || !notebook}>{busy ? 'Registrando…' : 'Registrar sessão'}</Button></form></DialogContent></Dialog>;
}
