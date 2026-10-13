import axios from "axios";
import { getApiErrorMessage } from "./api-errors";
import { OFFLINE_MODE, OFFLINE_USER, OFFLINE_DEMO_DATA } from "./offline-mode";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';
const API = `${BACKEND_URL}/api`;

// Re-export for convenience
export { OFFLINE_MODE };

// Session token management via localStorage
const TOKEN_KEY = "sirius_session_token";
let userCache = null;
let userRequest = null;
let authGeneration = 0;
let sessionGeneration = 0;
function invalidateUser() { userCache = null; userRequest = null; authGeneration += 1; }
function invalidateAuthentication() {
  sessionGeneration += 1; invalidateUser();
  try { window.sessionStorage?.removeItem('sirius-conversation'); } catch { /* Storage can be disabled. */ }
}
function sessionChangedError() {
  return Object.assign(new Error('A sessão mudou. A resposta anterior foi descartada.'), { code: 'ERR_CANCELED', __CANCEL__: true });
}
function belongsToCurrentSession(config) {
  return config?.siriusSessionGeneration === undefined || config.siriusSessionGeneration === sessionGeneration;
}
// Memory only: never reuse one account's response after logout or a token change.
export function getCurrentUser() {
  if (userCache && userCache.until > Date.now()) return Promise.resolve(userCache.response);
  if (userRequest) return userRequest;
  const generation = authGeneration;
  const session = sessionGeneration;
  const request = axios.get(`${API}/auth/me`, { withCredentials: true }).then(response => {
    if (session !== sessionGeneration) throw sessionChangedError();
    if (generation === authGeneration) userCache = { response, until: Date.now() + 30000 };
    return response;
  }).finally(() => { if (userRequest === request) userRequest = null; });
  userRequest = request;
  return request;
}
window.addEventListener('storage', event => { if (event.key === TOKEN_KEY || event.key === null) invalidateAuthentication(); });
window.addEventListener('sirius-auth-changed', invalidateAuthentication);

export const isOfflineMode = () => OFFLINE_MODE;

export const getToken = () => {
  if (OFFLINE_MODE) return 'offline_token';
  return localStorage.getItem(TOKEN_KEY);
};
export const setToken = (token) => {
  invalidateAuthentication();
  if (!OFFLINE_MODE) localStorage.setItem(TOKEN_KEY, token);
  window.dispatchEvent(new Event('sirius-auth-changed'));
};
export const clearToken = () => {
  invalidateAuthentication();
  if (!OFFLINE_MODE) localStorage.removeItem(TOKEN_KEY);
  window.dispatchEvent(new Event('sirius-auth-changed'));
};

export const getOfflineUser = () => OFFLINE_USER;
export const getOfflineData = () => OFFLINE_DEMO_DATA;

// Set up global axios interceptor to add Authorization header
axios.interceptors.request.use(
  (config) => {
    config.siriusSessionGeneration = sessionGeneration;
    const token = getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    // Always include credentials for cookie fallback
    config.withCredentials = true;
    return config;
  },
  (error) => Promise.reject(error)
);

// Interceptor for 401 responses - clear token and redirect to login
axios.interceptors.response.use(
  (response) => {
    if (!belongsToCurrentSession(response.config)) return Promise.reject(sessionChangedError());
    const isChatTransport = /\/ai\/(chat|cancel\/)/.test(response.config?.url || '');
    const url = response.config?.url || '';
    const isFinancialPreview = /\/finance\/intelligence\/(simulate|compare-debts)(?:\?|$)/.test(url) || /\/projections\/insights(?:\?|$)/.test(url);
    const isTrainingPreview = /\/workouts\/intelligence\/substitutions(?:\?|$)/.test(url);
    const isIntegratedPreview = /\/command\/scenarios(?:\?|$)/.test(url) || /\/life\/simulate(?:\?|$)/.test(url) || /\/study\/programs\/[^/]+\/strategy\/simulate(?:\?|$)/.test(url);
      const isNutritionPreview = /\/nutrition\/intelligence\/alternatives(?:\?|$)/.test(url) || /\/nutrition\/import-plan(?:\?|$)/.test(url);
    // Legacy bills GET materializes projections on first view; it is a mutation.
    const importsBills = /\/finance\/monthly-bills(?:\?|$)/.test(url) && response.config?.method === 'get';
      if (!isChatTransport && !isFinancialPreview && !isTrainingPreview && !isNutritionPreview && !isIntegratedPreview && (importsBills || !['get', 'head', 'options'].includes(response.config?.method || 'get'))) { invalidateUser(); window.dispatchEvent(new Event('sirius-data-changed')); }
    return response;
  },
  (error) => {
    if (!belongsToCurrentSession(error.config || error.response?.config)) return Promise.reject(sessionChangedError());
    if (OFFLINE_MODE) {
      const offlineError = new Error('Modo offline - dados locais');
      (offlineError).isOfflineError = true;
      return Promise.reject(offlineError);
    }
    if (error?.response?.status === 401) {
      clearToken();
      const path = window.location.pathname;
      if (path !== '/login' && path !== '/register' && path !== '/') {
        window.location.href = '/login';
      }
    }
    // Detect Gemini API key errors
    const errMsg = getApiErrorMessage(error, "");
    if (
      errMsg.includes("Configure sua chave") &&
      errMsg.includes("Gemini")
    ) {
      window.dispatchEvent(new CustomEvent("open-gemini-key-modal"));
    }
    if (errMsg.includes("cota da API Gemini esgotou") || errMsg.includes("chave de API Gemini é inválida")) {
      window.dispatchEvent(new CustomEvent("gemini-api-error", { detail: errMsg }));
    }
    return Promise.reject(error);
  }
);

export default axios;
