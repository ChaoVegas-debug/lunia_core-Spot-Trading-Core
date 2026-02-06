/**
 * Integration Gate I.1 RECOVERY v2 — Bootstrap Controller
 * 
 * CRITICAL FIXES:
 * - REAL timeout: controller.abort() (NOT signal.dispatchEvent)
 * - WATCHDOG: force BACKEND_UNREACHABLE after 3.5s if still BOOTING
 * - Comprehensive logging: [BOOT] prefix for all transitions
 * - inflight cleanup in finally block (no stuck inflight)
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { BootstrapState, type BootstrapContext } from '../lib/bootstrapTypes';

const HEALTH_TIMEOUT_MS = 3000;
const WATCHDOG_TIMEOUT_MS = 3500; // Watchdog: force terminal state
const API_BASE = '/api'; // Uses Vite proxy

interface HealthResponse {
    status: string;
    [key: string]: any;
}

let globalRequestId = 0; // StrictMode-safe: track latest probe

/**
 * Probe /api/health with REAL timeout (controller.abort).
 */
async function probeHealth(requestId: number, controller: AbortController): Promise<{
    transportOk: boolean;     // true only if HTTP response received
    httpStatus?: number;      // actual HTTP status code
    parseOk?: boolean;        // true if JSON parse succeeded
    data?: HealthResponse;    // parsed JSON data (or {} if parse failed)
    error?: string;           // error message for transport failures
    requestId: number;        // StrictMode safety
}> {
    console.log(`[BOOT] probe start url=${API_BASE}/health requestId=${requestId}`);

    // REAL timeout: abort controller after timeout
    const timeoutId = setTimeout(() => {
        console.warn('[BOOT] timeout abort fired');
        controller.abort();
    }, HEALTH_TIMEOUT_MS);

    try {
        const res = await fetch(`${API_BASE}/health`, {
            signal: controller.signal,
            headers: { 'Accept': 'application/json' },
        });
        clearTimeout(timeoutId);

        // Safe JSON parsing
        let data: any = {};
        let parseOk = true;
        try {
            data = await res.json();
        } catch (jsonErr: any) {
            console.warn(`[BOOT] JSON parse failed: ${jsonErr.message}`);
            parseOk = false;
            // Keep default empty object, proceed with status code
        }

        console.log(`[BOOT] probe resolved httpStatus=${res.status} transportOk=true parseOk=${parseOk}`);
        // Return transportOk=true for all HTTP responses (even 5xx)
        // Status code mapping happens in performProbe()
        return { transportOk: true, httpStatus: res.status, parseOk, data, requestId };
    } catch (err: any) {
        clearTimeout(timeoutId);

        if (controller.signal.aborted || err.name === 'AbortError') {
            console.error('[BOOT] probe error name=AbortError message=timeout');
            return { transportOk: false, error: 'Health check timed out', requestId };
        }

        console.error(`[BOOT] probe error name=${err.name} message=${err.message}`);
        return { transportOk: false, error: err.message || 'Network error', requestId };
    }
}

export function useBootstrapController(): BootstrapContext {
    const [state, setState] = useState<BootstrapState>(BootstrapState.BOOTING);
    const [lastProbeTime, setLastProbeTime] = useState<string>();
    const [lastProbeStatus, setLastProbeStatus] = useState<number | 'timeout' | 'error'>();
    const [errorMessage, setErrorMessage] = useState<string>();
    const [governanceReason, setGovernanceReason] = useState<string>();
    const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);

    const inflightRef = useRef(false); // Prevent concurrent probes
    const startTimeRef = useRef<number>(Date.now());
    const elapsedIntervalRef = useRef<number | null>(null);
    const watchdogRef = useRef<number | null>(null); // WATCHDOG: force terminal state

    const performProbe = useCallback(async () => {
        if (inflightRef.current) {
            console.warn('[BOOT] probe already inflight, skipping');
            return;
        }

        inflightRef.current = true;
        const requestId = ++globalRequestId;
        console.log(`[BOOT] enter BOOTING requestId=${requestId}`);

        setState(BootstrapState.BOOTING);
        setLastProbeTime(new Date().toISOString());
        startTimeRef.current = Date.now();
        setElapsedSeconds(0);

        // Start elapsed time tracker (100ms updates)
        if (elapsedIntervalRef.current) clearInterval(elapsedIntervalRef.current);
        elapsedIntervalRef.current = setInterval(() => {
            setElapsedSeconds(Math.floor((Date.now() - startTimeRef.current) / 1000));
        }, 100);

        // WATCHDOG: force BACKEND_UNREACHABLE after WATCHDOG_TIMEOUT_MS if still BOOTING
        if (watchdogRef.current) clearTimeout(watchdogRef.current);
        watchdogRef.current = setTimeout(() => {
            console.error('[BOOT] WATCHDOG fired -> forcing BACKEND_UNREACHABLE');
            setState(BootstrapState.BACKEND_UNREACHABLE);
            setErrorMessage('BOOT_WATCHDOG_TIMEOUT: Bootstrap exceeded 3.5s');
            setLastProbeStatus('timeout');

            // Cleanup
            if (elapsedIntervalRef.current) {
                clearInterval(elapsedIntervalRef.current);
                elapsedIntervalRef.current = null;
            }
            inflightRef.current = false;
        }, WATCHDOG_TIMEOUT_MS);

        const controller = new AbortController();

        try {
            const result = await probeHealth(requestId, controller);

            // Clear watchdog on successful completion
            if (watchdogRef.current) {
                clearTimeout(watchdogRef.current);
                watchdogRef.current = null;
            }

            // StrictMode safety: only process if this is the latest request
            if (result.requestId !== globalRequestId) {
                console.warn(`[BOOT] stale probe result, ignoring requestId=${result.requestId} (current=${globalRequestId})`);
                return;
            }

            setLastProbeStatus(result.httpStatus ?? 'error');

            // ═══════════════════════════════════════════════════════════════
            // CRITICAL: HTTP/Network Semantics (I.1.1 Hotfix)
            // ═══════════════════════════════════════════════════════════════
            // Order: transportOk first, then 200 (with gov checks), then errors
            // AXIOM: FALSE READY IS GOVERNANCE FAILURE
            // ═══════════════════════════════════════════════════════════════

            // 0. Check transport layer FIRST (network/timeout/abort failures)
            if (!result.transportOk) {
                setErrorMessage(result.error || 'Network error');
                setState(BootstrapState.BACKEND_UNREACHABLE);
                console.error(`[BOOT] terminal -> BACKEND_UNREACHABLE (transport failed) error=${result.error}`);
                return;
            }

            // From this point: transportOk=true, we have HTTP response
            // httpStatus is guaranteed to be set

            // 1. Check HTTP 200 FIRST (only success case)
            if (result.httpStatus === 200) {
                // Even on 200, check for governance markers
                if (result.data?.veto_reason || result.data?.drift || result.data?.airlock) {
                    setGovernanceReason(
                        result.data.veto_reason ||
                        result.data.drift ||
                        result.data.airlock ||
                        'Governance block active'
                    );
                    setState(BootstrapState.GOVERNANCE_BLOCK);
                    console.warn('[BOOT] terminal -> GOVERNANCE_BLOCK (200 OK but governance markers present)');
                    return;
                }
                if (result.data?.stop_active || result.data?.global_stop) {
                    setGovernanceReason('Global STOP mode active');
                    setState(BootstrapState.GLOBAL_STOP);
                    console.warn('[BOOT] terminal -> GLOBAL_STOP (200 OK but stop flags present)');
                    return;
                }
                // All clear: READY
                console.log('[BOOT] terminal -> READY');
                setState(BootstrapState.READY);
                return;
            }

            // 2. Check 401 UNAUTHORIZED
            if (result.httpStatus === 401) {
                setGovernanceReason(result.data?.error || 'Authentication required');
                setState(BootstrapState.UNAUTHORIZED);
                console.warn(`[BOOT] terminal -> UNAUTHORIZED (HTTP 401)`);
                return;
            }

            // 3. Check 409 GLOBAL_STOP (or stop markers in data)
            if (result.httpStatus === 409 || result.data?.stop_active || result.data?.global_stop) {
                setGovernanceReason('Global STOP mode active');
                setState(BootstrapState.GLOBAL_STOP);
                console.warn(`[BOOT] terminal -> GLOBAL_STOP (HTTP ${result.httpStatus})`);
                return;
            }

            // 4. Check 403 FORBIDDEN/GOVERNANCE_BLOCK
            if (result.httpStatus === 403) {
                // Check if this is a governance block (veto/drift/airlock markers)
                if (result.data?.veto_reason || result.data?.drift || result.data?.airlock) {
                    setGovernanceReason(
                        result.data.veto_reason ||
                        result.data.drift ||
                        result.data.airlock ||
                        'Governance block active'
                    );
                    setState(BootstrapState.GOVERNANCE_BLOCK);
                    console.warn('[BOOT] terminal -> GOVERNANCE_BLOCK (HTTP 403 with governance markers)');
                } else {
                    setGovernanceReason(result.data?.error || 'Access forbidden');
                    setState(BootstrapState.FORBIDDEN);
                    console.warn('[BOOT] terminal -> FORBIDDEN (HTTP 403)');
                }
                return;
            }

            // 5. Check 5xx SERVER ERROR (CRITICAL: never READY on 5xx)
            if (result.httpStatus && result.httpStatus >= 500 && result.httpStatus < 600) {
                setErrorMessage(`Backend error (HTTP ${result.httpStatus})`);
                setState(BootstrapState.BACKEND_ERROR);
                console.error(`[BOOT] terminal -> BACKEND_ERROR (HTTP ${result.httpStatus})`);
                return;
            }

            // 6. Fail-safe: any other 4xx
            if (result.httpStatus && result.httpStatus >= 400 && result.httpStatus < 500) {
                setErrorMessage(`HTTP ${result.httpStatus}`);
                setState(BootstrapState.FORBIDDEN);
                console.warn(`[BOOT] terminal -> FORBIDDEN (HTTP ${result.httpStatus} - fail-safe)`);
                return;
            }

            // 7. Unexpected: got HTTP response but not categorized (2xx/3xx besides 200)
            setErrorMessage(`Unexpected HTTP ${result.httpStatus}`);
            setState(BootstrapState.BACKEND_UNREACHABLE);
            console.error(`[BOOT] terminal -> BACKEND_UNREACHABLE (unexpected HTTP ${result.httpStatus})`);

        } finally {
            // CRITICAL: cleanup in finally to ensure no stuck inflight
            if (elapsedIntervalRef.current) {
                clearInterval(elapsedIntervalRef.current);
                elapsedIntervalRef.current = null;
            }
            inflightRef.current = false;
        }
    }, []);

    const retry = useCallback(() => {
        console.log('[BOOT] retry requested');

        // Clear watchdog on retry
        if (watchdogRef.current) {
            clearTimeout(watchdogRef.current);
            watchdogRef.current = null;
        }

        performProbe();
    }, [performProbe]);

    // Initial probe on mount
    useEffect(() => {
        performProbe();

        // Cleanup on unmount
        return () => {
            if (elapsedIntervalRef.current) {
                clearInterval(elapsedIntervalRef.current);
            }
            if (watchdogRef.current) {
                clearTimeout(watchdogRef.current);
            }
        };
    }, [performProbe]);

    return {
        state,
        lastProbeTime,
        lastProbeStatus,
        backendUrl: API_BASE,
        errorMessage,
        governanceReason,
        retry,
        elapsedSeconds,
    };
}
