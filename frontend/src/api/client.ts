import { APIError } from './errors';
import type { ApiResponse, ErrorEnvelope, Role } from './types';

const DEFAULT_API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080';

export interface ClientOptions {
  adminToken?: string;
  opsToken?: string;
  bearerToken?: string;
  role?: Role;
  tenantId?: string | null;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit & { signal?: AbortSignal } = {},
  clientOptions?: ClientOptions
): Promise<T> {
  const url = path.startsWith('http') ? path : `${DEFAULT_API_BASE}${path}`;
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> | undefined)
  };

  if (clientOptions?.tenantId) {
    headers['X-Tenant-Id'] = clientOptions.tenantId;
  }

  if (clientOptions?.adminToken) {
    headers['X-Admin-Token'] = clientOptions.adminToken;
    headers['X-OPS-TOKEN'] = clientOptions.opsToken || clientOptions.adminToken;
  } else if (clientOptions?.opsToken) {
    headers['X-OPS-TOKEN'] = clientOptions.opsToken;
  }

  if (clientOptions?.bearerToken) {
    headers.Authorization = `Bearer ${clientOptions.bearerToken}`;
  }

  const response = await fetch(url, {
    ...options,
    headers,
    signal: options.signal
  });

  const contentType = response.headers.get('content-type');
  const isJson = contentType?.includes('application/json');
  const payload: ApiResponse<T> | ErrorEnvelope | undefined = isJson
    ? await response.json().catch(() => undefined)
    : undefined;

  if (!response.ok) {
    const message = (payload as ErrorEnvelope | undefined)?.error || response.statusText;
    throw new APIError(typeof message === 'string' ? message : JSON.stringify(message), response.status, payload);
  }

  return isJson ? ((payload as ApiResponse<T>) ?? ({} as ApiResponse<T>)).data || (payload as T) : (undefined as unknown as T);
}

export function apiBaseUrl(): string {
  return DEFAULT_API_BASE;
}
