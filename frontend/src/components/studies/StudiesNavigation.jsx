const groups = [
  { key: 'dashboard', label: 'Hoje', tabs: [['dashboard', 'Próxima atividade'], ['tarefas', 'Pendências'], ['foco', 'Sessão livre']] },
  { key: 'preparacoes', label: 'Preparações', tabs: [['preparacoes', 'Minhas preparações'], ['editais', 'Editais analisados'], ['programas', 'Organizar programas']] },
  { key: 'library', label: 'Biblioteca', tabs: [['library', 'Todos os materiais'], ['materias', 'Matérias e materiais'], ['conteudo', 'Importar conteúdo'], ['redacao', 'Redação']] },
  { key: 'desempenho', label: 'Desempenho', tabs: [['desempenho', 'Domínio e erros'], ['simulados', 'Simulados']] },
];
export default function StudiesNavigation({ active, onChange }) {
  const current = groups.find(g => g.tabs.some(([key]) => key === active)) || groups[0];
  return <div className="space-y-4 mb-6">
    <nav aria-label="Áreas de estudos" className="grid grid-cols-4 border-b border-slate-700">{groups.map(group => <button key={group.key} aria-current={group.key === current.key ? 'page' : undefined} onClick={() => onChange(group.key)} className={`px-1 sm:px-4 py-3 text-[11px] sm:text-sm border-b-2 ${current.key === group.key ? 'border-purple-400 text-purple-200' : 'border-transparent text-slate-400'}`}>{group.label}</button>)}</nav>
    <div className="flex flex-wrap gap-2">{current.tabs.map(([key, label]) => <button key={key} aria-pressed={active === key} className={`px-3 py-2 rounded-lg text-xs ${active === key ? 'bg-slate-700 text-white' : 'text-slate-400 hover:bg-slate-800'}`} onClick={() => onChange(key)}>{label}</button>)}</div>
  </div>;
}
