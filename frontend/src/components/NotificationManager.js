import { useEffect, useRef, useCallback } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const POLL_INTERVAL = 60000; // Check every 60 seconds

export default function NotificationManager() {
  const intervalRef = useRef(null);
  const permissionRef = useRef(Notification?.permission);

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
    try {
      const timezoneOffset = new Date().getTimezoneOffset();
      const res = await axios.get(
        `${API}/notifications/check?timezone_offset=${timezoneOffset}`,
        { withCredentials: true }
      );

      const notifications = res.data;
      if (Array.isArray(notifications) && notifications.length > 0) {
        notifications.forEach((notif, idx) => {
          setTimeout(() => {
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
    // Request permission on mount
    requestPermission().then((granted) => {
      if (granted) {
        // Initial check
        checkNotifications();
        // Start polling
        intervalRef.current = setInterval(checkNotifications, POLL_INTERVAL);
      }
    });

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [requestPermission, checkNotifications]);

  // No visible UI
  return null;
}
