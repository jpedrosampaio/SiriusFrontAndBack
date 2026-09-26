import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useLocation } from 'react-router-dom';
import { Sparkles } from 'lucide-react';

const Chat = lazy(() => import('./AiChatModal'));
const POSITION_KEY = 'sirius-assistant-position-v1';
export function clampPosition(point, width, height) {
  const bottom = width < 768 ? 148 : 76;
  return { x: Math.max(12, Math.min(Number(point?.x) || width - 68, width - 68)),
    y: Math.max(64, Math.min(Number(point?.y) || height - bottom, Math.max(64, height - bottom))) };
}

export default function FloatingAssistant() {
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [position, setPosition] = useState(() => {
    let saved; try { saved = JSON.parse(localStorage.getItem(POSITION_KEY)); } catch { /* Optional operation failed; preserve the current view. */ }
    return clampPosition(saved, window.innerWidth, window.innerHeight);
  });
  const drag = useRef(null);
  const moved = useRef(false);
  const button = useRef(null);
  const close = () => { setOpen(false); requestAnimationFrame(() => button.current?.focus()); };
  useEffect(() => {
    const resize = () => setPosition(p => clampPosition(p, window.innerWidth, window.innerHeight));
    window.addEventListener('resize', resize);
    return () => window.removeEventListener('resize', resize);
  }, []);
  useEffect(() => { setOpen(false); }, [pathname]);
  useEffect(() => {
    const configure = () => setOpen(false);
    window.addEventListener('open-gemini-key-modal', configure);
    return () => window.removeEventListener('open-gemini-key-modal', configure);
  }, []);
  if (['/', '/login', '/register'].includes(pathname)) return null;
  const save = p => { setPosition(p); try { localStorage.setItem(POSITION_KEY, JSON.stringify(p)); } catch { /* Optional operation failed; preserve the current view. */ } };
  return createPortal(<>
    <button ref={button} type="button" className="sirius-assistant-launcher" aria-label="Abrir assistente Sirius"
      aria-expanded={open} aria-controls="sirius-assistant-panel" title="Abrir assistente · arraste para mover"
      style={{ left: position.x, top: position.y, visibility: open ? 'hidden' : 'visible' }}
      onPointerDown={e => { if (e.button !== 0) return; moved.current = false; drag.current = { x: e.clientX, y: e.clientY, position }; e.currentTarget.setPointerCapture(e.pointerId); }}
      onPointerMove={e => {
        if (!drag.current) return;
        const dx = e.clientX - drag.current.x, dy = e.clientY - drag.current.y;
        if (Math.hypot(dx, dy) > 6) moved.current = true;
        if (moved.current) setPosition(clampPosition({ x: drag.current.position.x + dx, y: drag.current.position.y + dy }, window.innerWidth, window.innerHeight));
      }}
      onPointerUp={() => { if (drag.current && moved.current) save(position); drag.current = null; }}
      onPointerCancel={() => { drag.current = null; moved.current = true; }}
      onClick={() => { if (!moved.current) { setLoaded(true); setOpen(true); } moved.current = false; }}
      onKeyDown={e => {
        const directions = { ArrowLeft: [-24, 0], ArrowRight: [24, 0], ArrowUp: [0, -24], ArrowDown: [0, 24] };
        if (directions[e.key]) { e.preventDefault(); const [x, y] = directions[e.key]; save(clampPosition({ x: position.x + x, y: position.y + y }, window.innerWidth, window.innerHeight)); }
      }}><Sparkles aria-hidden="true" className="w-6 h-6" /><span className="sr-only">Use as setas para mover</span></button>
    {loaded && <Suspense fallback={open ? <button className="sirius-assistant-loading" onClick={close}>Carregando assistente… Fechar</button> : null}><Chat open={open} onClose={close} /></Suspense>}
  </>, document.body);
}
