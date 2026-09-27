import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Command } from 'cmdk';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from './ui/dialog';
import { openSirius } from '@/lib/sirius-context';

const API = `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000'}/api`;
const actions = [
  ['Nova tarefa', '/tasks?create=task'], ['Registrar gasto', '/finance?create=expense'],
  ['Registrar receita', '/finance?create=income'], ['Iniciar estudo', '/studies'],
  ['Registrar estudo', '/studies?create=session'], ['Novo compromisso', 'sirius:Crie um compromisso'],
  ['Nota ou arquivo de estudo', '/studies?view=library'], ['Perguntar ao Sirius', 'sirius:'],
];
export default function CommandPalette({ mode, onClose }) {
  const [query, setQuery] = useState(''), [results, setResults] = useState([]), [error, setError] = useState(''), [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  useEffect(() => { setQuery(''); setResults([]); setError(''); }, [mode]);
  useEffect(() => {
    setResults([]); setError(''); setLoading(false);
    if (!mode || query.trim().length < 2) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setLoading(true);
      axios.get(`${API}/search/global`, { params: { q: query.trim() }, signal: controller.signal })
        .then(r => { if (!controller.signal.aborted) setResults(r.data.results || []); })
        .catch(() => { if (!controller.signal.aborted) setError('Não foi possível buscar. Tente novamente.'); })
        .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [query, mode]);
  const select = link => { onClose(); if (link.startsWith('sirius:')) { setTimeout(() => openSirius({ draft: link.slice(7) }), 0); } else navigate(link); };
  const visible = actions.filter(([name]) => name.toLocaleLowerCase('pt-BR').includes(query.toLocaleLowerCase('pt-BR')));
  return <Dialog open={Boolean(mode)} onOpenChange={open => { if (!open) onClose(); }}><DialogContent className="sirius-command-dialog">
    <DialogTitle>{mode === 'add' ? 'O que deseja adicionar?' : 'Buscar e fazer'}</DialogTitle>
    <DialogDescription>Encontre seus registros ou escolha uma ação. Use as setas e Enter.</DialogDescription>
    <Command shouldFilter={false} label="Busca global">
      <Command.Input aria-label="Buscar registros e ações" placeholder="Tarefa, matéria, preparação…" value={query} onValueChange={setQuery} className="sirius-command-input" />
      <Command.List className="max-h-[55dvh] overflow-y-auto">
        {loading && <p role="status" className="p-3 text-sm">Buscando…</p>}{error && <p role="alert" className="p-3 text-sm">{error}</p>}
        <Command.Group heading="Ações">{visible.map(([label, link]) => <Command.Item key={label} value={label} onSelect={() => select(link)}>{label}</Command.Item>)}</Command.Group>
        {results.length > 0 && <Command.Group heading="Seus registros">{results.map((r, i) => <Command.Item key={`${r.link}-${i}`} value={`${r.title}-${i}`} onSelect={() => select(r.link)}><span>{r.title}</span><small>{r.subtitle}</small></Command.Item>)}</Command.Group>}
        {!loading && !error && query.length >= 2 && results.length === 0 && <p className="p-3 text-sm text-slate-400">Nenhum registro encontrado.</p>}
      </Command.List>
    </Command>
  </DialogContent></Dialog>;
}
