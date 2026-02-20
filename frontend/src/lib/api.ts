import axios from "axios";

const API_BASE = `${process.env.REACT_APP_BACKEND_URL}/api`;

const api = axios.create({
  baseURL: API_BASE,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("aa_token");
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const setAuthToken = (token?: string) => {
  if (token) {
    localStorage.setItem("aa_token", token);
  } else {
    localStorage.removeItem("aa_token");
  }
};

export default api;
