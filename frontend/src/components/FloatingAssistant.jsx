import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useLocation } from 'react-router-dom';
import { Sparkles } from 'lucide-react';

const Chat = lazy(() => import('./AiChatModal'));
export function clampPosition(point, width, height) {
  const bottom = width < 768 ? 148 : 76;
  return { x: Math.max(12, Math.min(Number(point?.x) || width - 68, width - 68)),
    y: Math.max(64, Math.min(Number(point?.y) || height - bottom, Math.max(64, height - bottom))) };
}

export default function FloatingAssistant() {
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [context, setContext] = useState({});
  const trigger = useRef(null);
  const restoreFocus = () => {
    const deadline = performance.now() + 500;
    const visible = element => element?.isConnected && element !== document.body && element.getClientRects().length && getComputedStyle(element).visibility === 'visible';
    const attempt = () => {
      // A newly opened dialog owns focus, including palette -> assistant handoffs.
      if (document.querySelector('[role="dialog"][data-state="open"]')) return;
      const target = visible(trigger.current) ? trigger.current
        : Array.from(document.querySelectorAll('button[aria-label="Abrir assistente Sirius"]')).find(visible);
      target?.focus({ preventScroll: true });
      if ((!target || document.activeElement !== target) && performance.now() < deadline) requestAnimationFrame(attempt);
    };
    requestAnimationFrame(attempt);
  };
  // Radix restores focus after removing the modal focus trap. Restoring here
  // as well can race that teardown and send focus back into the closing panel.
  const close = () => setOpen(false);
  useEffect(() => { setOpen(false); setContext({}); }, [pathname]);
  useEffect(() => {
    const show = event => { trigger.current = document.activeElement; setContext(event.detail || {}); setLoaded(true); setOpen(true); };
    const configure = () => setOpen(false);
    window.addEventListener('sirius-open', show);
    window.addEventListener('open-gemini-key-modal', configure);
    return () => { window.removeEventListener('sirius-open', show); window.removeEventListener('open-gemini-key-modal', configure); };
  }, []);
  return createPortal(<>
    {pathname !== '/chat' && <button type="button" className="sirius-assistant-launcher" aria-label="Abrir assistente Sirius"
      aria-expanded={open} aria-controls="sirius-assistant-panel" title="Conversar com Sirius"
      style={{ right: 24, bottom: 24, cursor: 'pointer', visibility: open ? 'hidden' : 'visible' }}
      onClick={event => { trigger.current = event.currentTarget; setContext({}); setLoaded(true); setOpen(true); }}><Sparkles aria-hidden="true" className="w-6 h-6" /></button>}
    {loaded && <Suspense fallback={open ? <button className="sirius-assistant-loading" onClick={() => { close(); restoreFocus(); }}>Carregando Sirius… Fechar</button> : null}><Chat open={open} onClose={close} onRestoreFocus={restoreFocus} context={context} /></Suspense>}
  </>, document.body);
}
