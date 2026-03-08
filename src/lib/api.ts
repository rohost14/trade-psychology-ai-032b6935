import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const AUTH_TOKEN_KEY = 'tradementor_auth_token';

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

// Request interceptor: attach JWT Bearer token if available
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(AUTH_TOKEN_KEY);
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: detect auth failures and provide better error info
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const { status, data } = error.response;

      if (status === 401) {
        // Token expired or invalid - dispatch a custom event so BrokerContext can react
        window.dispatchEvent(new CustomEvent('tradementor:token-expired', {
          detail: { message: data?.detail || 'Authentication failed' }
        }));
      }

      // Log with context for debugging
      console.error(`API Error [${status}]:`, data?.detail || data?.message || error.message);
    } else if (error.code === 'ECONNABORTED') {
      console.error('API timeout:', error.message);
    } else {
      console.error('API network error:', error.message);
    }

    return Promise.reject(error);
  }
);

export default api;
