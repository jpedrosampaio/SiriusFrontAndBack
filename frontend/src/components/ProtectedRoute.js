import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getCurrentUser } from "@/lib/api";

export default function ProtectedRoute({ children }) {
  const [state, setState] = useState('loading');
  const [attempt, retry] = useState(0);
  const navigate = useNavigate();
  useEffect(() => {
    let active = true;
    getCurrentUser().then(() => { if (active) setState('ready'); }).catch(error => {
      if (!active) return;
      if (error.response?.status === 401) navigate('/login');
      else setState('error');
    });
    return () => { active = false; };
  }, [navigate, attempt]);
  if (state === 'ready') return children;
  return <div className="min-h-screen flex flex-col gap-4 items-center justify-center bg-background text-foreground" role="status">
    {state === 'error' ? <><p>Não foi possível conectar ao servidor.</p><button className="rounded-xl border px-5 py-3" onClick={() => { setState('loading'); retry(n => n + 1); }}>Tentar novamente</button></> : <><div className="animate-spin rounded-full h-10 w-10 border-2 border-blue-400 border-t-transparent" /><p>Conectando ao seu espaço…</p></>}
  </div>;
}
