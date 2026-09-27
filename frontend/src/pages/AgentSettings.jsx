import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { getCurrentUser } from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api-errors';

const API = `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000'}/api/ai`;
const control = 'rounded-lg border border-slate-700 bg-slate-900 p-2 text-sm min-w-0';
const button = `${control} hover:border-sky-500 disabled:opacity-40`;
const panel = 'rounded-2xl border border-slate-800 bg-slate-950/60 p-4 md:p-6 space-y-3';

export default function AgentSettings() {
  const [, setUser] = useState(null), [status, setStatus] = useState(null), [prefs, setPrefs] = useState(null);
  const [memory, setMemory] = useState([]), [content, setContent] = useState(''), [category, setCategory] = useState('preference');
  const [keys, setKeys] = useState({ gemini: '', groq: '' }), [error, setError] = useState(''), [busy, setBusy] = useState(false), [notice, setNotice] = useState('');
  const [editing, setEditing] = useState(null);
  const [sources, setSources] = useState({ editais: [], notebooks: [] });
  const load = useCallback(async () => {
    const [s, p, m] = await Promise.all([axios.get(`${API}/status`), axios.get(`${API}/preferences`), axios.get(`${API}/memory`)]);
    setStatus(s.data); setPrefs(p.data); setMemory(m.data);
    const docs = await axios.get(`${API}/rag/sources`); setSources(docs.data);
  }, []);
  useEffect(() => { getCurrentUser().then(r => setUser(r.data)).catch(() => {}); load().catch(e => setError(getApiErrorMessage(e, 'Não foi possível carregar as configurações.'))); }, [load]);
  const run = async operation => {
    setBusy(true); setError(''); setNotice('');
    try { await operation(); await load(); setNotice('Atualizado.'); }
    catch (e) { setError(getApiErrorMessage(e, 'Não foi possível concluir a operação.')); }
    finally { setBusy(false); }
  };
  return <div className="min-h-screen bg-[#080b12] text-slate-100"><main className=" px-4 md:px-8 pt-6 md:pt-8 pb-28 max-w-7xl">
    <header className="mb-7"><Link to="/chat" className="text-sm text-sky-400">← Conversar com Sirius</Link><h1 className="text-2xl md:text-3xl font-semibold mt-3">Seu assistente, suas escolhas</h1><p className="text-slate-400 mt-2">Controle as informações lembradas, os provedores e as propostas do Sirius.</p></header>
    {error && <p role="alert" className="text-amber-300 mb-4">{error}</p>}{notice && <p role="status" className="text-emerald-300 mb-4">{notice}</p>}
    <div className="grid xl:grid-cols-2 gap-5">
      <section className={panel}><h2 className="text-lg font-medium">Conexões de IA</h2><p className="text-sm text-slate-400">As chaves salvas nunca são devolvidas ao navegador. O catálogo prioriza modelos com faixa gratuita; a cobrança depende da configuração da sua conta no provedor.</p>
        {['gemini', 'groq'].map(provider => <div key={provider} className="space-y-2 border-t border-slate-800 pt-3"><p className="capitalize font-medium">{provider} <span className="text-xs text-slate-400">{status?.providers[provider].has_key ? `Configurada · ••••${status.providers[provider].last4}` : 'Sem chave'}</span></p><label className="sr-only" htmlFor={`${provider}-key`}>Nova chave {provider}</label><input id={`${provider}-key`} type="password" autoComplete="off" className={`${control} w-full`} placeholder="Cole uma nova chave" value={keys[provider]} onChange={e => setKeys({ ...keys, [provider]: e.target.value })} /><div className="flex gap-2"><button className={button} disabled={busy || !keys[provider]} onClick={() => run(async () => { await axios.put(`${API}/providers/${provider}`, { key: keys[provider] }); setKeys(k => ({ ...k, [provider]: '' })); })}>Salvar chave</button><button className={button} disabled={busy || !status?.providers[provider].has_key} onClick={() => run(() => axios.put(`${API}/providers/${provider}`, { key: '' }))}>Remover</button></div></div>)}
        {status && <p className="text-xs text-slate-400">Requisições internas hoje: {status.internal_requests_today}/{status.internal_daily_limit}. Busca documental: {status.capabilities.rag === 'lexical' ? 'por palavras e referências de página' : 'desabilitada'}.</p>}
      </section>
      <section className={panel}><h2 className="text-lg font-medium">Autonomia e sugestões</h2>{prefs && <><label className="block text-sm">Perfil <select className={`${control} ml-2`} value={prefs.profile} onChange={e => setPrefs({ ...prefs, profile: e.target.value })}><option value="conservative">Conservador</option><option value="balanced">Equilibrado</option><option value="proactive">Proativo</option></select></label><p className="text-sm text-slate-400">Todos os perfis exigem sua confirmação para alterar dados. O perfil proativo pode oferecer sugestões, sem executar pagamentos ou exclusões.</p><label className="block text-sm"><input type="checkbox" checked={prefs.automations} onChange={e => setPrefs({ ...prefs, automations: e.target.checked })} /> Receber sugestões automáticas</label><div className="flex flex-wrap gap-3"><label className="text-sm">Silêncio das <input className={`${control} w-16`} type="number" min="0" max="23" value={prefs.quiet_start} onChange={e => setPrefs({ ...prefs, quiet_start: Number(e.target.value) })} /></label><label className="text-sm">até <input className={`${control} w-16`} type="number" min="0" max="23" value={prefs.quiet_end} onChange={e => setPrefs({ ...prefs, quiet_end: Number(e.target.value) })} /></label></div><p className="text-xs text-slate-500">{status?.flags.dry_run ? 'Automações em simulação: não enviam notificações nem executam ações.' : 'Sugestões ativadas; alterações continuam exigindo confirmação.'}</p><button className={button} disabled={busy} onClick={() => run(() => axios.put(`${API}/preferences`, prefs))}>Salvar preferências</button></>}</section>
      <section className={panel}><h2 className="text-lg font-medium">O que Sirius lembra</h2><p className="text-sm text-slate-400">Somente informações que você salvar aqui. Ao remover, o mesmo conteúdo fica bloqueado para não ser lembrado novamente.</p><label className="sr-only" htmlFor="memory-category">Tipo de memória</label><select id="memory-category" className={control} value={category} onChange={e => setCategory(e.target.value)}><option value="preference">Preferência</option><option value="rule">Regra pessoal</option><option value="goal">Objetivo</option><option value="context">Contexto</option></select><textarea aria-label="Informação para lembrar" className={`${control} w-full`} maxLength={1000} value={content} onChange={e => setContent(e.target.value)} placeholder="Ex.: prefiro estudar no início da manhã" /><button className={button} disabled={busy || !content.trim()} onClick={() => run(async () => { await axios[editing ? 'put' : 'post'](`${API}/memory${editing ? `/${editing}` : ''}`, { category, content }); setContent(''); setEditing(null); })}>{editing ? 'Salvar edição' : 'Adicionar memória'}</button>{memory.map(m => <div key={m.memory_id} className="border-t border-slate-800 pt-3"><p className="text-sm break-words">{m.content}</p><div className="flex gap-3 mt-2"><button className="text-xs text-sky-400" onClick={() => { setEditing(m.memory_id); setContent(m.content); setCategory(m.category); }}>Editar</button><button className="text-xs text-rose-300" disabled={busy} onClick={() => run(() => axios.delete(`${API}/memory/${m.memory_id}`))}>Remover e bloquear</button></div></div>)}</section>
      <section className={panel}><h2 className="text-lg font-medium">Fontes para consulta</h2><p className="text-sm text-slate-400">Inclua editais e anotações na busca do assistente. Reindexe as anotações após editá-las. Tarefas e finanças são consultadas diretamente nos módulos.</p>{[['editais', 'analysis_id', 'pdf_filename'], ['notebooks', 'notebook_id', 'name']].map(([kind, id, title]) => <div key={kind}>{(sources[kind] || []).map(source => <div key={source[id]} className="flex flex-wrap justify-between gap-2 items-center border-t border-slate-800 py-3"><span className="text-sm break-words">{source[title] || source.title || 'Documento'}</span><button className={button} disabled={busy} onClick={() => run(() => axios.post(`${API}/rag/${kind}/${source[id]}`))}>Atualizar busca</button></div>)}</div>)}</section>
    </div>
  </main></div>;
}
