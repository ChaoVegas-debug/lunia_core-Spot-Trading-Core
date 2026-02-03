/**
 * @deprecated ARCHITECTURALLY BROKEN - DO NOT USE
 * 
 * ROOT CAUSE: Deterministic deadlock bug in interval/backoff interaction
 * - setInterval captures backoffRef.current at creation time
 * - When backoff increases on error, interval continues at old rate
 * - Result: interval and backoff desynchronize → permanent polling freeze
 * 
 * MIGRATION REQUIRED: Use usePoller.ts instead
 * 
 * Pattern:
 * BEFORE:
 *   const X = usePolledResource((signal) => apiCall(signal, client), 2000, [deps]);
 * 
 * AFTER:
 *   const { data: X, error: XError, refresh: XRefresh } = usePoller({
 *     key: 'unique_key',
 *     endpoint: '/api/actual/endpoint',
 *     fetcher: () => apiCall(new AbortController().signal, client),
 *     interval_ms: 2000,
 *     critical: true/false  // affects global AGE calculation
 *   });
 * 
 * See: /Users/neomind/.gemini/antigravity/brain/5a77fe4a-6cff-41cb-a2a5-c3b6f5064c42/implementation_plan.md
 * 
 * This hook is DISABLED. All usage will throw at runtime.
 */

import { useState, useCallback } from 'react';

interface ResourceState<T> {
  data?: T;
  error?: Error;
  loading: boolean;
  lastUpdated?: number;
  refresh: () => void;
}

export function usePolledResource<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  intervalMs: number,
  deps: unknown[] = []
): ResourceState<T> {
  // PHASE 2 KILL SWITCH: Fail fast on any usage
  throw new Error(
    `❌ usePolledResource is DEPRECATED and DISABLED.\n\n` +
    `ROOT CAUSE: Architectural deadlock bug (setInterval captures backoffRef → permanent freeze).\n\n` +
    `MIGRATION REQUIRED:\n` +
    `Use usePoller from '../../hooks/usePoller' instead.\n\n` +
    `Pattern:\n` +
    `  const { data, error, refresh } = usePoller({\n` +
    `    key: 'unique_key',\n` +
    `    endpoint: '/api/endpoint',\n` +
    `    fetcher: () => apiCall(new AbortController().signal, client),\n` +
    `    interval_ms: ${intervalMs},\n` +
    `    critical: false  // or true for ops_state/health\n` +
    `  });\n\n` +
    `See migration guide: implementation_plan.md in artifacts`
  );
}
