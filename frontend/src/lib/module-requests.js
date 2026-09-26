import axios from 'axios';

// Account-bound memory cache. Mutations invalidate before and after the write.
export function createModuleRequests(client, now = () => Date.now()) {
  let epoch = 0;
  const cache = new Map();
  const pending = new Map();
  const invalidate = () => { epoch += 1; cache.clear(); pending.clear(); };
  const get = (url, config = {}) => {
    if (config.signal || config.responseType || config.cache === false) return client.get(url, config);
    const key = JSON.stringify([url, config.params || {}]);
    if (cache.get(key)?.until > now()) return Promise.resolve(cache.get(key).value);
    if (pending.has(key)) return pending.get(key);
    const version = epoch;
    const promise = client.get(url, config).catch(error => {
      if (!error.response || [502, 503, 504].includes(error.response.status)) return client.get(url, config);
      throw error;
    }).then(value => {
      if (epoch === version) { if (cache.size >= 100) cache.clear(); cache.set(key, { value, until: now() + 10000 }); }
      return value;
    }).finally(() => { if (pending.get(key) === promise) pending.delete(key); });
    pending.set(key, promise);
    return promise;
  };
  const result = { get, invalidate };
  for (const method of ['post', 'put', 'patch', 'delete']) result[method] = async (...args) => {
    invalidate();
    try { return await client[method](...args); } finally { invalidate(); }
  };
  return result;
}

const requests = createModuleRequests(axios);
window.addEventListener('sirius-auth-changed', requests.invalidate);
window.addEventListener('sirius-data-changed', requests.invalidate);
window.addEventListener('storage', event => { if (!event.key || event.key === 'sirius_session_token') requests.invalidate(); });
export default requests;
