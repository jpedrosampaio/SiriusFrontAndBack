import { QueryClient } from '@tanstack/react-query';
import axios from 'axios';

export const queryClient = new QueryClient({ defaultOptions: { queries: {
  staleTime: 30000, gcTime: 300000, retry: false, refetchOnWindowFocus: false,
} } });
let session = 0;
export const cacheKey = (...parts) => ['session', session, ...parts];
export const sessionVersion = () => session;
export function clearSessionCache() {
  session += 1;
  void queryClient.cancelQueries();
  queryClient.clear();
}
window.addEventListener('sirius-auth-changed', clearSessionCache);
window.addEventListener('storage', e => { if (!e.key || e.key === 'sirius_session_token') clearSessionCache(); });
// Conservative invalidation for legacy mutations while migrating modules incrementally.
window.addEventListener('sirius-data-changed', () => { void queryClient.invalidateQueries({ predicate: q => !q.queryKey.includes('conversation') && !q.queryKey.includes('tutorial-videos'), refetchType: 'active' }); });
export function cachedGet(path, options = {}) {
  const version = session;
  const { mergeResponse, ...queryOptions } = options;
  return queryClient.fetchQuery({ queryKey: cacheKey(path), ...queryOptions, queryFn: async ({ signal }) => {
    const response = await axios.get(`${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000'}/api${path}`, { signal, timeout: 20000 });
    if (version !== session) throw new Error('Session changed');
    return mergeResponse ? mergeResponse(response.data, queryClient.getQueryData(cacheKey(path))) : response.data;
  } });
}
