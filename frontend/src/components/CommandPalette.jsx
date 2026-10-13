import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Command } from 'cmdk';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from './ui/dialog';
import { openSirius } from '@/lib/sirius-context';

const API = `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000'}/api`;
const domains = { tasks:'Tarefas',finance:'Finanças',habits:'Hábitos',goals:'Metas',calendar:'Agenda',workouts:'Planos de treino',exercises:'Exercícios',training_history:'Histórico de treino',nutrition:'Nutrição',notes:'Notas',programs:'Programas',targets:'Preparações',notebooks:'Matérias',topics:'Tópicos',questions:'Questões',errors:'Erros',reviews:'Revisões',materials:'Materiais',editais:'Editais',conversations:'Conversas' };
const entity = {question:'question_id',question_error:'attempt_id',exercise:'exercise_id',transaction:'transaction_id',edital:'analysis_id',material:'attachment_id',notebooks:'notebook_id',study_programs:'program_id'};
const actions = [
  ['Nova tarefa', '/tasks?create=task'], ['Registrar gasto', '/finance?create=expense'],
  ['Registrar receita', '/finance?create=income'], ['Iniciar estudo', '/studies'],
  ['Registrar estudo', '/studies?create=session'], ['Novo compromisso', 'sirius:Crie um compromisso'],
  ['Nota ou arquivo de estudo', '/studies?view=library'], ['Perguntar ao Sirius', 'sirius:'],
];
export default function CommandPalette({ mode, onClose }) {
  const [query, setQuery] = useState(''), [results, setResults] = useState([]), [error, setError] = useState(''), [loading, setLoading] = useState(false);
  const [groups,setGroups]=useState([]),[domain,setDomain]=useState('');
  const paging=useRef(null),epoch=useRef(0);
  const navigate = useNavigate();
  useEffect(() => { setQuery(''); setResults([]); setGroups([]); setDomain(''); setError(''); }, [mode]);
  useEffect(() => {
    const version=++epoch.current;paging.current?.abort();setResults([]);setGroups([]); setError(''); setLoading(false);
    if (!mode || query.trim().length < 2) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setLoading(true);
      axios.get(`${API}/search/global`, { params: { q: query.trim(),...(domain?{domain}:{}) }, signal: controller.signal })
        .then(r => { if (!controller.signal.aborted&&version===epoch.current) {setResults(r.data.results || []);setGroups(r.data.groups||[]);} })
        .catch(() => { if (!controller.signal.aborted) setError('Não foi possível buscar. Tente novamente.'); })
        .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    }, 250);
    return () => { clearTimeout(timer); controller.abort();paging.current?.abort(); };
  }, [query, mode,domain]);
  const next=async group=>{
    paging.current?.abort();const controller=new AbortController();paging.current=controller;const version=epoch.current;
    setLoading(true);setError('');
    try{const {data}=await axios.get(`${API}/search/global`,{params:{q:query.trim(),domain:group.domain,cursor:group.next_cursor},signal:controller.signal});
      if(!controller.signal.aborted&&version===epoch.current){setGroups(previous=>previous.map(g=>g.domain===group.domain?data.groups[0]:g));setResults(previous=>[...previous.filter(r=>r.domain!==group.domain),...data.results]);}}
    catch{if(!controller.signal.aborted)setError('Não foi possível continuar a busca. Tente novamente.');}
    finally{if(!controller.signal.aborted&&version===epoch.current)setLoading(false);}
  };
  const ask=r=>{onClose();openSirius({intent:'explain',...(entity[r.type]?{[entity[r.type]]:r.id}:{}),draft:`Explique este registro: ${r.title}`});};
  const select = link => { onClose(); if (link.startsWith('sirius:')) { setTimeout(() => openSirius({ draft: link.slice(7) }), 0); } else navigate(link); };
  const visible = actions.filter(([name]) => name.toLocaleLowerCase('pt-BR').includes(query.toLocaleLowerCase('pt-BR')));
  return <Dialog open={Boolean(mode)} onOpenChange={open => { if (!open) onClose(); }}><DialogContent className="sirius-command-dialog">
    <DialogTitle>{mode === 'add' ? 'O que deseja adicionar?' : 'Buscar e fazer'}</DialogTitle>
    <DialogDescription>Encontre seus registros ou escolha uma ação. Use as setas e Enter.</DialogDescription>
    <Command shouldFilter={false} label="Buscar registros e ações">
      <Command.Input aria-label="Buscar registros e ações" placeholder="Tarefa, matéria, preparação…" value={query} onValueChange={setQuery} className="sirius-command-input" />
      <label className="block px-3 text-sm">Domínio<select aria-label="Domínio de busca" className="w-full min-h-11 rounded-lg bg-slate-950 border border-white/15 px-2" value={domain} onChange={e=>setDomain(e.target.value)}><option value="">Todas as áreas</option>{Object.entries(domains).map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label>
      <Command.List className="max-h-[55dvh] overflow-y-auto">
        {loading && <p role="status" className="p-3 text-sm">Buscando…</p>}{error && <p role="alert" className="p-3 text-sm">{error}</p>}
        <Command.Group heading="Ações">{visible.map(([label, link]) => <Command.Item key={label} value={label} onSelect={() => select(link)}>{label}</Command.Item>)}</Command.Group>
        {groups.length>0 ? groups.filter(g=>g.results.length||g.next_cursor).map(g=><Command.Group key={g.domain} heading={domains[g.domain]||g.domain}>{g.results.map(r=><div key={r.id}><Command.Item value={`${r.id}-open`} onSelect={()=>select(r.link)}><span className="break-words min-w-0">{r.title}</span><small>{r.subtitle}</small></Command.Item>{entity[r.type]&&<Command.Item value={`${r.id}-ask`} onSelect={()=>ask(r)}><small>Perguntar ao Sirius sobre {r.title}</small></Command.Item>}</div>)}{g.next_cursor&&<Command.Item disabled={loading} value={`${g.domain}-next`} onSelect={()=>next(g)}>Próxima página de {domains[g.domain]}</Command.Item>}</Command.Group>) : results.length > 0 && <Command.Group heading="Seus registros">{results.map((r, i) => <Command.Item key={`${r.link}-${i}`} value={`${r.title}-${i}`} onSelect={() => select(r.link)}><span>{r.title}</span><small>{r.subtitle}</small></Command.Item>)}</Command.Group>}
        {!loading && !error && query.length >= 2 && results.length === 0 && <p className="p-3 text-sm text-slate-400">Nenhum registro encontrado.</p>}
      </Command.List>
    </Command>
  </DialogContent></Dialog>;
}
