import { useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const NOTICE = 'sirius-owned-notice';
const POLL_INTERVAL = 60000;

function Preview({ item, onRendered }) {
  useEffect(() => { onRendered(); }, [onRendered]);
  return <span className="block break-words">{item.preview}{item.grouped_count > 0 && ` Outros ${item.grouped_count} avisos estão na central.`}</span>;
}

export default function NotificationManager() {
  useEffect(() => {
    let active = true, generation = 0, pending = false, timer, state, nextKey, recoveryAttempts = 0;
    let abort = new AbortController(), shown = new Set(), nativeNotice;
    let toastId = `${NOTICE}-${crypto.randomUUID()}`;
    const current = stamp => active && generation === stamp && !abort.signal.aborted;
    const options = () => ({ withCredentials: true, signal: abort.signal, timeout: 15000 });
    const central = () => window.location.assign('/notifications');
    const closeNative = () => { if (nativeNotice) nativeNotice.close(); nativeNotice = null; };
    const action = stamp => ({ label: 'Ver na central', onClick: () => { if (current(stamp)) central(); } });
    async function check(recovering = false) {
      if (!active || pending || document.visibilityState !== 'visible') return;
      pending = true;
      const stamp = generation;
      let nextDelay = POLL_INTERVAL;
      try {
        if (!recovering || !state?.user_id || !nextKey) {
          const configuration = await axios.get(`${API}/automations/state`, options());
          if (!current(stamp)) return;
          if (state?.user_id && state.user_id !== configuration.data?.user_id) { window.dispatchEvent(new Event('sirius-auth-changed')); return; }
          state = configuration.data;
        }
        // No personal notice before the server identifies the current account.
        if (typeof state?.user_id !== 'string') { state = null; return; }
        let item;
        if (state.enabled) {
          if (!nextKey) { nextKey = crypto.randomUUID(); recoveryAttempts = 0; }
          const key = nextKey;
          const response = await axios.post(`${API}/automations/presentations/claim`, {}, {
            ...options(), headers: { 'Idempotency-Key': key },
          });
          if (!current(stamp)) return;
          if (response.data?.user_id !== state.user_id) { window.dispatchEvent(new Event('sirius-auth-changed')); return; }
          item = response.data?.item;
          nextKey = null;
          if (item && !shown.has(item.delivery_id)) {
            shown.add(item.delivery_id);
            if (shown.size > 50) shown.delete(shown.values().next().value);
            let acknowledged = false;
            const onRendered = () => {
              if (acknowledged || !current(stamp)) return;
              acknowledged = true;
              // Render confirmation is deliberately independent from reading.
              void axios.post(`${API}/automations/presentations/${item.delivery_id}`, { key }, options()).catch(() => {});
            };
            toast(item.title, { id: toastId, description: <Preview item={item} onRendered={onRendered} />,
              duration: 6000, action: action(stamp) });
          }
        }
        const browserAllowed = 'Notification' in window && Notification.permission === 'granted';
        const response = await axios.get(`${API}/notifications/check`, { ...options(), params: { browser_allowed: browserAllowed } });
        if (!current(stamp)) return;
        const reminders = Array.isArray(response.data) ? response.data : [];
        const inApp = reminders.filter(n => n.channels?.includes('in_app'));
        if (!item && inApp.length) toast(inApp.length > 1 ? `${inApp.length} lembretes disponíveis` : inApp[0].title,
          { id: toastId, description: 'Confira os detalhes na central de Notificações.', duration: 6000, action: action(stamp) });
        const browser = reminders.filter(n => n.channels?.includes('browser'));
        // Permission is requested only by the explicit control in Notifications.
        if (browser.length && 'Notification' in window && Notification.permission === 'granted') {
          closeNative();
          nativeNotice = new Notification(browser.length > 1 ? `${browser.length} lembretes disponíveis` : browser[0].title,
            { body: 'Confira os detalhes na central de Notificações.', tag: NOTICE, icon: '/favicon.ico' });
          const notice = nativeNotice;
          notice.onclick = () => { if (current(stamp)) { window.focus(); central(); } notice.close(); };
          setTimeout(() => notice.close(), 6000);
        }
      } catch (e) {
        // Keep an uncertain claim key; server history prevents automatic replays.
        // One prompt retry fits the server's 30s recovery window even after the
        // 15s request timeout. Further failures return to normal bounded polling.
        if (nextKey && recoveryAttempts < 1 && (!e.response || e.response.status >= 500)) {
          recoveryAttempts += 1; nextDelay = 1000;
        }
        // Configuration and history failures remain visible in the central UI.
      } finally {
        if (current(stamp)) { pending = false; clearTimeout(timer); timer = setTimeout(() => check(nextDelay === 1000), nextDelay); }
      }
    }
    const reset = () => {
      generation += 1; abort.abort(); abort = new AbortController();
      pending = false; state = null; nextKey = null; recoveryAttempts = 0; shown = new Set();
      clearTimeout(timer); toast.dismiss(toastId); toastId = `${NOTICE}-${crypto.randomUUID()}`; closeNative(); void check();
    };
    const visible = () => { if (document.visibilityState === 'visible') { clearTimeout(timer); void check(); } };
    const storage = event => { if (event.key === 'sirius_session_token' || event.key === null) reset(); };
    window.addEventListener('sirius-auth-changed', reset);
    window.addEventListener('sirius-automations-changed', reset);
    window.addEventListener('storage', storage);
    window.addEventListener('online', visible);
    document.addEventListener('visibilitychange', visible);
    void check();
    return () => {
      active = false; generation += 1; abort.abort(); clearTimeout(timer); toast.dismiss(toastId); closeNative();
      window.removeEventListener('sirius-auth-changed', reset);
      window.removeEventListener('sirius-automations-changed', reset);
      window.removeEventListener('storage', storage);
      window.removeEventListener('online', visible);
      document.removeEventListener('visibilitychange', visible);
    };
  }, []);
  return null;
}
