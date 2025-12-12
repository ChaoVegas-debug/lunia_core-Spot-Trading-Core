import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { getCurrentUser, postLogin } from '../api/endpoints';
import type { Role, UserProfile } from '../api/types';

interface AuthState {
  role: Role;
  adminToken?: string;
  opsToken?: string;
  bearerToken?: string;
  user?: UserProfile;
  expiresAt?: string;
}

interface AuthContextValue extends AuthState {
  setAuth: (next: AuthState | ((prev: AuthState) => AuthState)) => void;
  logout: () => void;
  login: (email: string, password: string) => Promise<void>;
}

const defaultRole = (import.meta.env.VITE_DEFAULT_ROLE as Role | undefined) || 'USER';
const AUTH_STORAGE_KEY = 'lunia-auth-state';

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const [auth, setAuthState] = useState<AuthState>(() => {
    const stored = localStorage.getItem(AUTH_STORAGE_KEY);
    if (stored) {
      try {
        return JSON.parse(stored) as AuthState;
      } catch (err) {
        console.warn('Failed to parse auth state', err);
      }
    }
    return { role: defaultRole };
  });

  useEffect(() => {
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(auth));
  }, [auth]);

  useEffect(() => {
    const refresh = async () => {
      if (!auth.bearerToken) return;
      try {
        const user = await getCurrentUser(new AbortController().signal, { bearerToken: auth.bearerToken, role: auth.role });
        setAuthState((prev) => ({ ...prev, user, role: user.role }));
      } catch (err) {
        console.warn('Failed to refresh auth state', err);
      }
    };
    refresh();
  }, [auth.bearerToken, auth.role]);

  const login = async (email: string, password: string) => {
    const controller = new AbortController();
    const resp = await postLogin({ email, password }, controller.signal);
    let userProfile: UserProfile | undefined;
    try {
      userProfile = await getCurrentUser(new AbortController().signal, { bearerToken: resp.access_token, role: resp.role });
    } catch (err) {
      console.warn('Failed to fetch /auth/me after login', err);
    }
    setAuthState((prev) => ({
      ...prev,
      bearerToken: resp.access_token,
      role: resp.role,
      user: userProfile ?? { id: resp.user_id, email, role: resp.role, is_active: true, created_at: '', last_login_at: resp.expires_at },
      expiresAt: resp.expires_at
    }));
  };

  const value = useMemo<AuthContextValue>(() => ({
    ...auth,
    setAuth: setAuthState,
    logout: () => setAuthState({ role: defaultRole }),
    login
  }), [auth]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = (): AuthContextValue => {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return ctx;
};

export const hasControlAccess = (role: Role): boolean => role === 'TRADER' || role === 'ADMIN';
export const isAdmin = (role: Role): boolean => role === 'ADMIN';
export type { Role };
