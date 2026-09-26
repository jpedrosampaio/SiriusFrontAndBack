import { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { getApiErrorMessage } from '@/lib/api-errors';
import { displayStudyDate } from '@/lib/study-workspace';

const localDate = date => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
export default function DatedStudyPlan({ api, program, onStudy }) {
  const today = localDate(new Date());
  const end = new Date(); end.setDate(end.getDate() + 27);
  const [plan, setPlan] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [page, setPage] = useState(0);
  const [settings, setSettings] = useState({ start_date: today, end_date: program.target_date?.slice(0, 10) && program.target_date.slice(0, 10) < localDate(end) ? program.target_date.slice(0, 10) : localDate(end), availability: [60, 60, 60, 60, 60, 0, 0], block_minutes: 50 });
  const endpoint = `${api}/study/programs/${program.program_id}/dated-plan`;
  const load = () => axios.get(endpoint).then(r => { setPlan(r.data); if (r.data.settings) setSettings(r.data.settings); setError(''); }).catch(e => setError(getApiErrorMessage(e, 'Não foi possível carregar sua agenda.')));
  useEffect(() => { load(); }, [endpoint]); // eslint-disable-line react-hooks/exhaustive-deps
  const generate = async () => {
    setBusy(true);
    try { const { data } = await axios.post(endpoint, settings, { headers: { 'Idempotency-Key': crypto.randomUUID() } }); setPlan(data); setEditing(false); setPage(0); toast.success('Agenda organizada. Seu histórico concluído foi preservado.'); }
    catch (e) { toast.error(getApiErrorMessage(e, 'Não foi possível organizar a agenda.')); }
    finally { setBusy(false); }
  };
  const update = async (entry, body) => {
    if (busy) return;
    setBusy(true);
    try { const { data } = await axios.patch(`${endpoint}/${entry.entry_id}`, body); setPlan(old => ({ ...old, entries: old.entries.map(e => e.entry_id === entry.entry_id ? data : e) })); }
    catch (e) { toast.error(getApiErrorMessage(e, 'Não foi possível atualizar o bloco.')); }
    finally { setBusy(false); }
  };
  const entries = [...(plan?.entries || [])].sort((a, b) => a.date.localeCompare(b.date));
  const dates = [...new Set(entries.map(e => e.date))];
  const visible = dates.slice(page * 7, page * 7 + 7);
  return <section className="sirius-study-panel rounded-2xl border p-5 space-y-5">
    <div className="flex flex-wrap justify-between gap-3"><div><h2 className="text-xl font-semibold">Agenda com datas</h2><p className="text-sm text-slate-400 mt-2">Tempo por dia, distribuição por peso e revisões sugeridas após 7 e 21 dias, conforme a disponibilidade.</p></div><Button variant="outline" onClick={() => setEditing(!editing)}>{editing ? 'Fechar ajustes' : 'Organizar disponibilidade'}</Button></div>
    {error && <div role="alert"><p>{error}</p><Button onClick={load}>Tentar novamente</Button></div>}
    {(editing || plan && !plan.settings) && <div className="space-y-4">
      <div className="grid sm:grid-cols-3 gap-4"><label className="text-sm">Começar em<Input type="date" value={settings.start_date} onChange={e => setSettings(s => ({ ...s, start_date: e.target.value }))} /></label><label className="text-sm">Planejar até<Input type="date" max={program.target_date?.slice(0, 10)} value={settings.end_date} onChange={e => setSettings(s => ({ ...s, end_date: e.target.value }))} /></label><label className="text-sm">Minutos por bloco<Input type="number" min={15} max={120} value={settings.block_minutes} onChange={e => setSettings(s => ({ ...s, block_minutes: Number(e.target.value) }))} /></label></div>
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">{['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'].map((day, index) => <label className="text-sm" key={day}>{day} · minutos<Input type="number" min={0} max={720} step={15} value={settings.availability[index]} onChange={e => setSettings(s => ({ ...s, availability: s.availability.map((v, i) => i === index ? Number(e.target.value) : v) }))} /></label>)}</div>
      <p className="text-xs text-slate-400">Zero indica descanso. Reorganizar substitui apenas os blocos pendentes; blocos concluídos permanecem no histórico. Prioridades estimadas continuam sujeitas à conferência do edital.</p>
      <label className="flex items-start gap-3 text-sm"><input type="checkbox" checked={!!settings.adaptive} onChange={e => setSettings(s => ({ ...s, adaptive: e.target.checked }))} />Priorizar disciplinas com mais erros (mínimo de 5 questões) e pendências anteriores ao início do plano. Preservar blocos concluídos.</label><Button onClick={generate} disabled={busy}>{busy ? 'Organizando…' : 'Gerar / reorganizar pendências'}</Button>
    </div>}
    {!plan && !error && <p role="status">Carregando agenda…</p>}
    {visible.map(date => <div key={date} className="space-y-3"><h3 className="font-semibold">{displayStudyDate(date)} {date === today && <span className="text-blue-300">· Hoje</span>}</h3>{entries.filter(e => e.date === date).map(entry => <article key={entry.entry_id} className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-700 p-4"><label className="flex items-center gap-3 flex-1 min-w-[180px]"><input type="checkbox" checked={entry.completed} disabled={busy} onChange={e => update(entry, { completed: e.target.checked })} /><span className={entry.completed ? 'text-slate-400' : ''}><span className="block text-sm font-medium">{entry.name}</span><span className="text-xs text-slate-400">{entry.kind} · {entry.minutes} min{!entry.completed && date < today ? ' · Pendente de outro dia' : ''}</span>{entry.reason && <span className="block text-xs text-blue-300 mt-1">{entry.reason}</span>}</span></label>{!entry.completed && <><Input type="date" aria-label={`Remarcar ${entry.name}`} className="w-auto max-w-full" value={entry.date} disabled={busy} onChange={e => { if (e.target.value) update(entry, { date: e.target.value }); }} /><Button size="sm" onClick={() => onStudy(entry)}>Estudar</Button></>}</article>)}</div>)}
    {dates.length > 7 && <div className="flex items-center gap-3"><Button variant="outline" disabled={page === 0} onClick={() => setPage(p => p - 1)}>Anterior</Button><span className="text-sm">{page + 1} / {Math.ceil(dates.length / 7)}</span><Button variant="outline" disabled={(page + 1) * 7 >= dates.length} onClick={() => setPage(p => p + 1)}>Próximos dias</Button></div>}
  </section>;
}
