import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { getBranding } from '../api/endpoints';
import type { BrandingConfig } from '../api/types';
import { useAuth } from './useAuth';

const defaultBrand: BrandingConfig = {
  brand_name: import.meta.env.VITE_BRAND_NAME || 'Lunia Console',
  logo_url: import.meta.env.VITE_BRAND_LOGO || undefined,
  support_email: import.meta.env.VITE_BRAND_SUPPORT || undefined,
  primary_color: import.meta.env.VITE_BRAND_PRIMARY_COLOR || undefined,
  tenant_id: import.meta.env.VITE_TENANT_ID || undefined,
  environment: import.meta.env.MODE
};

interface BrandingState {
  branding: BrandingConfig;
  loading: boolean;
  error?: Error;
  lastUpdated?: number;
}

const BrandingContext = createContext<BrandingState | undefined>(undefined);

export const BrandingProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const auth = useAuth();
  const [branding, setBranding] = useState<BrandingConfig>(defaultBrand);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | undefined>(undefined);
  const [lastUpdated, setLastUpdated] = useState<number | undefined>(undefined);

  useEffect(() => {
    const controller = new AbortController();
    const run = async () => {
      setLoading(true);
      try {
        const resp = await getBranding(controller.signal, {
          bearerToken: auth.bearerToken,
          adminToken: auth.adminToken,
          opsToken: auth.opsToken,
          role: auth.role,
          tenantId: auth.tenantId
        });
        setBranding(resp);
        document.title = resp.brand_name;
        setLastUpdated(Date.now());
      } catch (err) {
        setError(err as Error);
        document.title = defaultBrand.brand_name;
      } finally {
        setLoading(false);
      }
    };
    run();
    return () => controller.abort();
  }, [auth.adminToken, auth.opsToken, auth.bearerToken, auth.role, auth.tenantId]);

  const value = useMemo(() => ({ branding, loading, error, lastUpdated }), [branding, loading, error, lastUpdated]);

  return <BrandingContext.Provider value={value}>{children}</BrandingContext.Provider>;
};

export const useBranding = (): BrandingState => {
  const ctx = useContext(BrandingContext);
  if (!ctx) {
    throw new Error('useBranding must be used inside BrandingProvider');
  }
  return ctx;
};
