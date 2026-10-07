import { useEffect, useState } from 'react';
import { Outlet, Link } from 'react-router-dom';
import { Search, Plus, Bell, User } from 'lucide-react';
import Sidebar from './Sidebar';
import MobileNav from './MobileNav';
import FloatingAssistant from './FloatingAssistant';
import CommandPalette from './CommandPalette';
import FocusResume from './FocusResume';
import { getCurrentUser } from '@/lib/api';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient, cachedGet } from '@/lib/query-cache';

export default function AppShell() {
  const [user, setUser] = useState(null);
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('sidebar_collapsed') === 'true');
  const [palette, setPalette] = useState(null);
  const [sessionEpoch, setSessionEpoch] = useState(0);
  useEffect(() => {
    let active = true;
    let version = 0;
    const load = () => { const current = ++version; return getCurrentUser().then(r => { if (active && current === version) setUser(r.data); }).catch(() => {}); };
    const resize = () => setCollapsed(localStorage.getItem('sidebar_collapsed') === 'true');
    const resetSession = () => { version += 1; setUser(null); setPalette(null); setSessionEpoch(n => n + 1); queueMicrotask(load); };
    const storageSession = e => { if (!e.key || e.key === 'sirius_session_token') resetSession(); };
    const keyboard = e => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setPalette('search'); } };
    load();
    window.addEventListener('sidebar-toggle', resize);
    window.addEventListener('storage', resize);
    window.addEventListener('sirius-data-changed', load);
    window.addEventListener('keydown', keyboard);
    window.addEventListener('sirius-auth-changed', resetSession);
    window.addEventListener('storage', storageSession);
    return () => { active = false; window.removeEventListener('sirius-auth-changed', resetSession); window.removeEventListener('storage', storageSession); window.removeEventListener('sidebar-toggle', resize); window.removeEventListener('storage', resize); window.removeEventListener('sirius-data-changed', load); window.removeEventListener('keydown', keyboard); };
  }, []);
  const prefetch = e => { if (window.innerWidth >= 768 && e.target.closest('a[href="/workouts"]')) void cachedGet('/workout-plans').catch(() => {}); };
  return <QueryClientProvider client={queryClient}><div className="sirius-app-shell" data-collapsed={collapsed} onMouseOver={prefetch} onFocus={prefetch}>
    <a className="sirius-skip-link" href="#page-content">Ir para o conteúdo</a>
    <Sidebar user={user} />
    <div className="sirius-shell-body">
      <header className="sirius-topbar">
        <button className="sirius-search-trigger" onClick={() => setPalette('search')}><Search size={18} /><span>Buscar no Sirius</span><kbd className="hidden lg:inline">Ctrl K</kbd></button>
        <div className="flex items-center gap-1 sm:gap-3">
          <button className="sirius-quick-add" onClick={() => setPalette('add')} aria-label="Adicionar"><Plus size={18} /><span className="hidden sm:inline">Adicionar</span></button>
          <Link to="/notifications" aria-label="Notificações" className="sirius-icon-button"><Bell size={19} /></Link>
          <Link to="/profile" aria-label="Perfil" className="sirius-icon-button"><User size={19} /></Link>
        </div>
      </header>
      {user && <FocusResume userId={user.user_id} />}
      <div id="page-content" key={sessionEpoch} tabIndex={-1}><Outlet /></div>
    </div>
    <MobileNav user={user} />
    <FloatingAssistant />
    <CommandPalette mode={palette} onClose={() => setPalette(null)} />
  </div></QueryClientProvider>;
}
