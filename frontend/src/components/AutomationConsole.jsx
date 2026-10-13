import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { createActivityRequests } from '@/lib/activity-requests';
import { getApiErrorMessage } from '@/lib/api-errors';
import { deliveryLabels, eventLabels, outcomeLabels, deliveryError, transitionTypes, receiptIntent } from '@/lib/automation-state';
import { formatBRL } from '@/lib/finance-money';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const field = 'w-full min-w-0 rounded-lg border border-slate-700 bg-slate-950 p-2 text-sm';
const panel = 'min-w-0 rounded-xl border border-slate-800 bg-slate-950/70 p-4 space-y-3';

function Report({ report }) {
  if (!report) return null;
  const f = report.facts;
  return <article className={panel} aria-label="Resumo integrado">
    <p className="text-xs text-slate-400">{report.date} · {report.timezone} · Registros próprios</p>
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <p><strong>Tarefas</strong><br />{f.tasks.recorded_completed} conclusões registradas · {f.tasks.pending_count ?? 'Desconhecido'} pendências atuais</p>
      <p><strong>Preparação</strong><br />{f.preparation.recorded_minutes} min registrados · {f.preparation.planned_minutes} min planejados</p>
      <p><strong>Treinos</strong><br />{f.training.recorded_completed} concluídos · {f.training.recorded_minutes} min registrados</p>
      <p><strong>Despesas no período</strong><br />{formatBRL(f.finance.recorded_expense)}<br /><span className="text-xs text-slate-400">Não é saldo bancário.</span></p>
    </div>
    {f.tasks.pending.length > 0 && <div><h4 className="font-medium">Pendências para revisar</h4><ul className="text-sm text-slate-300 space-y-1">{f.tasks.pending.map(p => <li key={`${p.id}:${p.date}`} className="break-words">{p.title} · {p.date}</li>)}</ul></div>}
    <div><h4 className="font-medium">Agenda de amanhã</h4>{f.tomorrow.commitments.length === 0 ? <p className="text-sm text-slate-400">Nenhum compromisso registrado.</p> : <ul className="text-sm space-y-1">{f.tomorrow.commitments.map(c => <li key={c.id} className="break-words">{c.title} · {c.start}</li>)}</ul>}</div>
    {report.proposals.map((p, i) => <Link key={i} to={p.link} className="block text-sky-300 underline break-words">{p.title} · revisar e confirmar</Link>)}
    <details><summary className="cursor-pointer text-sm text-slate-400">Fontes e limites do resumo</summary><ul className="mt-2 text-xs text-slate-400 space-y-2">{report.limitations.map((l,i) => <li key={i}>{l}</li>)}</ul></details>
    <p className="text-xs text-slate-400">Somente leitura. O Global Planner continua responsável pelo planejamento; nenhuma proposta foi aplicada.</p>
  </article>;
}

function Evidence({ facts = {} }) {
  if (facts.version === 'event-briefing/2') return <Report report={facts}/>;
  const labels = { date:'Data registrada', due_date:'Vencimento registrado', exam_date:'Data da prova',
    days_remaining:'Dias até a prova', recorded_minutes:'Minutos registrados', category:'Categoria',
    question_count:'Questões distintas no grupo', origin:'Origem registrada', target_date:'Prazo da meta', progress:'Progresso registrado (%)' };
  return <dl className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-slate-300">
    {Object.entries(labels).filter(([key])=>facts[key]!==null&&facts[key]!==undefined).map(([key,label])=><div key={key}><dt className="text-slate-400">{label}</dt><dd>{String(facts[key])}</dd></div>)}
    {[['spent','Despesa registrada'],['limit','Limite efetivo registrado'],['amount','Valor registrado']].filter(([key])=>facts[key]!==null&&facts[key]!==undefined).map(([key,label])=><div key={key}><dt className="text-slate-400">{label}</dt><dd>{formatBRL(facts[key])}</dd></div>)}
    {facts.remaining&&<div className="sm:col-span-2"><dt className="text-slate-400">Diferença entre metas confirmadas e consumo registrado</dt><dd>{Object.entries(facts.remaining).map(([key,value])=>`${({calories:'Calorias',protein:'Proteína',carbs:'Carboidratos',fat:'Gordura'})[key]||key}: ${value} ${key==='calories'?'kcal':'g'}`).join(' · ')}</dd></div>}
  </dl>;
}

export default function AutomationConsole() {
  const [state,setState] = useState(null), [policy,setPolicy] = useState(null), [enabled,setEnabled] = useState(false), [cap,setCap] = useState(3);
  const [events,setEvents] = useState([]), [cursor,setCursor] = useState(null), [report,setReport] = useState(null), [mode,setMode] = useState('morning');
  const [loading,setLoading] = useState(true), [busy,setBusy] = useState(false), [error,setError] = useState(''), [saved,setSaved] = useState(false);
  const requests = useRef(createActivityRequests()), sequence = useRef(0);
  const load = useCallback(async () => {
    const seq = ++sequence.current; setLoading(true); setError('');
    try {
      const [s,e] = await Promise.all([axios.get(`${API}/automations/state`,{withCredentials:true}),axios.get(`${API}/automations/events`,{withCredentials:true})]);
      if (sequence.current !== seq) return;
      setState(s.data);setPolicy(s.data.policy);setEnabled(s.data.enabled);setCap(s.data.daily_cap);setEvents(e.data.items);setCursor(e.data.next_cursor);
    } catch(e) { if(sequence.current===seq)setError(getApiErrorMessage(e,'Não foi possível carregar as automações.')); }
    finally { if(sequence.current===seq)setLoading(false); }
  },[]);
  useEffect(() => { load(); return () => { sequence.current += 1; }; },[load]);
  useEffect(() => {
    if (!state) return;
    let active = true; setReport(null);
    axios.get(`${API}/dashboard/daily-briefing`,{params:{mode},withCredentials:true}).then(r=>{if(active)setReport(r.data);}).catch(e=>{if(active)setError(getApiErrorMessage(e,'Resumo indisponível.'));});
    return () => {active=false;};
  },[mode,state]);
  const save = async () => {
    const body={enabled,daily_cap:Number(cap),policy};const key=requests.current.begin('policy',JSON.stringify(body));if(!key)return;
    setBusy(true);setError('');setSaved(false);let succeeded=false;
    try {await axios.put(`${API}/automations/policy`,body,{withCredentials:true,headers:{'Idempotency-Key':key}});succeeded=true;setSaved(true);window.dispatchEvent(new Event('sirius-automations-changed'));await load();}
    catch(e){setError(getApiErrorMessage(e,'Não foi possível salvar. Tente novamente para retomar com segurança.'));}
    finally {requests.current.finish('policy',succeeded);setBusy(false);}
  };
  const receipt = async (d,action) => {
    const accept=action==='retry';
    if(accept&&!window.confirm('A entrega anterior pode ter chegado. Reenviar pode duplicar a mensagem. Deseja confirmar?'))return;
    const key=requests.current.begin(d.delivery_id,receiptIntent(action,d.delivery_id,accept));if(!key)return;
    setBusy(true);setError('');let succeeded=false;
    try {await axios.post(`${API}/automations/deliveries/${d.delivery_id}`,{action,accept_duplicate_risk:accept},{withCredentials:true,headers:{'Idempotency-Key':key}});succeeded=true;
      const e=await axios.get(`${API}/automations/events`,{withCredentials:true});setEvents(e.data.items);setCursor(e.data.next_cursor);}
    catch(e){setError(getApiErrorMessage(e,'Ação indisponível; tente novamente.'));}
    finally {requests.current.finish(d.delivery_id,succeeded);setBusy(false);}
  };
  const more = async () => {
    setBusy(true);setError('');
    try {const e=await axios.get(`${API}/automations/events`,{params:{before:cursor},withCredentials:true});setEvents(v=>[...v,...e.data.items.filter(x=>!v.some(old=>old.event_id===x.event_id))]);setCursor(e.data.next_cursor);}
    catch(e){setError(getApiErrorMessage(e,'Histórico indisponível.'));}finally{setBusy(false);}
  };
  const updateRule = (kind,changes) => setPolicy(p=>({...p,rules:{...p.rules,[kind]:{...state.catalog.find(c=>c.event_type===kind).rule,...p.rules[kind],...changes}}}));
  return <section aria-label="Automações inteligentes" className="space-y-5 min-w-0">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-semibold">Sua rotina, conectada</h2><p className="text-sm text-slate-400">Alertas explicáveis, resumos integrados e histórico de entrega.</p></div><Button variant="outline" onClick={load} disabled={busy||loading}>Atualizar automações</Button></div>
    {error&&<div role="alert" className="rounded-lg border border-red-800 bg-red-950/30 p-3 text-sm break-words">{error}</div>}
    {loading&&<p role="status">Carregando automações…</p>}
    {!loading&&!state&&<Button onClick={load}>Tentar novamente</Button>}
    {state&&policy&&<>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <div className={panel}><h3 className="font-medium">Resumo da sua rotina</h3><label className="block text-sm">Período do resumo<select aria-label="Período do resumo" value={mode} onChange={e=>setMode(e.target.value)} className={field}><option value="morning">Daily Briefing · Hoje</option><option value="night">Night Review · Hoje</option><option value="weekly">Weekly Coach · Últimos 7 dias</option></select></label><Report report={report}/></div>
        <div className={panel}><h3 className="font-medium">Preferências de automação</h3>
          <label className="flex gap-3 items-center text-sm"><input type="checkbox" checked={enabled} onChange={e=>setEnabled(e.target.checked)}/>Ativar automações</label>
          <p className="text-xs text-slate-400">Fuso da conta: {state.timezone}. Nenhuma regra ignora o horário silencioso, inclusive as de prioridade alta.</p>
          {!state.runtime_enabled&&<p className="text-amber-300 text-sm">Worker desativado no servidor. Próximas execuções dependem da sua reativação.</p>}
          {state.simulation_only&&<p className="text-amber-300 text-sm">Modo de simulação do servidor: alertas disponíveis no Sirius; Telegram não será enviado automaticamente.</p>}
          <p className="text-xs text-slate-400">Telegram: {state.channels.telegram?'disponível':state.telegram_paired?'vinculado, envio automático indisponível':'vincule a conta em Configurações'}. Disponível no Sirius significa aguardando sua leitura, não entrega confirmada.</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <label className="text-sm">Silêncio a partir de<input aria-label="Silêncio a partir de" className={field} type="time" value={policy.quiet_start??state.inherited_quiet_start} onChange={e=>setPolicy(p=>({...p,quiet_start:e.target.value}))}/></label>
            <label className="text-sm">Fim do silêncio<input aria-label="Fim do silêncio" className={field} type="time" value={policy.quiet_end??state.inherited_quiet_end} onChange={e=>setPolicy(p=>({...p,quiet_end:e.target.value}))}/></label>
            <label className="text-sm">Limite diário de alertas<input aria-label="Limite diário de alertas" type="number" min="0" max="10" className={field} value={cap} onChange={e=>setCap(e.target.value)}/></label>
            {[['morning_time','Resumo da manhã'],['night_time','Revisão da noite'],['weekly_time','Revisão semanal']].map(([key,label])=><label key={key} className="text-sm">{label}<input aria-label={label} className={field} type="time" value={policy[key]} onChange={e=>setPolicy(p=>({...p,[key]:e.target.value}))}/></label>)}
            <label className="text-sm">Dia da revisão semanal<select aria-label="Dia da revisão semanal" className={field} value={policy.weekly_weekday} onChange={e=>setPolicy(p=>({...p,weekly_weekday:Number(e.target.value)}))}>{['Segunda','Terça','Quarta','Quinta','Sexta','Sábado','Domingo'].map((v,i)=><option key={i} value={i}>{v}</option>)}</select></label>
          </div>
          <p className="text-xs text-slate-400">Horários iguais desativam o silêncio. Limite zero suspende a publicação de alertas.</p>
          <Button disabled={busy} onClick={save}>Salvar automações</Button>{saved&&<p role="status" className="text-emerald-300 text-sm">Preferências salvas.</p>}
          {state.scan&&<p className="text-xs text-slate-400 break-words">Última varredura: {state.scan.last_scan||'aguardando execução'} · Status: {eventLabels[state.scan.status]||state.scan.status}{state.scan.last_error&&` · ${deliveryError(state.scan.last_error)}`}</p>}
          {state.scan?.limitations?.length>0&&<details><summary className="text-xs text-slate-400">Limites da varredura</summary>{state.scan.limitations.map((l,i)=><p key={i} className="text-xs text-slate-400">{l}</p>)}</details>}
        </div>
      </div>
      <details className={panel}><summary className="cursor-pointer font-medium">Tipos de eventos e canais</summary><p className="text-xs text-slate-400">Frequência controla a repetição das condições persistentes. Conclusões, despesas e atualizações avisam uma vez por registro. Prioridade é sua preferência explícita.</p>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">{state.catalog.map(c=>{const rule={...c.rule,...policy.rules[c.event_type]};return <fieldset key={c.event_type} className="min-w-0 rounded-lg border border-slate-800 p-3 space-y-3"><legend className="px-1 text-sm font-medium">{c.title}</legend>
          <label className="text-sm flex gap-2 items-center"><input aria-label={`Ativar ${c.title}`} type="checkbox" checked={rule.enabled} onChange={e=>updateRule(c.event_type,{enabled:e.target.checked})}/>Ativa</label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">{transitionTypes.includes(c.event_type)?<p className="text-xs text-slate-400">Uma vez por registro.</p>:<label className="text-xs">Frequência<select aria-label={`Frequência ${c.title}`} className={field} value={rule.frequency} onChange={e=>updateRule(c.event_type,{frequency:e.target.value})}><option value="daily">Diária</option><option value="weekly">Semanal</option></select></label>}<label className="text-xs">Prioridade<select aria-label={`Prioridade ${c.title}`} className={field} value={rule.priority} onChange={e=>updateRule(c.event_type,{priority:e.target.value})}><option value="low">Baixa</option><option value="medium">Normal</option><option value="high">Alta</option></select></label></div>
          <div className="flex flex-wrap gap-3">{[['in_app','No Sirius'],['telegram','Telegram']].map(([channel,label])=><label key={channel} className="text-xs flex gap-2"><input aria-label={`${label} ${c.title}`} type="checkbox" checked={rule.channels.includes(channel)} onChange={e=>{const channels=e.target.checked?[...rule.channels,channel]:rule.channels.filter(v=>v!==channel);if(channels.length)updateRule(c.event_type,{channels});}}/>{label}</label>)}</div>
        </fieldset>;})}</div>
      </details>
      <div className={panel}><h3 className="font-medium">Eventos e entregas</h3>{events.length===0&&<p className="text-sm text-slate-400">Nenhum evento registrado nesta conta. Ative as automações para iniciar a varredura.</p>}
        {events.map(e=><article key={e.event_id} className="border-t border-slate-800 pt-3 space-y-2 break-words"><div className="flex flex-wrap justify-between gap-2"><h4 className="font-medium">{e.title}</h4><span className="text-xs text-slate-400">{eventLabels[e.status]||e.status} · {e.attempts} tentativa(s)</span></div>
          <p className="text-xs text-slate-400">Observado em {e.created_at}</p>{e.last_error&&<p className="text-sm text-amber-300">{deliveryError(e.last_error)}</p>}{e.outcome&&<p className="text-xs text-slate-400">{outcomeLabels[e.outcome]||e.outcome}</p>}
          {e.candidate?.reasons?.map((reason,i)=><p key={i} className="text-sm text-slate-300">{reason}</p>)}
          {e.candidate?.facts?.title&&<p className="text-sm">{e.candidate.facts.title}</p>}
          {e.candidate&&<Evidence facts={e.candidate.facts}/>}
          {state.catalog.find(c=>c.event_type===e.event_type)?.link&&<Link className="text-xs text-sky-300 underline" to={state.catalog.find(c=>c.event_type===e.event_type).link}>Abrir módulo e revisar dados</Link>}
          {e.deliveries.map(d=><div key={d.delivery_id} className="rounded-lg bg-slate-900 p-3 space-y-2"><p className="text-sm">{d.channel==='telegram'?'Telegram':'Sirius'} · {deliveryLabels[d.status]||d.status} · {d.attempts} tentativa(s)</p>{d.last_error&&<p className="text-xs text-amber-300">{deliveryError(d.last_error)}</p>}
            {d.status==='available'&&<Button variant="outline" disabled={busy} onClick={()=>receipt(d,'read')}>Marcar como lido</Button>}
            {d.retry_allowed&&<Button variant="outline" disabled={busy} onClick={()=>receipt(d,'retry')}>Reenviar com confirmação</Button>}
            {d.history?.length>0&&<details><summary className="text-xs cursor-pointer text-slate-400">Histórico de tentativas</summary>{d.history.map((h,i)=><p key={i} className="text-xs text-slate-400">{h.at} · {deliveryLabels[h.outcome]||h.outcome}{h.receipt&&` · recibo ${h.receipt}`}</p>)}</details>}
          </div>)}
        </article>)}
        {cursor&&<Button variant="outline" disabled={busy} onClick={more}>Carregar eventos anteriores</Button>}
      </div>
    </>}
  </section>;
}
