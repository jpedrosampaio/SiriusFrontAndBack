import { pipeline, env } from '@xenova/transformers';

env.allowWasm = true;
env.allowRemoteModels = true;
env.backends.onnx.wasm.proxy = false;
env.backends.onnx.wasm.numThreads = 1;

class LocalAIService {
  constructor() {
    this.generator = null;
    this.tokenizer = null;
    this.isLoading = false;
    this.loadingProgress = 0;
    this.status = 'idle';
    this.listeners = new Set();
    this._notify();
  }

  subscribe(fn) {
    this.listeners.add(fn);
    fn(this.getState());
    return () => this.listeners.delete(fn);
  }

  getState() {
    return {
      status: this.status,
      progress: this.loadingProgress,
      isReady: !!this.generator,
      error: this.error,
    };
  }

  _notify() {
    const state = this.getState();
    this.listeners.forEach((fn) => fn(state));
  }

  async loadModel() {
    if (this.generator) return;
    if (this.isLoading) return;
    this.isLoading = true;
    this.status = 'downloading';
    this.error = null;
    this._notify();
    try {
      this.generator = await pipeline('text-generation', 'Xenova/LaMini-GPT-124M', {
        progress_callback: (p) => {
          if (p.status === 'download' && typeof p.progress === 'number') {
            this.loadingProgress = p.progress;
          } else if (p.status === 'done') {
            this.loadingProgress = 1;
          }
          this._notify();
        },
      });
      this.status = 'ready';
      this.isLoading = false;
      this._notify();
    } catch (err) {
      console.error('Failed to load local AI model:', err);
      this.error = err.message || 'Erro ao carregar modelo';
      this.status = 'error';
      this.isLoading = false;
      this._notify();
    }
  }

  async generate(prompt, systemMessage = 'Você é um assistente fitness especializado em treinos, nutrição e saúde.', signal) {
    if (!this.generator) {
      await this.loadModel();
      if (!this.generator) {
        throw new Error(this.error || 'Modelo não carregado');
      }
    }
    const formattedPrompt = `${systemMessage}\n\nUser: ${prompt}\nAssistant:`;
    const result = await this.generator(formattedPrompt, {
      max_new_tokens: 512,
      temperature: 0.7,
      top_p: 0.9,
      repetition_penalty: 1.1,
      do_sample: true,
      signal,
    });
    const raw = result[0]?.generated_text || '';
    const answer = raw.split('Assistant:').pop() || raw;
    return answer.trim();
  }

  reset() {
    this.generator?.dispose?.();
    this.generator = null;
    this.tokenizer = null;
    this.status = 'idle';
    this.loadingProgress = 0;
    this.error = null;
    this._notify();
  }
}

const localAi = new LocalAIService();
export default localAi;
