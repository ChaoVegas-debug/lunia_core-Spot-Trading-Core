/**
 * Integration Gate I.2 — Auth Controller
 * 
 * Deterministic auth state machine with transport/HTTP semantics.
 * Parallel to useBootstrapController but for session/identity resolution.
 * 
 * CRITICAL: NO SILENT AUTH FAILURES.
 * Every auth error MUST map to a visible UI state.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { AuthState, type AuthControllerContext } from '../lib/authTypes';
import type { UserProfile } from '../api/types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';
const AUTH_PROBE_TIMEOUT_MS = 3000;
const WATCHDOG_TIMEOUT_MS = 3500;

interface HealthResponse {
    id?: number;
    email?: string;
    role?: string;
    tier?: string;
    [key: string]: any;
}

/**
 * Probe /api/v1/auth/me with REAL timeout (controller.abort).
 * Returns transport/HTTP separation just like bootstrap probe.
 */
async function probeAuth(requestId: number, controller: AbortController, bearerToken?: string): Promise<{
    transportOk: boolean;     // true only if HTTP response received
    httpStatus?: number;      // actual HTTP status code
    parseOk?: boolean;        // true if JSON parse succeeded
    data?: HealthResponse;    // parsed JSON data (or {} if parse failed)
    error?: string;           // error message for transport failures
    requestId: number;        // StrictMode safety
}> {
    console.log(`[AUTH] probe start url=${API_BASE}/api/v1/auth/me requestId=${requestId}`);

    const timeoutId = setTimeout(() => {
        console.log('[AUTH] timeout abort fired');
        controller.abort();
    }, AUTH_PROBE_TIMEOUT_MS);

    try {
        const headers: Record<string, string> = { 'Accept': 'application/json' };
        if (bearerToken) {
            headers['Authorization'] = `Bearer ${bearerToken}`;
        }

        const res = await fetch(`${API_BASE}/api/v1/auth/me`, {
            signal: controller.signal,
            headers,
        });
        clearTimeout(timeoutId);

        // Safe JSON parsing
        let data: any = {};
        let parseOk = true;
        try {
            data = await res.json();
        } catch (jsonErr: any) {
            console.warn(`[AUTH] JSON parse failed: ${jsonErr.message}`);
            parseOk = false;
            // Keep default empty object, proceed with status code
        }

        console.log(`[AUTH] probe resolved httpStatus=${res.status} transportOk=true parseOk=${parseOk}`);
        // Return transportOk=true for all HTTP responses (even 5xx)
        // Status code mapping happens in performProbe()
        return { transportOk: true, httpStatus: res.status, parseOk, data, requestId };
    } catch (err: any) {
        clearTimeout(timeoutId);

        if (controller.signal.aborted || err.name === 'AbortError') {
            console.error('[AUTH] probe error name=AbortError message=timeout');
            return { transportOk: false, error: 'Auth check timed out', requestId };
        }

        console.error(`[AUTH] probe error name=${err.name} message=${err.message}`);
        return { transportOk: false, error: err.message || 'Network error', requestId };
    }
}

export function useAuthController(bearerToken?: string): AuthControllerContext {
    const [state, setState] = useState<AuthState>(AuthState.AUTH_BOOTING);
    const [user, setUser] = useState<UserProfile | undefined>();
    const [role, setRole] = useState<string | undefined>();
    const [errorMessage, setErrorMessage] = useState<string | undefined>();
    const [lastProbeTime, setLastProbeTime] = useState<string>('');
    const [lastProbeStatus, setLastProbeStatus] = useState<number | string>('');
    const [elapsedSeconds, setElapsedSeconds] = useState(0);

    const inflightRef = useRef(false);
    const requestIdRef = useRef(0);
    const elapsedIntervalRef = useRef<number>();
    const watchdogRef = useRef<number>();

    const performProbe = useCallback(async () => {
        // StrictMode guard + duplicate prevention
        if (inflightRef.current) {
            console.warn('[AUTH] probe already inflight, skipping');
            return;
        }

        inflightRef.current = true;
        const requestId = ++requestIdRef.current;
        const globalRequestId = requestId; // capture for closure

        console.log(`[AUTH] performProbe start requestId=${requestId}`);

        const controller = new AbortController();

        try {
            const result = await probeAuth(requestId, controller, bearerToken);

            // StrictMode safety: only process if this is the latest request
            if (result.requestId !== globalRequestId) {
                console.warn(`[AUTH] stale probe result, ignoring requestId=${result.requestId} (current=${globalRequestId})`);
                return;
            }

            setLastProbeTime(new Date().toISOString());
            setLastProbeStatus(result.httpStatus ?? 'error');

            // ═══════════════════════════════════════════════════════════════
            // CRITICAL: HTTP/Network Semantics (I.2)
            // ═══════════════════════════════════════════════════════════════
            // Order: transportOk first, then 200 (with user data), then errors
            // AXIOM: FALSE AUTH_READY IS GOVERNANCE FAILURE
            // ═══════════════════════════════════════════════════════════════

            // 0. Check transport layer FIRST (network/timeout/abort failures)
            if (!result.transportOk) {
                setErrorMessage(result.error || 'Network error');
                setState(AuthState.AUTH_ERROR_TRANSPORT);
                console.error(`[AUTH] terminal -> AUTH_ERROR_TRANSPORT (transport failed) error=${result.error}`);
                return;
            }

            // From this point: transportOk=true, we have HTTP response
            // httpStatus is guaranteed to be set

            // 1. Check HTTP 200 FIRST (only success case)
            if (result.httpStatus === 200) {
                // Validate we have user data
                if (!result.data?.id || !result.data?.role) {
                    setErrorMessage('Invalid user data in response');
                    setState(AuthState.AUTH_ERROR_SERVER);
                    console.error('[AUTH] terminal -> AUTH_ERROR_SERVER (200 OK but missing user data)');
                    return;
                }

                // All clear: AUTH_READY
                setUser(result.data as UserProfile);
                setRole(result.data.role);
                setErrorMessage(undefined);
                console.log('[AUTH] terminal -> AUTH_READY');
                setState(AuthState.AUTH_READY);
                return;
            }

            // 2. Check 401 UNAUTHORIZED
            if (result.httpStatus === 401) {
                setErrorMessage(result.data?.error || 'Authentication required');
                setState(AuthState.AUTH_UNAUTHORIZED);
                console.warn(`[AUTH] terminal -> AUTH_UNAUTHORIZED (HTTP 401)`);
                return;
            }

            // 3. Check 403 FORBIDDEN (insufficient role/tier)
            if (result.httpStatus === 403) {
                setErrorMessage(result.data?.error || 'Access forbidden');
                setState(AuthState.AUTH_FORBIDDEN);
                console.warn(`[AUTH] terminal -> AUTH_FORBIDDEN (HTTP 403)`);
                return;
            }

            // 4. Check 5xx SERVER ERROR (CRITICAL: never AUTH_READY on 5xx)
            if (result.httpStatus && result.httpStatus >= 500 && result.httpStatus < 600) {
                setErrorMessage(`Auth server error (HTTP ${result.httpStatus})`);
                setState(AuthState.AUTH_ERROR_SERVER);
                console.error(`[AUTH] terminal -> AUTH_ERROR_SERVER (HTTP ${result.httpStatus})`);
                return;
            }

            // 5. Fail-safe: any other 4xx
            if (result.httpStatus && result.httpStatus >= 400 && result.httpStatus < 500) {
                setErrorMessage(`HTTP ${result.httpStatus}`);
                setState(AuthState.AUTH_UNAUTHORIZED);
                console.warn(`[AUTH] terminal -> AUTH_UNAUTHORIZED (HTTP ${result.httpStatus} - fail-safe)`);
                return;
            }

            // 6. Unexpected: got HTTP response but not categorized (2xx/3xx besides 200)
            setErrorMessage(`Unexpected HTTP ${result.httpStatus}`);
            setState(AuthState.AUTH_ERROR_TRANSPORT);
            console.error(`[AUTH] terminal -> AUTH_ERROR_TRANSPORT (unexpected HTTP ${result.httpStatus})`);

        } finally {
            // CRITICAL: cleanup in finally to ensure no stuck inflight
            if (elapsedIntervalRef.current) {
                clearInterval(elapsedIntervalRef.current);
                elapsedIntervalRef.current = undefined;
            }
            if (watchdogRef.current) {
                clearTimeout(watchdogRef.current);
                watchdogRef.current = undefined;
            }
            inflightRef.current = false;
        }
    }, [bearerToken]);

    const retry = useCallback(() => {
        console.log('[AUTH] manual retry triggered');
        setState(AuthState.AUTH_BOOTING);
        setElapsedSeconds(0);
        performProbe();
    }, [performProbe]);

    // Initial probe on mount (or when bearerToken changes)
    useEffect(() => {
        console.log('[AUTH] initial probe effect fired');

        // If no bearer token, immediately go to UNAUTHORIZED (no point probing)
        if (!bearerToken) {
            console.log('[AUTH] no bearerToken, skipping probe -> AUTH_UNAUTHORIZED');
            setState(AuthState.AUTH_UNAUTHORIZED);
            return;
        }

        setState(AuthState.AUTH_BOOTING);
        setElapsedSeconds(0);

        // Elapsed timer
        const start = Date.now();
        elapsedIntervalRef.current = window.setInterval(() => {
            setElapsedSeconds((Date.now() - start) / 1000);
        }, 100);

        // Watchdog: if still AUTH_BOOTING after 3.5s, force AUTH_ERROR_TRANSPORT
        watchdogRef.current = window.setTimeout(() => {
            if (state === AuthState.AUTH_BOOTING) {
                console.error('[AUTH] WATCHDOG FIRED - still AUTH_BOOTING after 3.5s -> AUTH_ERROR_TRANSPORT');
                setErrorMessage('Auth check timeout (watchdog)');
                setState(AuthState.AUTH_ERROR_TRANSPORT);
            }
        }, WATCHDOG_TIMEOUT_MS);

        performProbe();

        return () => {
            if (elapsedIntervalRef.current) clearInterval(elapsedIntervalRef.current);
            if (watchdogRef.current) clearTimeout(watchdogRef.current);
        };
    }, [bearerToken, performProbe]); // Depend on bearerToken so it re-probes when token changes

    return {
        state,
        role,
        user,
        errorMessage,
        lastProbeTime,
        lastProbeStatus,
        elapsedSeconds,
        retry,
    };
}
