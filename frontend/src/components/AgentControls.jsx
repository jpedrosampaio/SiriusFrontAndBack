import { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { getApiErrorMessage } from '@/lib/api-errors';

const API = `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000'}/api/ai`;
const button = 'rounded-lg border border-slate-700 px-3 py-2 text-xs hover:bg-slate-800 disabled:opacity-40';

export function AgentAttachment({ assistant }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const operation = useRef(null);
  useEffect(() => {
    const cancel = () => { operation.current?.abort(); operation.current = null; setBusy(false); setError(''); };
    const storage = event => { if (!event.key || event.key === 'sirius_session_token') cancel(); };
    window.addEventListener('sirius-auth-changed', cancel);
    window.addEventListener('storage', storage);
    return () => { operation.current?.abort(); operation.current = null; window.removeEventListener('sirius-auth-changed', cancel); window.removeEventListener('storage', storage); };
  }, []);
  const upload = async event => {
    const file = event.target.files?.[0]; event.target.value = '';
    if (!file) return;
    if (file.size > 8 * 1024 * 1024) { setError('Limite de 8 MB.'); return; }
    const controller = new AbortController(); operation.current?.abort(); operation.current = controller;
    setBusy(true); setError('');
    try { const body = new FormData(); body.append('file', file); const { data } = await axios.post(`${API}/attachments`, body, { timeout: 120000, signal: controller.signal }); if (!controller.signal.aborted) assistant.setAttachment(data); }
    catch (e) { if (!controller.signal.aborted) setError(getApiErrorMessage(e, 'Não foi possível anexar.')); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  };
  const remove = async () => {
    const controller = new AbortController(); operation.current?.abort(); operation.current = controller;
    setBusy(true); setError('');
    try { await axios.delete(`${API}/attachments/${assistant.attachment.attachment_id}`, { signal: controller.signal }); if (!controller.signal.aborted) assistant.setAttachment(null); }
    catch { if (!controller.signal.aborted) setError('Não foi possível remover o arquivo.'); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  };
  return <div className="px-4 py-2 text-xs text-slate-400"><label className="inline-flex items-center gap-2 cursor-pointer">{busy ? 'Processando arquivo…' : 'Anexar PDF ou imagem'}<input aria-label="Anexar PDF ou imagem ao Sirius" type="file" accept="application/pdf,image/png,image/jpeg,image/webp" disabled={busy || assistant.sending} onChange={upload} className="max-w-[190px] text-xs" /></label>{assistant.attachment && <p className="mt-2 break-words">{assistant.attachment.filename} · {assistant.attachment.provenance === 'inferred' ? 'leitura por IA, confira o conteúdo' : 'texto extraído'} <button type="button" onClick={remove} disabled={busy} className="underline">Remover arquivo</button></p>}{error && <p role="alert" className="text-amber-300 mt-2">{error}</p>}</div>;
}

export function AgentToolbar({ assistant }) {
  return <div className="flex flex-wrap items-center gap-2 px-4 py-2 border-b border-slate-800 text-slate-300">
    <button className={button} disabled={assistant.sending} onClick={assistant.newConversation}>Nova conversa</button>
    <select aria-label="Conversas recentes" className="min-w-0 max-w-[180px] bg-slate-900 rounded-lg p-2 text-xs" disabled={assistant.sending} value={assistant.conversationId} onChange={e => assistant.selectConversation(e.target.value)}>
      <option value={assistant.conversationId}>Conversa atual</option>
      {assistant.conversations.filter(c => c.conversation_id && c.conversation_id !== assistant.conversationId).map(c => <option key={c.conversation_id} value={c.conversation_id}>{c.title || 'Conversa anterior'}</option>)}
    </select>
    <Link className={button} to="/assistant/settings">Configurações</Link>
    {assistant.sending && <button className={`${button} text-amber-300`} onClick={assistant.cancel}>Parar resposta</button>}
  </div>;
}

const labels = { amount: 'Valor (R$)', category: 'Categoria', description: 'Descrição', date: 'Data', title: 'Título', priority: 'Prioridade', recurrence: 'Recorrência', notebook_id: 'Caderno', duration_minutes: 'Minutos', notes: 'Observações', start_minute: 'Início (minutos do dia)', end_minute: 'Fim (minutos do dia)' };
const statusLabels = { pending: 'Aguardando confirmação', executed: 'Executada', cancelled: 'Cancelada', expired: 'Expirada', failed: 'Falhou' };
const factLabels = { get_today_tasks: 'Tarefas de hoje', get_tasks: 'Tarefas', get_study_progress: 'Estudos', get_finance_summary: 'Finanças', get_budget_status: 'Orçamentos', get_workout_progress: 'Treinos', get_active_workout: 'Planos de treino', get_nutrition_today: 'Nutrição de hoje', get_habits: 'Hábitos', get_goals: 'Metas', get_calendar: 'Agenda', get_daily_plan: 'Plano do dia', get_weekly_review: 'Revisão semanal', total: 'Total', completed: 'Concluídas', completed_today: 'Concluído hoje', income: 'Receitas', expense: 'Despesas', balance: 'Saldo', date: 'Data', start: 'Início', end: 'Fim', items: 'Itens', title: 'Título', name: 'Nome', priority: 'Prioridade', minutes: 'Minutos', sessions: 'Sessões', total_study_time_minutes: 'Tempo estudado (min)', blocks: 'Blocos', start_minute: 'Início (min)', end_minute: 'Fim (min)', duration_minutes: 'Duração (min)', unscheduled: 'Sem horário disponível', reason: 'Motivo', progress: 'Progresso', deadline: 'Prazo', total_calories: 'Calorias', total_protein: 'Proteínas', total_carbs: 'Carboidratos', total_fat: 'Gorduras', remaining_minutes: 'Minutos disponíveis' };

function FactValue({ value, depth = 0 }) {
  if (value === null || value === undefined) return <span>Não informado</span>;
  if (typeof value !== 'object') return <span>{typeof value === 'boolean' ? (value ? 'Sim' : 'Não') : String(value)}</span>;
  if (depth > 4) return <span>Detalhes disponíveis no módulo.</span>;
  if (Array.isArray(value)) return value.length ? <ul className="space-y-2 list-none">{value.slice(0, 15).map((v, i) => <li key={i} className="rounded bg-slate-900/70 p-2"><FactValue value={v} depth={depth + 1} /></li>)}</ul> : <span>Nenhum registro neste período.</span>;
  return <dl className="space-y-1">{Object.entries(value).filter(([k]) => !k.endsWith('_id') && !['preview', 'truncated', 'duration_estimated'].includes(k)).map(([k, v]) => <div key={k}><dt className="text-slate-400">{factLabels[k] || k.replaceAll('_', ' ')}</dt><dd className="break-words"><FactValue value={v} depth={depth + 1} /></dd></div>)}</dl>;
}

function ActionCard({ action }) {
  const [status, setStatus] = useState(action.status);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => setStatus(action.status), [action.status]);
  const expired = new Date(action.expires_at).getTime() <= Date.now();
  const apply = async operation => {
    setBusy(true); setError('');
    try {
      const { data } = await axios.post(`${API}/actions/${action.action_id}/${operation}`, {}, { withCredentials: true });
      setStatus(data.status);
      window.dispatchEvent(new Event('sirius-data-updated'));
    } catch (err) { setError(getApiErrorMessage(err, 'Não foi possível processar a proposta.')); }
    finally { setBusy(false); }
  };
  return <section className="my-3 rounded-xl border border-sky-700/50 bg-sky-950/20 p-3 text-sm break-words">
    <p className="font-semibold text-sky-200">{action.summary}</p>
    <p className="text-xs text-slate-400 my-1">{action.reason}</p>
    <dl className="my-3 space-y-1">{Object.entries(action.arguments || {}).map(([key, value]) => <div key={key}><dt className="inline text-slate-400">{labels[key] || key}: </dt><dd className="inline">{String(value)}</dd></div>)}</dl>
    <p className="text-xs text-slate-400">{statusLabels[expired && status === 'pending' ? 'expired' : status] || status}</p>
    {status === 'pending' && !expired && <div className="flex flex-wrap gap-2 mt-3"><button className={`${button} bg-sky-700 text-white`} disabled={busy} onClick={() => apply('confirm')}>Confirmar alteração</button><button className={button} disabled={busy} onClick={() => apply('cancel')}>Cancelar proposta</button></div>}
    {error && <p role="alert" className="text-amber-300 mt-2">{error}</p>}
  </section>;
}

export function AgentMessageDetails({ message }) {
  return <>
    {message.actions?.map(action => <ActionCard key={action.action_id} action={action} />)}
    {message.facts && Object.keys(message.facts).length > 0 && <details open={message.degraded} className="mt-3 text-xs"><summary className="cursor-pointer text-sky-300">Dados consultados nos módulos</summary><div className="mt-2 max-h-80 overflow-y-auto"><FactValue value={message.facts} /></div></details>}
    {message.citations?.length > 0 && <details className="mt-3 text-xs"><summary className="cursor-pointer text-sky-300">Fontes do documento</summary>{message.citations.map((source, i) => <blockquote key={i} className="my-2 border-l-2 border-sky-700 pl-2">Página {source.page}: {source.text}</blockquote>)}</details>}
    {message.role === 'assistant' && typeof window.speechSynthesis !== 'undefined' && <span className="flex gap-3 mt-2 text-xs text-slate-400"><button className="underline" onClick={() => { window.speechSynthesis.cancel(); const utterance = new SpeechSynthesisUtterance(message.content); utterance.lang = 'pt-BR'; window.speechSynthesis.speak(utterance); }}>Ouvir resposta</button><button className="underline" onClick={() => window.speechSynthesis.cancel()}>Parar áudio</button></span>}
  </>;
}

export function VoiceInput({ onText, disabled }) {
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const recorder = useRef(null), stream = useRef(null), timer = useRef(null), mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; clearTimeout(timer.current); if (recorder.current?.state === 'recording') recorder.current.stop(); stream.current?.getTracks().forEach(t => t.stop()); }; }, []);
  const record = async () => {
    if (recording) { recorder.current.stop(); return; }
    setError('');
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!mounted.current) { stream.current.getTracks().forEach(t => t.stop()); return; }
      recorder.current = new MediaRecorder(stream.current);
      const chunks = [];
      recorder.current.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
      recorder.current.onstop = async () => {
        clearTimeout(timer.current); stream.current.getTracks().forEach(t => t.stop());
        if (!mounted.current) return;
        setRecording(false); setBusy(true);
        try {
          const blob = new Blob(chunks, { type: recorder.current.mimeType });
          if (blob.size > 8 * 1024 * 1024) throw new Error('size');
          const form = new FormData(); form.append('file', blob, 'voice.webm');
          const { data } = await axios.post(`${API}/voice/transcribe`, form, { withCredentials: true, timeout: 100000 });
          if (mounted.current) onText(data.text);
        } catch (err) { if (mounted.current) setError(getApiErrorMessage(err, 'Transcrição indisponível. Continue digitando.')); }
        finally { if (mounted.current) setBusy(false); }
      };
      recorder.current.start(); setRecording(true);
      timer.current = setTimeout(() => { if (recorder.current?.state === 'recording') recorder.current.stop(); }, 60000);
    } catch { stream.current?.getTracks().forEach(t => t.stop()); setError('Não foi possível acessar o microfone.'); }
  };
  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') return null;
  return <div className="px-3 pb-2 text-xs"><button type="button" className={button} disabled={disabled || busy} onClick={record}>{recording ? 'Parar gravação' : busy ? 'Transcrevendo…' : 'Usar microfone'}</button><span className="ml-2 text-slate-500">Revise o texto antes de enviar.</span>{error && <p role="alert" className="text-amber-300 mt-1">{error}</p>}</div>;
}
