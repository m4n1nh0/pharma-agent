import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { authApi } from "@/api/endpoints";
import { getToken, setToken, setUnauthorizedHandler } from "@/api/client";
import type { UserResponse } from "@/api/types";

const USER_KEY = "pharma_user";

export interface AuthContextValue {
  user: UserResponse | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: { name: string; email: string; password: string; role: string; crm_crf?: string | null }) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function readStoredUser(): UserResponse | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as UserResponse) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(() => getToken());
  const [user, setUser] = useState<UserResponse | null>(() => readStoredUser());

  const persist = useCallback((tok: string, u: UserResponse) => {
    setToken(tok);
    localStorage.setItem(USER_KEY, JSON.stringify(u));
    setTokenState(tok);
    setUser(u);
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    localStorage.removeItem(USER_KEY);
    setTokenState(null);
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
  }, [logout]);

  const login = useCallback(
    async (email: string, password: string) => {
      const data = await authApi.login({ email, password });
      persist(data.access_token, data.user);
    },
    [persist]
  );

  const register = useCallback(
    async (data: { name: string; email: string; password: string; role: string; crm_crf?: string | null }) => {
      const res = await authApi.register({ ...data, role: data.role as UserResponse["role"] });
      persist(res.access_token, res.user);
    },
    [persist]
  );

  const value = useMemo<AuthContextValue>(
    () => ({ user, token, isAuthenticated: !!token, login, register, logout }),
    [user, token, login, register, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth deve ser usado dentro de <AuthProvider>");
  return ctx;
}
