/**
 * USE POLLER - INSTITUTIONAL POLLING HOOK
 * 
 * Implements UI Constitution standards for data polling:
 * - LAW 3: Fail-closed (maintains lastGood snapshot)
 * - LAW 4: Provenance tracking (req_id, latency, age, source)
 * - LAW 5: Stale data awareness (10s threshold)
 * - Dead Man's Switch compliance (pause when hidden, force refresh on visible)
 * 
 * This hook replaces usePolledResource with institutional-grade polling.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import type { ProvenanceMeta } from '../lib/runtime/provenance';
import { computeAgeS } from '../lib/runtime/provenance';
import { pulseStore } from '../lib/runtime/pulseStore';

export interface UsePollerOptions<T> {
    /** Cache key for this poller (used for deduplication) */
    key: string;

    /** API endpoint (for provenance display) */
    endpoint: string;

    /** Data fetcher function (should use normalizeResponse wrapper) */
    fetcher: () => Promise<T>;

    /** Polling interval in milliseconds */
    interval_ms: number;

    /** Stale threshold in seconds (default: 10) */
    stale_threshold_s?: number;

    /** Pause polling when tab/window hidden (default: true) */
    pause_when_hidden?: boolean;

    /** Force refresh on tab/window visible (default: true) */
    force_refresh_on_focus?: boolean;

    /** Register as critical source in pulse store (for global data age) */
    critical?: boolean;
}

export interface UsePollerReturn<T> {
    /** Current data (null if never loaded) */
    data: T | null;

    /** Current error (null if no error) */
    error: Error | null;

    /** Provenance metadata */
    meta: ProvenanceMeta;

    /** Is data stale (age > threshold) */
    isStale: boolean;

    /** Last good snapshot (for fail-closed display) */
    lastGood: { data: T; meta: ProvenanceMeta } | null;

    /** Manually trigger refresh */
    refresh: () => Promise<void>;
}

export function usePoller<T>({
    key,
    endpoint,
    fetcher,
    interval_ms,
    stale_threshold_s = 10,
    pause_when_hidden = true,
    force_refresh_on_focus = true,
    critical = false,
}: UsePollerOptions<T>): UsePollerReturn<T> {
    // Register in pulse store (Phase F3.1)
    useEffect(() => {
        pulseStore.registerSource(key, endpoint, critical);
    }, [key, endpoint, critical]);
    const [data, setData] = useState<T | null>(null);
    const [error, setError] = useState<Error | null>(null);
    const [meta, setMeta] = useState<ProvenanceMeta>({
        ts: Date.now(),
        age_s: 0,
        source: 'unknown',
        endpoint,
    });
    const [lastGood, setLastGood] = useState<{ data: T; meta: ProvenanceMeta } | null>(null);

    const inFlightRef = useRef(false);
    const intervalRef = useRef<number | null>(null);
    const isMountedRef = useRef(true);

    // PHASE 1 FORENSICS: Debug flag for production certification
    const DEBUG = import.meta.env.VITE_DEBUG_POLL === '1';

    const refresh = useCallback(async () => {
        // CERTIFICATION CHECK: Log tick start
        if (DEBUG) {
            console.log(`[POLLER] TICK_START`, {
                endpoint,
                paused: pause_when_hidden && document.hidden,
                hidden: document.hidden,
                key
            });
        }

        // SKIP-IF-BUSY: Prevent overlapping requests (CRITICAL FIX for request storm)
        if (inFlightRef.current) {
            if (DEBUG) {
                console.log(`[POLLER] IN_FLIGHT (SKIP)`, { endpoint, inFlightRef: inFlightRef.current });
            }
            return;
        }

        inFlightRef.current = true;
        if (DEBUG) {
            console.log(`[POLLER] IN_FLIGHT (START)`, { endpoint, inFlightRef: inFlightRef.current });
        }

        const startTime = Date.now();

        try {
            const result = await fetcher();
            const latency_ms = Date.now() - startTime;

            if (!isMountedRef.current) {
                if (DEBUG) {
                    console.log(`[POLLER] UNMOUNTED (IGNORE)`, { endpoint });
                }
                return;
            }

            const newMeta: ProvenanceMeta = {
                req_id: (result as any)?.meta?.request_id || (result as any)?.request_id,
                latency_ms,
                ts: Date.now(),
                age_s: 0,
                source: 'network',
                http_status: 200,
                endpoint,
                last_success_ts: Date.now(),
            };

            if (DEBUG) {
                const bytes = JSON.stringify(result).length;
                console.log(`[POLLER] SUCCESS`, {
                    endpoint,
                    bytes,
                    latency_ms,
                    ts: newMeta.ts,
                    req_id: newMeta.req_id
                });
            }

            setData(result);
            setError(null);
            setMeta(newMeta);
            setLastGood({ data: result, meta: newMeta });

            // Update pulse store (Phase F3.1)
            pulseStore.updateMeta(key, newMeta);

        } catch (err: any) {
            const latency_ms = Date.now() - startTime;

            if (!isMountedRef.current) {
                if (DEBUG) {
                    console.log(`[POLLER] UNMOUNTED (IGNORE ERROR)`, { endpoint });
                }
                return;
            }

            // CERTIFICATION CHECK: Log abort vs real error
            if (err.name === 'AbortError') {
                if (DEBUG) {
                    console.log(`[POLLER] ABORT`, {
                        endpoint,
                        signal_aborted: true,
                        latency_ms
                    });
                }
                // CRITICAL: Silent abort, don't poison state
                return;
            }

            if (DEBUG) {
                console.error(`[POLLER] ERROR`, {
                    endpoint,
                    error_name: err.name,
                    error_message: err.message,
                    http_status: err.http_status,
                    latency_ms
                });
            }

            const newMeta: ProvenanceMeta = {
                latency_ms,
                ts: Date.now(),
                age_s: 0,
                source: 'network',
                http_status: err.http_status || 0,
                content_type: err.content_type,
                endpoint,
                last_success_ts: lastGood?.meta.ts,
            };

            setError(err);
            setMeta(newMeta);
            // Don't clear data on error - maintain fail-closed snapshot

            // Set reason in pulse store (Phase F3.1)
            const errorType = err.constructor?.name || 'Error';
            const detail = `${err.http_status || 'Network'} ${errorType}${err.hint ? ' (' + err.hint + ')' : ''}`;
            pulseStore.setReason(key, 'NETWORK', detail);
            pulseStore.updateMeta(key, newMeta);
        } finally {
            // 🔴 CERTIFICATION GATE: inFlightRef MUST be reset in finally
            inFlightRef.current = false;
            if (DEBUG) {
                console.log(`[POLLER] FINALLY`, { endpoint, inFlightRef: inFlightRef.current });
            }
        }
    }, [fetcher, endpoint, lastGood, key]);

    // Update age every second
    useEffect(() => {
        const ageInterval = setInterval(() => {
            setMeta(prev => ({
                ...prev,
                age_s: computeAgeS(prev.ts),
            }));
        }, 1000);

        return () => clearInterval(ageInterval);
    }, []);

    // Polling interval
    useEffect(() => {
        if (pause_when_hidden && document.hidden) {
            // Don't start interval when hidden
            // Set reason to TAB_HIDDEN (Phase F3.1)
            pulseStore.setReason(key, 'TAB_HIDDEN', 'Polling paused due to tab hidden');
            return;
        }

        // Initial fetch
        refresh();

        // Start interval
        intervalRef.current = setInterval(refresh, interval_ms);

        return () => {
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
                intervalRef.current = null;
            }
        };
    }, [refresh, interval_ms, pause_when_hidden]);

    // Visibility change handler
    useEffect(() => {
        if (!pause_when_hidden && !force_refresh_on_focus) {
            return;
        }

        const handleVisibilityChange = () => {
            if (!document.hidden) {
                // Tab became visible
                if (force_refresh_on_focus) {
                    refresh(); // Force immediate refresh
                }

                // Restart interval if paused
                if (pause_when_hidden && !intervalRef.current) {
                    intervalRef.current = setInterval(refresh, interval_ms);
                }
            } else {
                // Tab became hidden
                if (pause_when_hidden && intervalRef.current) {
                    clearInterval(intervalRef.current);
                    intervalRef.current = null;
                    // Set reason to TAB_HIDDEN (Phase F3.1)
                    pulseStore.setReason(key, 'TAB_HIDDEN', 'Polling paused due to tab hidden');
                }
            }
        };

        document.addEventListener('visibilitychange', handleVisibilityChange);

        return () => {
            document.removeEventListener('visibilitychange', handleVisibilityChange);
        };
    }, [refresh, interval_ms, pause_when_hidden, force_refresh_on_focus]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            isMountedRef.current = false;
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
            }
        };
    }, []);

    const isStale = meta.age_s > stale_threshold_s;

    return {
        data,
        error,
        meta,
        isStale,
        lastGood,
        refresh,
    };
}
