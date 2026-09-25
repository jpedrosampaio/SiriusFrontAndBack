import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { readSaved, writeSaved } from '@/lib/session-storage';

export default function useStudyDraft({ api, userId, notebookId, topicKey }) {
  const key = `sirius-draft:${userId}:${notebookId}:${topicKey || 'general'}`;
  const [draft, setDraft] = useState({ key, text: readSaved(key)?.text || '' });
  const [status, setStatus] = useState('Carregando anotações…');
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const reconnect = () => setReload(n => n + 1);
    window.addEventListener('online', reconnect);
    return () => window.removeEventListener('online', reconnect);
  }, []);
  const revision = useRef(0);
  const current = useRef(key); current.current = key;
  const timer = useRef(null);
  const queue = useRef(Promise.resolve());
  const ready = useRef(false);
  const dirty = useRef(false);
  const latestText = useRef(draft.text);
  const endpoint = `${api}/study/notebooks/${notebookId}/draft?topic_key=${encodeURIComponent(topicKey || 'general')}`;
  const save = useCallback((text, savedKey = key) => {
    queue.current = queue.current.catch(() => {}).then(async () => {
      if (current.current !== savedKey || !ready.current) return;
      setStatus('Salvando…');
      try {
        const response = await axios.put(endpoint, { text, revision: revision.current });
        if (current.current !== savedKey) return;
        revision.current = response.data.revision;
        const latest = readSaved(savedKey);
        if (latestText.current === text) { writeSaved(savedKey, { text, dirty: false, revision: response.data.revision }); dirty.current = false; setStatus('Salvo na sua conta'); }
        else { if (latest) writeSaved(savedKey, { ...latest, revision: response.data.revision }); setStatus('Salvando alterações mais recentes…'); }
      } catch (error) {
        if (current.current !== savedKey) return;
        if (error.response?.status === 409) ready.current = false;
        setStatus(error.response?.status === 409 ? 'Outra aba alterou esta anotação. Copie seu texto antes de recarregar.' : 'Sem confirmação do servidor. Rascunho mantido neste dispositivo; tente salvar novamente.');
      }
    });
  }, [endpoint, key]);
  useEffect(() => {
    clearTimeout(timer.current); ready.current = false; dirty.current = false;
    const local = readSaved(key);
    latestText.current = local?.text || '';
    setDraft({ key, text: local?.text || '' });
    if (!notebookId) { setStatus(''); return; }
    let active = true;
    axios.get(endpoint).then(({ data }) => {
      if (!active) return;
      const latest = readSaved(key);
      if (latest?.dirty && latest.text !== data.text && (latest.revision == null ? !!data.text : latest.revision !== data.revision)) {
        setStatus('Há uma versão diferente na conta. Copie seu rascunho antes de recarregar em outro dispositivo.'); return;
      }
      revision.current = data.revision; ready.current = true;
      if (latest?.dirty || dirty.current) { save(latestText.current); }
      else { latestText.current = data.text; setDraft({ key, text: data.text }); writeSaved(key, { text: data.text, dirty: false, revision: data.revision }); setStatus('Salvo na sua conta'); }
    }).catch(() => { if (active) setStatus('Rascunho local. Recarregue para sincronizar com sua conta.'); });
    return () => { active = false; clearTimeout(timer.current); };
  }, [key, endpoint, notebookId, save, reload]);
  const change = text => {
    dirty.current = true; latestText.current = text; setDraft({ key, text });
    const persisted = writeSaved(key, { text, dirty: true, revision: ready.current ? revision.current : readSaved(key)?.revision ?? null });
    setStatus(persisted ? 'Rascunho salvo neste dispositivo' : 'Armazenamento indisponível. Mantenha a página aberta até salvar.');
    clearTimeout(timer.current); timer.current = setTimeout(() => save(text), 700);
  };
  return { notes: draft.key === key ? draft.text : readSaved(key)?.text || '', setNotes: change, status, retry: () => ready.current ? save(draft.text) : setReload(n => n + 1) };
}
