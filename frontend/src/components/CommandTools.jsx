import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { cacheKey } from '@/lib/query-cache';
import { getApiErrorMessage } from '@/lib/api-errors';
import WhyDetails from './WhyDetails';
import GlobalPlanner from './GlobalPlanner';
import { getCurrentUser } from '@/lib/api';
import { formatBRL } from '@/lib/finance-money';

const API = `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000'}/api/command`;
const button = 'min-h-11 rounded-lg border border-white/15 px-3 py-2 text-sm disabled:opacity-50';
const control = 'min-h-11 w-full rounded-lg border border-white/15 bg-slate-950 px-3 py-2 text-sm';
const scopes = { global:'Global', preparation:'Preparação', finance:'Finanças', training:'Treinos', nutrition:'Nutrição', tasks:'Tarefas', calendar:'Agenda', habits:'Hábitos', goals:'Metas' };
const kinds = { fact:'Fato declarado', preference:'Preferência', decision:'Decisão', rule:'Regra anterior', goal:'Meta anterior', context:'Contexto anterior' };
const eventLabels = { 'life.availability':'Disponibilidade atualizada', 'life.plan.accepted':'Planejamento confirmado', 'life.allocation.released':'Horário liberado', 'preparation.plan.updated':'Cronograma de estudos atualizado', 'preparation.entry.updated':'Bloco de estudo atualizado', 'memory.created':'Memória adicionada', 'memory.updated':'Memória corrigida', 'memory.removed':'Memória removida', 'command.undo':'Ação desfeita', record_expense:'Registro de despesa', record_income:'Registro de receita', create_task:'Criação de tarefa', record_study_session:'Registro de estudo', create_calendar_event:'Criação de compromisso' };
const changeLabels = {entry_count:'Blocos',recorded_minutes:'Minutos planejados',start_date:'Início',end_date:'Fim',date:'Data',completed:'Concluído',manual:'Ajuste manual',adaptive:'Estratégia adaptativa',block_minutes:'Minutos por bloco',protected_count:'Blocos preservados',allocated_count:'Horários alocados'};
function AuditChanges({ changes }) {
  if(!changes)return null;
  return <div className="grid sm:grid-cols-2 gap-3 my-3">{[['before','Antes'],['after','Depois']].map(([side,label])=>changes[side]&&<div key={side}><p className="text-sm font-medium">{label}</p><dl className="text-xs text-slate-400">{Object.entries(changes[side]).filter(([key])=>changeLabels[key]).map(([key,value])=><div key={key} className="flex flex-wrap gap-x-2"><dt>{changeLabels[key]}:</dt><dd>{value===null?'Não registrado':typeof value==='boolean'?(value?'Sim':'Não'):String(value)}</dd></div>)}</dl></div>)}</div>;
}
const datasets = { finance:'Finanças', tasks:'Tarefas', calendar:'Agenda', habits:'Hábitos', goals:'Metas', workouts:'Histórico de treinos', nutrition:'Refeições', study:'Sessões de estudo', topics:'Tópicos', attempts:'Respostas a questões', memory:'Memória', conversations:'Conversas', messages:'Mensagens', materials:'Materiais', editais:'Editais analisados' };
export default function CommandTools({ initialTab, onClose }) {
  const [error,setError]=useState(''),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false);
  const [content,setContent]=useState(''),[category,setCategory]=useState('fact'),[scope,setScope]=useState('global'),[editing,setEditing]=useState(null);
  const [cursor,setCursor]=useState(null),[source,setSource]=useState('command'),[undoId,setUndoId]=useState(null);
  const [capacity,setCapacity]=useState(''),[income,setIncome]=useState(''),[expense,setExpense]=useState(''),[scenario,setScenario]=useState(null);
  const [advanced,setAdvanced]=useState(false);
  const [dataset,setDataset]=useState('finance'),[format,setFormat]=useState('json'),[exportCursor,setExportCursor]=useState(''),[nextExport,setNextExport]=useState('');
  const intent=useRef(null),locked=useRef(false),abort=useRef(null);
  useEffect(()=>{ abort.current=new AbortController();return()=>abort.current.abort(); },[]);
  const memory=useQuery({queryKey:cacheKey('command-memory'),enabled:initialTab==='memory',queryFn:async({signal})=>(await axios.get(`${API}/memory`,{signal})).data});
  const audit=useQuery({queryKey:cacheKey('command-audit',source,cursor),enabled:initialTab==='audit',queryFn:async({signal})=>(await axios.get(`${API}/audit`,{signal,params:{source,cursor}})).data});
  const owner=useQuery({queryKey:cacheKey('command-owner'),enabled:initialTab==='scenarios',queryFn:async()=>(await getCurrentUser()).data});
  const run=async work=>{
    if(locked.current)return;locked.current=true;setBusy(true);setError('');setNotice('');
    try{await work();}catch(e){if(!abort.current.signal.aborted)setError(getApiErrorMessage(e,'A operação falhou. Confira os dados e tente novamente.'));}
    finally{locked.current=false;if(!abort.current.signal.aborted)setBusy(false);}
  };
  const mutate=async(method,url,data)=>{
    const fingerprint=JSON.stringify([method,url,data]);
    if(intent.current?.fingerprint!==fingerprint)intent.current={fingerprint,key:crypto.randomUUID()};
    const response=await axios({method,url,data,signal:abort.current.signal,headers:{'Idempotency-Key':intent.current.key}});
    if(abort.current.signal.aborted)return;
    intent.current=null;return response.data;
  };
  const saveMemory=()=>run(async()=>{
    const body={content,category,scope,...(editing?{expected_version:editing.version}:{})};
    await mutate(editing?'put':'post',`${API}/memory${editing?`/${editing.memory_id}`:''}`,body);
    if(abort.current.signal.aborted)return;setContent('');setEditing(null);setNotice('Memória salva como declaração explícita.');await memory.refetch();
  });
  const simulate=()=>run(async()=>{
    const body={routine:{...(capacity!==''?{capacity_minutes:Number(capacity)}:{})},
      ...(income!==''||expense!==''?{finance:{months:3,monthly_income:income||'0.00',monthly_expense:expense||'0.00'}}:{})};
    const {data}=await axios.post(`${API}/scenarios`,body,{signal:abort.current.signal});
    if(!abort.current.signal.aborted)setScenario(data);
  });
  const download=()=>run(async()=>{
    const {data,headers}=await axios.get(`${API}/export/${dataset}/${format}`,{responseType:'blob',signal:abort.current.signal,params:{limit:100,...(exportCursor?{cursor:exportCursor}:{})}});
    if(abort.current.signal.aborted)return;const url=URL.createObjectURL(data),anchor=document.createElement('a');anchor.href=url;anchor.download=`sirius_${dataset}.${format}`;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    setNextExport(headers['x-export-next-cursor']||'');setNotice('Página exportada. JSON e o cabeçalho da resposta identificam a continuação.');
  });
  const q=initialTab==='memory'?memory:initialTab==='audit'?audit:null;
  return <section aria-label="Controle integrado" className="rounded-xl border border-white/15 p-4 space-y-4">
    <header className="flex justify-between items-center gap-3"><h2 className="text-lg font-semibold">{{memory:'Memória explícita',audit:'Histórico de ações',scenarios:'Central de cenários',export:'Exportar dados'}[initialTab]}</h2><button className={button} onClick={onClose}>Fechar ferramenta</button></header>
    {error&&<p role="alert" className="text-amber-200 break-words">{error}</p>}{notice&&<p role="status" className="text-sky-200">{notice}</p>}
    {q?.isPending&&<p role="status">Carregando registros…</p>}{q?.isError&&<div role="alert"><p>Não foi possível consultar os registros.</p><button className={button} onClick={()=>q.refetch()}>Tentar novamente</button></div>}
    {initialTab==='memory'&&<>
      <p className="text-sm text-slate-400">Somente você confirma o que deve ser lembrado. Fatos declarados não são verificados; inferências da IA não são salvas automaticamente.</p>
      <button className={button} disabled={memory.isFetching} onClick={()=>memory.refetch()}>Atualizar memórias para comparar</button>
      <label className="block text-sm">Tipo<select className={control} value={category} onChange={e=>setCategory(e.target.value)}>{Object.entries(kinds).map(([id,label])=><option value={id} key={id}>{label}</option>)}</select></label>
      <label className="block text-sm">Escopo<select className={control} value={scope} onChange={e=>setScope(e.target.value)}>{Object.entries(scopes).map(([id,label])=><option value={id} key={id}>{label}</option>)}</select></label>
      <label className="block text-sm">Informação para lembrar<textarea aria-label="Informação para lembrar" className={`${control} min-h-24`} maxLength={1000} value={content} onChange={e=>setContent(e.target.value)}/></label>
      <div className="flex flex-wrap gap-2"><button className={button} disabled={busy||!content.trim()} onClick={saveMemory}>{editing?'Salvar correção':'Confirmar memória'}</button>{editing&&<button className={button} onClick={()=>{setEditing(null);setContent('');}}>Cancelar edição</button>}</div>
      {memory.data?.length===0&&<p className="text-sm text-slate-400">Nenhuma memória explícita cadastrada.</p>}
      <ul className="space-y-4">{memory.data?.map(m=><li key={m.memory_id} className="border-t border-white/10 pt-3 space-y-2"><p className="break-words">{m.content}</p><p className="text-xs text-slate-400">{kinds[m.category]||m.category} · {scopes[m.scope]||'Global'} · {m.provenance?.origin==='user_declared'?'Declarado por você':m.provenance?.origin==='verified'?'Fonte verificada':'Origem anterior não documentada'}</p><div className="flex flex-wrap gap-2"><button className={button} onClick={()=>{setEditing(m);setContent(m.content);setCategory(m.category);setScope(m.scope||'global');}}>Corrigir memória</button><button className={button} disabled={busy} onClick={()=>run(async()=>{await mutate('delete',`${API}/memory/${m.memory_id}?version=${m.version}`);if(!abort.current.signal.aborted){setNotice('Memória removida e bloqueada.');await memory.refetch();}})}>Remover e bloquear</button></div></li>)}</ul>
    </>}
    {initialTab==='audit'&&<>
      <label className="block text-sm">Origem dos registros<select className={control} value={source} onChange={e=>{setSource(e.target.value);setCursor(null);setUndoId(null);}}><option value="command">Planejamento e memória</option><option value="agent">Ações existentes do Agent</option></select></label>
      <p className="text-sm text-slate-400">Registros anteriores permanecem nas fontes originais. Desfazer é oferecido somente para disponibilidade ou alocações flexíveis futuras e intactas.</p>
      {audit.data?.items?.length===0&&<p>Nenhum registro nesta página.</p>}
      <ol className="space-y-4">{audit.data?.items?.map(row=><li key={row.id} className="border-t border-white/10 pt-3"><p className="break-words font-medium">{eventLabels[row.event]||'Ação do Sirius'}</p><p className="text-xs text-slate-400">{new Date(row.created_at).toLocaleString('pt-BR',{timeZone:audit.data?.timezone||'America/Sao_Paulo'})} · {row.actor}</p><p className="text-xs break-all text-slate-400">{row.entity_type}{row.entity_id?` · ${row.entity_id}`:''}</p><AuditChanges changes={row.changes}/><WhyDetails why={row.why}/>{row.undone_at&&<p className="text-sm">Desfeito em {new Date(row.undone_at).toLocaleString('pt-BR',{timeZone:audit.data?.timezone||'America/Sao_Paulo'})}</p>}{row.undo_available&&<button className={button} disabled={busy} onClick={()=>setUndoId(row.id)}>Desfazer ação</button>}{undoId===row.id&&<div className="space-y-2 mt-2"><p>Confirmar reversão? O servidor conferirá o estado atual. Mudanças concorrentes impedem desfazer.</p><button className={button} disabled={busy} onClick={()=>run(async()=>{await mutate('post',`${API}/audit/${row.id}/undo`,{confirmed:true});if(!abort.current.signal.aborted){setUndoId(null);setNotice('Reversão confirmada.');await audit.refetch();}})}>Confirmar desfazer</button><button className={button} onClick={()=>setUndoId(null)}>Cancelar</button></div>}</li>)}</ol>
      <div className="flex flex-wrap gap-2">{cursor&&<button className={button} onClick={()=>setCursor(null)}>Registros recentes</button>}{audit.data?.next_cursor&&<button className={button} onClick={()=>{setCursor(audit.data.next_cursor);setUndoId(null);}}>Próxima página</button>}</div>
    </>}
    {initialTab==='scenarios'&&<>
      <p className="text-sm text-slate-400">Hipóteses não alteram histórico, saldo, XP ou agenda. Estudos, treino e tarefas usam o mesmo Global Planner.</p>
      <label className="block text-sm">Limite de minutos flexíveis (opcional)<input className={control} type="number" min="0" max="1440" value={capacity} onChange={e=>{setCapacity(e.target.value);setScenario(null);}}/></label>
      <div className="grid sm:grid-cols-2 gap-3"><label className="block text-sm">Receita mensal hipotética (R$)<input className={control} inputMode="decimal" value={income} onChange={e=>{setIncome(e.target.value);setScenario(null);}} placeholder="0.00"/></label><label className="block text-sm">Despesa mensal hipotética (R$)<input className={control} inputMode="decimal" value={expense} onChange={e=>{setExpense(e.target.value);setScenario(null);}} placeholder="0.00"/></label></div>
      <button className={button} disabled={busy} onClick={simulate}>{busy?'Simulando…':'Simular sem alterar registros'}</button>
      {scenario&&<div className="space-y-3" aria-label="Resultado hipotético"><h3 className="font-medium">Prévia, sem aplicação</h3><p>{scenario.routine?.plan?.blocks?.length||0} atividade(s) sugerida(s); {scenario.routine?.plan?.unscheduled?.length||0} sem horário.</p>{scenario.routine?.plan?.blocks?.map(b=><div key={b.candidate_id}><p className="break-words">{b.title} · {b.duration_minutes} min</p><WhyDetails why={{source:'global-planner/1',evidence:b.reasons,constraints:['Compromissos fixos preservados.'],limitations:scenario.routine.state.warnings}}/></div>)}
        {scenario.finance&&<><h3>Previsão de fluxos financeiros (não é saldo bancário)</h3><ul className="space-y-2">{scenario.finance.scenario?.months?.map(month=><li key={month.month} className="rounded-lg border border-white/10 p-3"><p>{month.month}</p><p className="text-sm">Variação estimada de fluxo: {formatBRL(month.net_change)}</p><p className="text-xs text-slate-400">Receita hipotética: {formatBRL(month.scenario_income)} · Despesa hipotética: {formatBRL(month.scenario_expense)}</p></li>)}</ul>{scenario.finance.scenario?.assumptions?.map(v=><p key={v} className="text-xs text-slate-400">{v}</p>)}</>}
        {scenario.limitations?.map(v=><p key={v} className="text-xs text-slate-400">{v}</p>)}<Link className={`${button} inline-flex items-center`} to="/calendar">Revisar e confirmar apenas o planejamento</Link>
      </div>}
      {owner.data&&<details onToggle={e=>setAdvanced(e.currentTarget.open)}><summary className="min-h-11 cursor-pointer text-sky-300">Configurar disponibilidade e simular atividades específicas</summary>{advanced&&<GlobalPlanner userId={owner.data.user_id}/>}</details>}
    </>}
    {initialTab==='export'&&<>
      <p className="text-sm text-slate-400">Exportação por conjunto, em páginas de até 100 registros. Valores desconhecidos permanecem null. Credenciais, chaves de armazenamento e contexto interno ficam excluídos.</p>
      <label className="block text-sm">Dados<select className={control} value={dataset} onChange={e=>{setDataset(e.target.value);setExportCursor('');setNextExport('');}}>{Object.entries(datasets).map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label>
      <label className="block text-sm">Formato<select className={control} value={format} onChange={e=>setFormat(e.target.value)}><option value="json">JSON estruturado</option><option value="csv">CSV</option></select></label>
      <button className={button} disabled={busy} onClick={download}>Baixar página de dados</button>
      {nextExport&&<button className={button} disabled={busy} onClick={()=>{setExportCursor(nextExport);setNextExport('');}}>Selecionar próxima página</button>}
      {exportCursor&&<p className="text-xs text-slate-400 break-all">Página após {exportCursor}. <button className="underline min-h-11" onClick={()=>{setExportCursor('');setNextExport('');}}>Voltar à primeira página</button></p>}
      <button className={button} disabled={busy} onClick={()=>run(async()=>{const {data}=await axios.get(`${API}/export/daily-report.pdf`,{responseType:'blob',signal:abort.current.signal});if(abort.current.signal.aborted)return;const url=URL.createObjectURL(data),a=document.createElement('a');a.href=url;a.download='sirius_dia.pdf';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);})}>Baixar relatório diário PDF</button>
    </>}
  </section>;
}
