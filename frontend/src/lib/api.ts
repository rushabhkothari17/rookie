import axios, { AxiosError } from "axios";
import { getViewAsTenantHeader } from "@/components/TenantSwitcher";

const API_BASE = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Track if we're currently refreshing to prevent multiple refresh calls
let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

const subscribeTokenRefresh = (cb: (token: string) => void) => {
  refreshSubscribers.push(cb);
};

const onTokenRefreshed = (token: string) => {
  refreshSubscribers.forEach((cb) => cb(token));
  refreshSubscribers = [];
};

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

// Response interceptor for token refresh
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as any;
    
    // Don't retry if it's already a retry, or if it's the refresh endpoint, or logout
    if (
      originalRequest?._retry ||
      originalRequest?.url?.includes('/auth/refresh') ||
      originalRequest?.url?.includes('/auth/logout') ||
      originalRequest?.url?.includes('/auth/login')
    ) {
      return Promise.reject(error);
    }
    
    // Only handle 401 errors (token expired)
    if (error.response?.status === 401 && error.response?.data) {
      const errorMessage = (error.response.data as any)?.detail || '';
      
      // Check if it's a token expiry issue (not invalid credentials)
      if (errorMessage.includes('expired') || errorMessage === 'Not authenticated') {
        if (!isRefreshing) {
          isRefreshing = true;
          
          try {
            // Try to refresh the token
            const refreshResponse = await axios.post(
              `${API_BASE}/auth/refresh`,
              {},
              { withCredentials: true }
            );
            
            const newToken = refreshResponse.data.token;
            if (newToken) {
              localStorage.setItem("aa_token", newToken);
              onTokenRefreshed(newToken);
            }
            
            isRefreshing = false;
            
            // Retry the original request
            originalRequest._retry = true;
            if (newToken) {
              originalRequest.headers.Authorization = `Bearer ${newToken}`;
            }
            return api(originalRequest);
          } catch (refreshError) {
            isRefreshing = false;
            // Refresh failed - user needs to login again
            localStorage.removeItem("aa_token");
            // Don't redirect here - let the AuthContext handle it
            return Promise.reject(error);
          }
        } else {
          // Wait for the refresh to complete
          return new Promise((resolve) => {
            subscribeTokenRefresh((token: string) => {
              originalRequest._retry = true;
              originalRequest.headers.Authorization = `Bearer ${token}`;
              resolve(api(originalRequest));
            });
          });
        }
      }
    }
    
    return Promise.reject(error);
  }
);

export const setAuthToken = (token?: string) => {
  if (token) {
    localStorage.setItem("aa_token", token);
  } else {
    localStorage.removeItem("aa_token");
  }
};

export default api;
