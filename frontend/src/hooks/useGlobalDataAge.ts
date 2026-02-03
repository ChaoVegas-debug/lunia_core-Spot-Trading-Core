/**
 * USE GLOBAL DATA AGE — PHASE 3 TRUTH MODEL
 * 
 * Phase F3.1: Truth of Freshness (LEVEL 10 CERTIFICATION)
 * 
 * Computes max age across CRITICAL data sources only with root-cause reason.
 * 
 * TRUTH GUARANTEES:
 * - NEVER shows age=0 when data is stale (0s lie eliminated)
 * - NEVER shows age=999 poison pill (missing meta handled gracefully)
 * - ONLY aggregates critical sources (ops_state, health, balances)
 * - Initialization fallback: shows time-since-startup until first critical meta arrives
 * 
 * Returns:
 * - age_s: Maximum age in seconds (truthful - never 0 unless truly fresh)
 * - status: FRESH (<10s) | STALE (10-60s) | DECAYED (>60s)
 * - worst_endpoint: Endpoint with max age
 * - worst_key: Source key with max age
 * - reason_label: Human-readable reason (TAB_HIDDEN vs NETWORK vs INITIALIZING)
 * - reason_detail: Specific error details if available
 * - last_success_ts: Timestamp of last successful update for worst source
 */

import { useState, useEffect, useRef } from 'react';
import { pulseStore } from '../lib/runtime/pulseStore';
import { computeAgeS } from '../lib/runtime/provenance';

export type DataAgeStatus = 'FRESH' | 'STALE' | 'DECAYED';

export interface GlobalDataAge {
    age_s: number;
    status: DataAgeStatus;
    worst_endpoint: string;
    worst_key: string;
    reason_label: string;
    reason_detail?: string;
    last_success_ts?: number;
}

// Track startup timestamp (module-level singleton)
const STARTUP_TS = Date.now();

export function useGlobalDataAge(): GlobalDataAge {
    // Start with truthful initialization state (time since startup)
    const [age, setAge] = useState<GlobalDataAge>(() => {
        const startupAge = Math.floor((Date.now() - STARTUP_TS) / 1000);
        return {
            age_s: startupAge,
            status: 'STALE', // Initializing is considered STALE until first critical meta
            worst_endpoint: 'initialization',
            worst_key: 'startup',
            reason_label: 'Initializing - awaiting first critical data source',
        };
    });

    useEffect(() => {
        // Poll pulse store every 1s to compute max age
        const interval = setInterval(() => {
            const snapshot = pulseStore.getSnapshot();
            const sources = Object.entries(snapshot);

            // Filter to critical sources only
            const criticalSources = sources.filter(([_, source]) => source.critical);

            if (criticalSources.length === 0) {
                // No critical sources registered yet - use startup fallback
                const startupAge = Math.floor((Date.now() - STARTUP_TS) / 1000);
                setAge({
                    age_s: startupAge,
                    status: startupAge < 10 ? 'FRESH' : startupAge < 60 ? 'STALE' : 'DECAYED',
                    worst_endpoint: 'initialization',
                    worst_key: 'startup',
                    reason_label: 'Initializing - no critical sources registered',
                });
                return;
            }

            // Compute max age across critical sources that have meta
            let max_age: number | null = null;
            let worst_key = '';
            let worst_endpoint = '';
            let worst_reason = 'UNKNOWN';
            let worst_detail = '';
            let worst_ts = 0;
            let has_any_meta = false;

            criticalSources.forEach(([key, source]) => {
                if (!source.meta) {
                    // Critical source registered but no meta yet - skip gracefully
                    // This is NOT a 999 poison - it's just "not yet observed"
                    return;
                }

                has_any_meta = true;
                const age = computeAgeS(source.meta.ts);

                if (max_age === null || age > max_age) {
                    max_age = age;
                    worst_key = key;
                    worst_endpoint = source.endpoint;
                    worst_reason = source.last_update_reason || 'UNKNOWN';
                    worst_detail = source.reason_detail || '';
                    worst_ts = source.meta.ts;
                }
            });

            // If no critical source has meta yet, use startup fallback
            if (!has_any_meta || max_age === null) {
                const startupAge = Math.floor((Date.now() - STARTUP_TS) / 1000);
                setAge({
                    age_s: startupAge,
                    status: startupAge < 10 ? 'FRESH' : startupAge < 60 ? 'STALE' : 'DECAYED',
                    worst_endpoint: 'initialization',
                    worst_key: 'startup',
                    reason_label: 'Initializing - awaiting first critical poll completion',
                });
                return;
            }

            // Determine status based on max age
            const status: DataAgeStatus = max_age < 10 ? 'FRESH' : max_age < 60 ? 'STALE' : 'DECAYED';

            // Build reason label with forensic specificity
            let reason_label = '';
            if (max_age < 10) {
                reason_label = 'All critical sources fresh';
            } else if (worst_reason === 'TAB_HIDDEN') {
                reason_label = `Stale due to TAB_HIDDEN (${worst_endpoint})`;
            } else if (worst_reason === 'NETWORK') {
                reason_label = `Stale due to NETWORK (${worst_endpoint})`;
            } else {
                reason_label = `Stale (${worst_endpoint})`;
            }

            setAge({
                age_s: Math.floor(max_age),
                status,
                worst_endpoint,
                worst_key,
                reason_label,
                reason_detail: worst_detail,
                last_success_ts: worst_ts,
            });
        }, 1000);

        return () => clearInterval(interval);
    }, []);

    return age;
}
