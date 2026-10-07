import axios from 'axios';
import { cacheKey, queryClient, sessionVersion } from '@/lib/query-cache';
import { getApiErrorMessage } from '@/lib/api-errors';

export const editalJobsKey = () => cacheKey('edital-jobs');
export const EDITAL_CAPABILITY_STALE = 60000;
// Match the existing worker's 900-second processing ceiling, not the upload's 60s.
export const EDITAL_DIRECT_TIMEOUT = 900000;
export async function queryEditalJobs(api, signal) {
  const version = sessionVersion();
  const { data } = await axios.get(`${api}/study/edital-jobs`, { signal, timeout: 20000 });
  if (version !== sessionVersion()) throw new Error('Session changed');
  if (!Array.isArray(data?.jobs) || typeof data.upload_available !== 'boolean') throw new Error('Invalid capability response');
  return data;
}
export function fetchEditalCapability(api) {
  return queryClient.fetchQuery({ queryKey: editalJobsKey(), staleTime: EDITAL_CAPABILITY_STALE, queryFn: ({ signal }) => queryEditalJobs(api, signal) });
}
export function activeEditalJobs(data) { return (data?.jobs || []).some(job => ['queued', 'running'].includes(job.status)); }
export function isStorageUnavailable(error) { return error?.response?.data?.detail?.code === 'durable_storage_unavailable'; }
export function editalErrorMessage(error) {
  if (error?.code === 'ERR_CANCELED') return 'Espera interrompida. A análise no servidor pode continuar; ao reenviar o PDF, uma análise salva poderá ser reutilizada.';
  if (error?.code === 'ECONNABORTED' || error?.code === 'ETIMEDOUT' || error?.response?.status === 504) return 'A análise demorou mais que o esperado. Tente novamente.';
  if (!error?.response) return 'Não foi possível receber a análise. Verifique sua conexão e tente novamente. O PDF foi preservado nesta tela.';
  return getApiErrorMessage(error, 'Não foi possível analisar o edital. Tente novamente.');
}
