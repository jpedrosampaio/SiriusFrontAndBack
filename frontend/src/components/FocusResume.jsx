import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { readSaved } from '@/lib/session-storage';
export default function FocusResume({ userId }) {
  const location = useLocation(), [resume, setResume] = useState(null);
  useEffect(() => {
    const load = () => {
      const active = readSaved(`sirius-active-focus:${userId}`);
      const state = active?.key && readSaved(active.key);
      setResume(state?.isRunning && !state?.isBreak && active?.path?.startsWith('/studies') ? active : null);
    };
    load(); window.addEventListener('sirius-focus-changed', load);
    return () => window.removeEventListener('sirius-focus-changed', load);
  }, [userId]);
  if (!resume || resume.path === location.pathname + location.search) return null;
  return <div className="px-4 py-3 bg-purple-950/40 border-b border-purple-400/20 flex flex-wrap justify-between gap-2 text-sm"><span>Você tem uma sessão de estudo em andamento.</span><Link to={resume.path} className="text-purple-200 underline">Continuar sessão</Link></div>;
}
