import { useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const POLL_INTERVAL = 60000; // Check every 60 seconds

export default function NotificationManager() {
  const intervalRef = useRef(null);
  const permissionRef = useRef(typeof Notification === 'undefined' ? 'denied' : Notification.permission);
  const generationRef = useRef(0);
  const alertsRef = useRef(new Map());
  const enabledRef = useRef(false);

  const requestPermission = useCallback(async () => {
    if (!('Notification' in window)) return false;
    if (Notification.permission === 'granted') return true;
    if (Notification.permission === 'denied') return false;

    const permission = await Notification.requestPermission();
    permissionRef.current = permission;
    return permission === 'granted';
  }, []);

  const showNotification = useCallback((title, options = {}) => {
    if (permissionRef.current !== 'granted') return;

    try {
      const notification = new Notification(title, {
        icon: '/logo192.png',
        badge: '/logo192.png',
        vibrate: [200, 100, 200],
        tag: options.tag || 'sirius-notification',
        ...options,
      });

      notification.onclick = () => {
        window.focus();
        if (options.url) {
          window.location.href = options.url;
        }
        notification.close();
      };

      // Auto-close after 8 seconds
      setTimeout(() => notification.close(), 8000);
    } catch (e) {
      console.warn('Notification failed:', e);
    }
  }, []);

  const checkNotifications = useCallback(async () => {
    const generation = generationRef.current;
    try {
      const inbox = enabledRef.current ? await axios.get(`${API}/automations/inbox`, { withCredentials: true }) : { data: [] };
      if (generation !== generationRef.current) return;
      const unseen = Array.isArray(inbox.data) ? inbox.data.find(n => !alertsRef.current.has(n.delivery_id)) : null;
      if (unseen) {
        const key = crypto.randomUUID();
        alertsRef.current.set(unseen.delivery_id, key);
        if (alertsRef.current.size > 50) alertsRef.current.delete(alertsRef.current.keys().next().value);
        toast(unseen.title, {
          id: `automation-${unseen.delivery_id}`, description: unseen.message.slice(0, 240), duration: 8000,
          action: { label: 'Marcar como lido', onClick: async () => {
            if (generation !== generationRef.current) return;
            try { await axios.post(`${API}/automations/deliveries/${unseen.delivery_id}`, { action: 'read' },
              { withCredentials: true, headers: { 'Idempotency-Key': key } }); }
            catch(e) { if (generation === generationRef.current) toast.error('Leitura não confirmada. Abra Notificações para tentar novamente.'); }
          } },
        });
      }
    } catch(e) { /* Unauthenticated sessions have no owned inbox. Console shows request failures. */ }
    if (permissionRef.current !== 'granted') return;
    try {
      const timezoneOffset = new Date().getTimezoneOffset();
      const res = await axios.get(
        `${API}/notifications/check?timezone_offset=${timezoneOffset}`,
        { withCredentials: true }
      );

      const notifications = res.data;
      if (generation !== generationRef.current) return;
      if (Array.isArray(notifications) && notifications.length > 0) {
        notifications.forEach((notif, idx) => {
          setTimeout(() => {
            if (generation !== generationRef.current) return;
            showNotification(notif.title || 'Sirius', {
              body: notif.message || notif.body || '',
              tag: notif.notification_id || `notif-${idx}`,
              url: notif.action_link || '/dashboard',
            });
          }, idx * 1500); // Stagger notifications
        });
      }
    } catch (e) {
      // Silently fail - user may not be logged in
    }
  }, [showNotification]);

  useEffect(() => {
    const reset = () => {
      generationRef.current += 1;
      enabledRef.current = false;
      for (const identity of alertsRef.current.keys()) toast.dismiss(`automation-${identity}`);
      alertsRef.current.clear();
    };
    let active = true;
    const configure = async () => {
      const generation = generationRef.current;
      try {
        const state = await axios.get(`${API}/automations/state`, { withCredentials: true });
        if (!active || generation !== generationRef.current) return;
        enabledRef.current = state.data.enabled === true;
        if (enabledRef.current) checkNotifications();
      } catch(e) { /* Console exposes configuration errors; unavailable/anonymous state does not opt in. */ }
    };
    const onAuth = () => { reset(); configure(); };
    window.addEventListener('sirius-auth-changed', onAuth);
    window.addEventListener('sirius-automations-changed', configure);
    const onStorage = event => { if(event.key === 'sirius_session_token' || event.key === null) onAuth(); };
    window.addEventListener('storage', onStorage);
    configure();
    intervalRef.current = setInterval(checkNotifications, POLL_INTERVAL);
    // Request permission on mount
    requestPermission().then(granted => {
        if (!active) return;
        if (granted) checkNotifications();
    });

    return () => {
      active = false;
      reset();
      window.removeEventListener('sirius-auth-changed', onAuth);
      window.removeEventListener('sirius-automations-changed', configure);
      window.removeEventListener('storage', onStorage);
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [requestPermission, checkNotifications]);

  // No visible UI
  return null;
}
