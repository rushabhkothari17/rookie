import axios from "axios";
import { getViewAsTenantHeader } from "@/components/TenantSwitcher";

const API_BASE = `${process.env.REACT_APP_BACKEND_URL}/api`;

const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true, // Enable sending/receiving HttpOnly cookies
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("aa_token");
  const viewAsHeaders = getViewAsTenantHeader();
  
  // Set headers - include Authorization if token exists (for backward compatibility)
  config.headers = {
    ...(config.headers || {}),
    ...viewAsHeaders,
  } as any;
  
  if (token) {
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
