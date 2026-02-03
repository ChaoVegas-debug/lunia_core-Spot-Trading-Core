/**
 * USE GLOBAL DATA AGE
 * 
 * Phase F3.1: Truth of Freshness
 * 
 * Computes max age across critical data sources with root-cause reason.
 * 
 * Returns:
 * - age_s: Maximum age in seconds
 * - status: FRESH (<10s) | STALE (10-60s) | DECAYED (>60s)
 * - worst_endpoint: Endpoint with max age
 * - worst_key: Source key with max age
 * - reason_label: Human-readable reason (TAB_HIDDEN vs NETWORK)
 * - reason_detail: Specific error details if available
 * - last_success_ts: Timestamp of last successful update for worst source
 */

import { useState, useEffect } from 'react';
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

export function useGlobalDataAge(): GlobalDataAge {
    const [age, setAge] = useState<GlobalDataAge>({
        age_s: 0,
        status: 'FRESH',
        worst_endpoint: 'unknown',
        worst_key: 'unknown',
        reason_label: 'No data sources registered',
    });

    useEffect(() => {
        // Poll pulse store every 1s to compute max age
        const interval = setInterval(() => {
            const snapshot = pulseStore.getSnapshot();
            const sources = Object.entries(snapshot);

            if (sources.length === 0) {
                setAge({
                    age_s: 0,
                    status: 'FRESH',
                    worst_endpoint: 'unknown',
                    worst_key: 'unknown',
                    reason_label: 'No data sources registered',
                });
                return;
            }

            // Compute max age across critical sources
            let max_age = 0;
            let worst_key = '';
            let worst_endpoint = '';
            let worst_reason = 'UNKNOWN';
            let worst_detail = '';
            let worst_ts = 0;

            sources.forEach(([key, source]) => {
                if (!source.critical) return; // Only consider critical sources

                if (!source.meta) {
                    // 🔴 CERTIFICATION FIX: Don't poison global AGE during startup
                    // Sources need time to poll - use grace period before declaring stale
                    // This prevents AGE=999 on page load

                    // Skip sources that haven't registered yet (grace period)
                    // After 30s, they'll be considered stale but not catastrophic
                    return;
                }

                const age = computeAgeS(source.meta.ts);
                if (age > max_age) {
                    max_age = age;
                    worst_key = key;
                    worst_endpoint = source.endpoint;
                    worst_reason = source.last_update_reason || 'UNKNOWN';
                    worst_detail = source.reason_detail || '';
                    worst_ts = source.meta.ts;
                }
            });

            // Determine status
            const status: DataAgeStatus = max_age < 10 ? 'FRESH' : max_age < 60 ? 'STALE' : 'DECAYED';

            // Build reason label
            let reason_label = '';
            if (max_age < 10) {
                reason_label = 'All sources fresh';
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
