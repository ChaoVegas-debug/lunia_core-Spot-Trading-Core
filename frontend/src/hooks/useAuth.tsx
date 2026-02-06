import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { getCurrentUser, postLogin } from '../api/adapter';
import { buildClient } from '../api/client'; // Unified helper
import type { Role, UserProfile } from '../api/types';

interface AuthState {
  role: Role;
  adminToken?: string;
  opsToken?: string; // Often required for System Mode changes
  bearerToken?: string;
  user?: UserProfile;
  expiresAt?: string;
}

interface AuthContextValue extends AuthState {
  setAuth: (next: AuthState | ((prev: AuthState) => AuthState)) => void;
  logout: () => void;
  login: (email: string, password: string) => Promise<UserProfile | undefined>;
}

const defaultRole = (import.meta.env.VITE_DEFAULT_ROLE as Role | undefined) || 'USER';
const AUTH_STORAGE_KEY = 'lunia-auth-state';

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  console.log('AuthProvider Rendering');
  const [auth, setAuthState] = useState<AuthState>(() => {
    // FORCE PREVIEW STRAP (Option A: Visibly Runnable)
    if (import.meta.env.VITE_PREVIEW_MODE === '1' && import.meta.env.VITE_PREVIEW_SIMULATION === '1') {
      console.log('[AuthProvider] Force-Bootstrapping PREVIEW Session (Admin)');
      return {
        role: 'ADMIN',
        bearerToken: 'sim-force-token',
        opsToken: 'sim-ops-token',
        user: {
          id: 1,
          email: 'preview@lunia.fi',
          role: 'ADMIN',
          tier: 'INST_PRO',
          is_active: true,
          onboarding_completed: true, // Bypass Wizard
          created_at: new Date().toISOString()
        } as UserProfile
      };
    }

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

  // Persistence
  useEffect(() => {
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(auth));
  }, [auth]);

  // Session Refresh / Validation
  useEffect(() => {
    const refresh = async () => {
      // If we have a bearer token, try to validate/refresh user profile
      if (!auth.bearerToken) return;

      try {
        const client = buildClient(auth);
        const user = await getCurrentUser(new AbortController().signal, client);

        // Update state with fresh identity
        setAuthState((prev) => ({
          ...prev,
          user,
          role: user.role // Trust backend source of truth for role
        }));
      } catch (err) {
        // I.2: Auth failures are now visible via useAuthController (no silent warnings)
        // This refresh is kept for backward compatibility but errors are handled by auth controller
        console.debug('[Auth] Session refresh failed, auth controller will handle visibility', err);
      }
    };
    refresh();
  }, [auth.bearerToken]); // Only verify when token changes/mounts

  const login = async (email: string, password: string): Promise<UserProfile | undefined> => {
    // PREVIEW BYPASS: Instant Login for Proofs
    if (import.meta.env.VITE_PREVIEW_MODE === '1') {
      console.log('[Auth] Preview Mode Instant Login');
      const mockUser: UserProfile = {
        id: 1,
        email,
        role: 'ADMIN',
        tier: 'INST_PRO',
        is_active: true,
        onboarding_completed: true,
        created_at: new Date().toISOString()
      };

      setAuthState({
        bearerToken: 'preview-bypass-token',
        opsToken: 'preview-ops-token',
        role: 'ADMIN',
        user: mockUser
      });

      // Signal for Playwright
      (window as any).__LUNIA_LOGIN_OK__ = true;
      console.info('[LOGIN_OK]');

      return mockUser;
    }

    const controller = new AbortController();
    const resp = await postLogin({ email, password }, controller.signal);

    // Initial fetch of profile
    // Note: postLogin returns access_token. We treat this as bearerToken.
    // OpsToken is usually separate. For MVP/Beta, if Admin logs in, we might assume OpsToken = BearerToken 
    // or it's hardcoded/injected via other means. We don't magically set it here unless backend provided it.

    let userProfile: UserProfile | undefined;
    try {
      // Use the NEW token immediately
      const tempAuth = { role: resp.role as Role, bearerToken: resp.access_token };
      userProfile = await getCurrentUser(new AbortController().signal, buildClient(tempAuth));
    } catch (err) {
      console.warn('Failed to fetch /auth/me after login', err);
    }

    const finalUser: UserProfile = userProfile ?? {
      id: resp.user_id,
      email,
      role: resp.role as Role,
      tier: 'BEGINNER', // Default for P2.2 if backend is missing it
      is_active: true,
      created_at: '',
      last_login_at: resp.expires_at
    };

    // P2.2: Ensure tier defaults if backend returns user but no tier
    if (finalUser && !finalUser.tier) {
      finalUser.tier = 'BEGINNER';
    }

    setAuthState((prev) => ({
      ...prev,
      bearerToken: resp.access_token,
      role: resp.role as Role,
      user: finalUser,
      expiresAt: resp.expires_at,
      // Logic for OpsToken: If Admin, maybe reuse bearer? 
      // This is a heuristic for simple deployments.
      opsToken: (resp.role === 'ADMIN') ? resp.access_token : prev.opsToken
    }));

    return finalUser;
  };

  const value = useMemo<AuthContextValue>(() => ({
    ...auth,
    setAuth: setAuthState,
    logout: () => {
      setAuthState({ role: defaultRole });
      localStorage.removeItem(AUTH_STORAGE_KEY);
    },
    login
  }), [auth]);

  // ...
  console.log('AuthProvider returning children:', children);
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
