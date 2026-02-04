/**
 * PULSE STORE — IN-MEMORY FRESHNESS REGISTRY
 * 
 * Phase F3.1: Truth of Freshness
 * 
 * Tracks data freshness across critical pollers to compute GLOBAL DATA AGE.
 * 
 * Features:
 * - In-memory registry (NO React dependency)
 * - Per-source tracking: endpoint, meta, critical flag, update reason
 * - Reason tracking: NETWORK (fetch failed) | TAB_HIDDEN (paused) | UNKNOWN
 * - Consumed by useGlobalDataAge for max age computation with root-cause
 * 
 * Critical sources (minimum):
 * - ops → /api/ops/state
 * - balances → /api/balances
 * - signals → /api/signals/active
 */

import type { ProvenanceMeta } from './provenance';

export type PulseReason = 'NETWORK' | 'TAB_HIDDEN' | 'UNKNOWN';

export interface PulseSource {
    endpoint: string;
    meta: ProvenanceMeta | null;
    critical: boolean;
    last_update_reason?: PulseReason;
    reason_detail?: string; // e.g., "502 Bad Gateway", "NonJsonResponseError HTML page"
}

class PulseRegistry {
    private sources: Map<string, PulseSource> = new Map();

    /**
     * Register a data source for freshness tracking
     */
    registerSource(key: string, endpoint: string, critical: boolean = false): void {
        if (!this.sources.has(key)) {
            this.sources.set(key, {
                endpoint,
                meta: null,
                critical,
                last_update_reason: 'UNKNOWN',
            });
        }
    }

    /**
     * Update metadata for a source (called by pollers on each cycle)
     */
    updateMeta(key: string, meta: ProvenanceMeta): void {
        const source = this.sources.get(key);
        if (source) {
            source.meta = meta;
            // If update succeeded, clear stale reasons (assume fresh unless setReason called)
            if (!source.last_update_reason || source.last_update_reason === 'UNKNOWN') {
                source.last_update_reason = 'UNKNOWN';
                source.reason_detail = undefined;
            }
        }
    }

    /**
     * Set reason why data is stale/paused
     */
    setReason(key: string, reason: PulseReason, detail?: string): void {
        const source = this.sources.get(key);
        if (source) {
            source.last_update_reason = reason;
            source.reason_detail = detail;
        }
    }

    /**
     * Get snapshot of all registered sources
     */
    getSnapshot(): Record<string, PulseSource> {
        const snapshot: Record<string, PulseSource> = {};
        this.sources.forEach((source, key) => {
            snapshot[key] = { ...source };
        });
        return snapshot;
    }

    /**
     * Get specific source
     */
    getSource(key: string): PulseSource | undefined {
        return this.sources.get(key);
    }

    /**
     * Clear all sources (for testing)
     */
    clear(): void {
        this.sources.clear();
    }
}

// Singleton instance
export const pulseStore = new PulseRegistry();

// PHASE 5B: DEBUG INSPECTOR (Dev-only heartbeat certification)
// @ts-ignore - vite env vars exist at runtime
if (typeof window !== 'undefined' && import.meta.env?.VITE_DEBUG_POLL === '1') {
    setInterval(() => {
        const snapshot = pulseStore.getSnapshot();
        const critical = Object.entries(snapshot).filter(([, s]) => s.critical);

        console.group('[PULSE STORE] Critical Sources Snapshot (10s interval)');
        critical.forEach(([key, source]) => {
            const age_s = source.meta?.age_s ?? 999;
            const last_ok_ts = source.meta?.last_success_ts ?? 0;
            const status = age_s > 10 ? '🔴 STALE' : '🟢 FRESH';
            console.log(`${status} ${key}:`, {
                endpoint: source.endpoint,
                age_s,
                last_ok_ts: last_ok_ts ? new Date(last_ok_ts).toISOString().substr(11, 8) : 'NEVER',
                reason: source.last_update_reason,
                detail: source.reason_detail
            });
        });
        console.groupEnd();
    }, 10000);
}
