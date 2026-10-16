// Keep OS acceptance separate from the server acknowledgement and from reading.
export async function presentNativeNotice(title, options, current, onClick) {
  let registration, lookupTimer;
  try {
    registration = await Promise.race([navigator.serviceWorker?.getRegistration(), new Promise(resolve => {
      lookupTimer = setTimeout(() => resolve(null), 2000);
    })]);
  } catch { /* desktop fallback */ }
  finally { clearTimeout(lookupTimer); }
  if (!current()) return { outcome: 'uncertain', close() {} };
  if (registration?.showNotification) {
    let timer;
    const close = async () => {
      try {
        const notices = await registration.getNotifications({ tag: options.tag });
        notices.filter(n => n.data?.presentation_token === options.data.presentation_token).forEach(n => n.close());
      } catch { /* Closing an OS surface is best effort. */ }
    };
    try {
      const accepted = registration.showNotification(title, options).then(() => {
        if (!current()) void close();
        return true;
      });
      // Timeout is ambiguous: the browser might accept later. Never fall back
      // or automatically repeat an attempt whose outcome is uncertain.
      const outcome = await Promise.race([accepted, new Promise(resolve => { timer = setTimeout(() => resolve(false), 5000); })]);
      return { outcome: outcome ? 'accepted' : 'uncertain', close };
    } catch { /* A rejected SW API permits the desktop constructor fallback. */ }
    finally { clearTimeout(timer); }
  }
  if (!current()) return { outcome: 'uncertain', close() {} };
  try {
    const notice = new Notification(title, options);
    notice.onclick = () => { if (current()) onClick(); notice.close(); };
    return { outcome: 'accepted', close: () => notice.close() };
  } catch { return { outcome: 'failed', close() {} }; }
}
