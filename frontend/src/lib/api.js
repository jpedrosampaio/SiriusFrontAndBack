import axios from "axios";
import { OFFLINE_MODE, OFFLINE_USER, OFFLINE_DEMO_DATA } from "./offline-mode";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';
const API = `${BACKEND_URL}/api`;

// Re-export for convenience
export { OFFLINE_MODE };

// Session token management via localStorage
const TOKEN_KEY = "sirius_session_token";

export const isOfflineMode = () => OFFLINE_MODE;

export const getToken = () => {
  if (OFFLINE_MODE) return 'offline_token';
  return localStorage.getItem(TOKEN_KEY);
};
export const setToken = (token) => {
  if (!OFFLINE_MODE) localStorage.setItem(TOKEN_KEY, token);
};
export const clearToken = () => {
  if (!OFFLINE_MODE) localStorage.removeItem(TOKEN_KEY);
};

export const getOfflineUser = () => OFFLINE_USER;
export const getOfflineData = () => OFFLINE_DEMO_DATA;

// Set up global axios interceptor to add Authorization header
axios.interceptors.request.use(
  (config) => {
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
  (response) => response,
  (error) => {
    if (OFFLINE_MODE) {
      const offlineError = new Error('Modo offline - dados locais');
      (offlineError).isOfflineError = true;
      return Promise.reject(offlineError);
    }
    if (error.response?.status === 401) {
      clearToken();
      const path = window.location.pathname;
      if (path !== '/login' && path !== '/register' && path !== '/') {
        window.location.href = '/login';
      }
    }
    // Detect missing Gemini API key errors and trigger modal
    const errMsg = error.response?.data?.detail || "";
    if (
      errMsg.includes("Configure sua chave") &&
      errMsg.includes("Gemini")
    ) {
      window.dispatchEvent(new CustomEvent("open-gemini-key-modal"));
    }
    return Promise.reject(error);
  }
);

export default axios;
