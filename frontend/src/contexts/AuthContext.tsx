import React, { createContext, useContext, useEffect, useState } from "react";
import api, { setAuthToken } from "@/lib/api";

type AuthUser = {
  id: string;
  email: string;
  full_name: string;
  company_name: string;
  phone: string;
  is_verified: boolean;
  is_admin: boolean;
};

type AuthContextType = {
  user: AuthUser | null;
  customer: any;
  address: any;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  register: (payload: any) => Promise<any>;
  verifyEmail: (email: string, code: string) => Promise<void>;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [customer, setCustomer] = useState<any>(null);
  const [address, setAddress] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    try {
      const response = await api.get("/me");
      setUser(response.data.user);
      setCustomer(response.data.customer);
      setAddress(response.data.address);
    } catch (error) {
      setUser(null);
      setCustomer(null);
      setAddress(null);
    } finally {
      setLoading(false);
    }
  };

  const login = async (email: string, password: string) => {
    const response = await api.post("/auth/login", { email, password });
    setAuthToken(response.data.token);
    await refresh();
  };

  const logout = () => {
    setAuthToken(undefined);
    setUser(null);
    setCustomer(null);
    setAddress(null);
  };

  const register = async (payload: any) => {
    const response = await api.post("/auth/register", payload);
    return response.data;
  };

  const verifyEmail = async (email: string, code: string) => {
    await api.post("/auth/verify-email", { email, code });
  };

  useEffect(() => {
    const token = localStorage.getItem("aa_token");
    if (token) {
      setAuthToken(token);
      refresh();
    } else {
      setLoading(false);
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        customer,
        address,
        loading,
        login,
        logout,
        register,
        verifyEmail,
        refresh,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
};
