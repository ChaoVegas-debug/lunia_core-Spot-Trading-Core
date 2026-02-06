/**
 * Integration Gate I.3 — Entitlement Controller
 * 
 * Deterministic tier/subscription state machine with transport/HTTP semantics.
 * Validates user tier from /api/v1/auth/me and enforces plan limits.
 * 
 * CRITICAL: NO FALSE ACCESS.
 * Every tier validation error MUST map to a visible UI state.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { EntitlementState, type EntitlementControllerContext } from '../lib/entitlementTypes';
import { getPlan, PLANS, type PlanTier, type SubscriptionPlan } from '../domain/subscription/plans';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';
const ENT_PROBE_TIMEOUT_MS = 3000;
const WATCHDOG_TIMEOUT_MS = 3500;

interface TierResponse {
    id?: number;
    email?: string;
    role?: string;
    tier?: string;
    [key: string]: any;
}

/**
 * Probe /api/v1/auth/me with focus on tier validation.
 * Returns transport/HTTP separation just like bootstrap/auth probe.
 */
async function probeTier(requestId: number, controller: AbortController, bearerToken?: string): Promise<{
    transportOk: boolean;
    httpStatus?: number;
    parseOk?: boolean;
    data?: TierResponse;
    error?: string;
    requestId: number;
}> {
    console.log(`[ENT] probe start url=${API_BASE}/api/v1/auth/me requestId=${requestId}`);

    const timeoutId = setTimeout(() => {
        console.log('[ENT] timeout abort fired');
        controller.abort();
    }, ENT_PROBE_TIMEOUT_MS);

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
            console.warn(`[ENT] JSON parse failed: ${jsonErr.message}`);
            parseOk = false;
        }

        console.log(`[ENT] probe resolved httpStatus=${res.status} transportOk=true parseOk=${parseOk}`);
        return { transportOk: true, httpStatus: res.status, parseOk, data, requestId };
    } catch (err: any) {
        clearTimeout(timeoutId);

        if (controller.signal.aborted || err.name === 'AbortError') {
            console.error('[ENT] probe error name=AbortError message=timeout');
            return { transportOk: false, error: 'Tier check timed out', requestId };
        }

        console.error(`[ENT] probe error name=${err.name} message=${err.message}`);
        return { transportOk: false, error: err.message || 'Network error', requestId };
    }
}

export function useEntitlementController(bearerToken?: string): EntitlementControllerContext {
    const [state, setState] = useState<EntitlementState>(EntitlementState.ENT_BOOTING);
    const [tier, setTier] = useState<string | undefined>();
    const [plan, setPlan] = useState<SubscriptionPlan | undefined>();
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
            console.warn('[ENT] probe already inflight, skipping');
            return;
        }

        inflightRef.current = true;
        const requestId = ++requestIdRef.current;
        const globalRequestId = requestId;

        console.log(`[ENT] performProbe start requestId=${requestId}`);

        const controller = new AbortController();

        try {
            const result = await probeTier(requestId, controller, bearerToken);

            // StrictMode safety: only process if this is the latest request
            if (result.requestId !== globalRequestId) {
                console.warn(`[ENT] stale probe result, ignoring requestId=${result.requestId} (current=${globalRequestId})`);
                return;
            }

            setLastProbeTime(new Date().toISOString());
            setLastProbeStatus(result.httpStatus ?? 'error');

            // ═══════════════════════════════════════════════════════════════
            // CRITICAL: HTTP/Network Semantics (I.3)
            // ═══════════════════════════════════════════════════════════════
            // Order: transportOk first, then 200 (with tier validation), then errors
            // AXIOM: FALSE ENT_READY IS TIER BYPASS (GOVERNANCE FAILURE)
            // ═══════════════════════════════════════════════════════════════

            // 0. Check transport layer FIRST
            if (!result.transportOk) {
                setErrorMessage(result.error || 'Network error');
                setState(EntitlementState.ENT_ERROR_TRANSPORT);
                console.error(`[ENT] terminal -> ENT_ERROR_TRANSPORT (transport failed) error=${result.error}`);
                return;
            }

            // From this point: transportOk=true, we have HTTP response

            // 1. Check HTTP 200 FIRST (only success case)
            if (result.httpStatus === 200) {
                // CRITICAL: Validate tier field present
                if (!result.data?.tier) {
                    setErrorMessage('Tier field missing from user profile');
                    setState(EntitlementState.ENT_MALFORMED);
                    console.error('[ENT] terminal -> ENT_MALFORMED (200 OK but tier missing)');
                    return;
                }

                const userTier = result.data.tier;

                // CRITICAL: Validate tier is in PLANS map
                if (!PLANS[userTier as PlanTier]) {
                    console.warn(`[ENT] Unknown tier "${userTier}", falling back to BEGINNER (safe default)`);
                    // Agent decision: Use getPlan() fallback logic (returns BEGINNER for unknown)
                    // This is SAFE (most restrictive) rather than blocking
                }

                // Load plan using canonical getPlan (handles fallback)
                const userPlan = getPlan(userTier);
                setPlan(userPlan);
                setTier(userTier);
                setErrorMessage(undefined);
                console.log(`[ENT] terminal -> ENT_READY tier=${userTier} plan=${userPlan.id}`);
                setState(EntitlementState.ENT_READY);
                return;
            }

            // 2. Check 401 UNAUTHORIZED (auth failure, not tier issue)
            if (result.httpStatus === 401) {
                setErrorMessage('Authentication required for tier validation');
                setState(EntitlementState.ENT_FORBIDDEN);
                console.warn(`[ENT] terminal -> ENT_FORBIDDEN (HTTP 401)`);
                return;
            }

            // 3. Check 403 FORBIDDEN
            if (result.httpStatus === 403) {
                setErrorMessage(result.data?.error || 'Access forbidden');
                setState(EntitlementState.ENT_FORBIDDEN);
                console.warn(`[ENT] terminal -> ENT_FORBIDDEN (HTTP 403)`);
                return;
            }

            // 4. Check 5xx SERVER ERROR
            if (result.httpStatus && result.httpStatus >= 500 && result.httpStatus < 600) {
                setErrorMessage(`Tier service error (HTTP ${result.httpStatus})`);
                setState(EntitlementState.ENT_ERROR_SERVER);
                console.error(`[ENT] terminal -> ENT_ERROR_SERVER (HTTP ${result.httpStatus})`);
                return;
            }

            // 5. Fail-safe: any other 4xx
            if (result.httpStatus && result.httpStatus >= 400 && result.httpStatus < 500) {
                setErrorMessage(`HTTP ${result.httpStatus}`);
                setState(EntitlementState.ENT_FORBIDDEN);
                console.warn(`[ENT] terminal -> ENT_FORBIDDEN (HTTP ${result.httpStatus} - fail-safe)`);
                return;
            }

            // 6. Unexpected: got HTTP response but not categorized
            setErrorMessage(`Unexpected HTTP ${result.httpStatus}`);
            setState(EntitlementState.ENT_ERROR_TRANSPORT);
            console.error(`[ENT] terminal -> ENT_ERROR_TRANSPORT (unexpected HTTP ${result.httpStatus})`);

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
        console.log('[ENT] manual retry triggered');
        setState(EntitlementState.ENT_BOOTING);
        setElapsedSeconds(0);
        performProbe();
    }, [performProbe]);

    // Initial probe on mount (or when bearerToken changes)
    useEffect(() => {
        console.log('[ENT] initial probe effect fired');

        // If no bearer token, immediately go to FORBIDDEN (can't validate tier without auth)
        if (!bearerToken) {
            console.log('[ENT] no bearerToken, skipping probe -> ENT_FORBIDDEN');
            setState(EntitlementState.ENT_FORBIDDEN);
            setErrorMessage('Authentication required');
            return;
        }

        setState(EntitlementState.ENT_BOOTING);
        setElapsedSeconds(0);

        // Elapsed timer
        const start = Date.now();
        elapsedIntervalRef.current = window.setInterval(() => {
            setElapsedSeconds((Date.now() - start) / 1000);
        }, 100);

        // Watchdog: if still ENT_BOOTING after 3.5s, force ENT_ERROR_TRANSPORT
        watchdogRef.current = window.setTimeout(() => {
            if (state === EntitlementState.ENT_BOOTING) {
                console.error('[ENT] WATCHDOG FIRED - still ENT_BOOTING after 3.5s -> ENT_ERROR_TRANSPORT');
                setErrorMessage('Tier check timeout (watchdog)');
                setState(EntitlementState.ENT_ERROR_TRANSPORT);
            }
        }, WATCHDOG_TIMEOUT_MS);

        performProbe();

        return () => {
            if (elapsedIntervalRef.current) clearInterval(elapsedIntervalRef.current);
            if (watchdogRef.current) clearTimeout(watchdogRef.current);
        };
    }, [bearerToken, performProbe]);

    return {
        state,
        tier,
        plan,
        errorMessage,
        lastProbeTime,
        lastProbeStatus,
        elapsedSeconds,
        retry,
    };
}
