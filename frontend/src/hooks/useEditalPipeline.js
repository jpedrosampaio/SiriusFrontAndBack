import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { cacheKey, queryClient, sessionVersion } from '@/lib/query-cache';
import { getApiErrorMessage } from '@/lib/api-errors';

export default function useEditalPipeline(api, analysisId) {
  const key = cacheKey('edital-pipeline', analysisId);
  const [hidden, setHidden] = useState(document.hidden), [pending, setPending] = useState(false), [error, setError] = useState('');
  const active = useRef(null), retry = useRef(null), mounted = useRef(true);
  const query = useQuery({ queryKey: key, retry: false, staleTime: 0,
    queryFn: async ({ signal }) => {
      const version = sessionVersion(), previous = queryClient.getQueryData(key);
      const response = await axios.get(`${api}/study/edital-pipeline/${analysisId}`, { signal, timeout: 20000,
        headers: previous?._etag ? { 'If-None-Match': previous._etag } : {}, validateStatus: status => status === 200 || status === 304 });
      if (version !== sessionVersion()) throw new Error('Session changed');
      if (response.status === 304 && previous) return previous;
      if (response.data?.pipeline !== 'edital/universal/6' || response.data?.analysis_id !== analysisId || !response.data?.manifest) throw new Error('Invalid analysis response');
      return { ...response.data, _etag: response.headers.etag };
    },
    refetchInterval: state => state.state.data?.manifest.status === 'processing' ? (hidden ? 15000 : 4000) : false,
    refetchIntervalInBackground: true,
  });
  useEffect(() => {
    mounted.current = true;
    const visibility = () => setHidden(document.hidden);
    document.addEventListener('visibilitychange', visibility);
    return () => { mounted.current = false; active.current?.abort(); document.removeEventListener('visibilitychange', visibility); };
  }, [analysisId]);
  const command = async (action, body = {}) => {
    if (active.current || !query.data) return null;
    const version = sessionVersion(), controller = new AbortController(); active.current = controller;
    setPending(true); setError('');
    const fingerprint = JSON.stringify([analysisId, action, body]);
    if (retry.current?.fingerprint !== fingerprint) retry.current = { fingerprint, id: crypto.randomUUID(), payload: { revision: query.data.revision, ...body } };
    const payload = retry.current.payload;
    try {
      const { data } = await axios.post(`${api}/study/edital-pipeline/${analysisId}/${action}`, payload, {
        headers: { 'Idempotency-Key': retry.current.id }, signal: controller.signal, timeout: 30000,
      });
      if (version !== sessionVersion() || !mounted.current || controller.signal.aborted) return null;
      retry.current = null;
      await queryClient.invalidateQueries({ queryKey: key });
      window.dispatchEvent(new Event('edital-job-created'));
      return data;
    } catch (failure) {
      if (version === sessionVersion() && mounted.current && !controller.signal.aborted) {
        setError(getApiErrorMessage(failure, 'Não foi possível confirmar a operação. Tente a mesma ação para recuperar seu recibo.'));
        if (failure.response?.status === 409) { retry.current = null; await query.refetch(); }
      }
      return null;
    } finally { if (active.current === controller) active.current = null; if (mounted.current && version === sessionVersion()) setPending(false); }
  };
  return { ...query, command, pending, commandError: error };
}
