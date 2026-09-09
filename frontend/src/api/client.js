import axios from "axios";

/**
 * Axios API client for communicating with the FastAPI backend.
 *
 * In development, Vite proxies /api requests to http://localhost:8000.
 * The JWT token is automatically attached from localStorage.
 */
const API = axios.create({
  baseURL: "/api",
  headers: {
    "Content-Type": "application/json",
  },
});

// ── Request interceptor: attach JWT token ──
API.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("nawi_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// ── Response interceptor: handle 401 (expired/invalid token) ──
API.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      localStorage.removeItem("nawi_token");
      localStorage.removeItem("nawi_user");
    }
    return Promise.reject(error);
  }
);

export default API;
