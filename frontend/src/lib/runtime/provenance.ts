/**
 * PROVENANCE RUNTIME
 * 
 * Institutional-grade provenance tracking for all live data surfaces.
 * Implements UI Constitution LAW 4 (Golden Thread) and LAW 10 (Provenance Contracts).
 * 
 * Every widget displaying live data MUST use ProvenanceMeta to expose:
 * - Request ID (traceability)
 * - Latency (performance monitoring)
 * - Age (stale data detection)
 * - Source (network vs cache vs sim)
 * - HTTP status + content-type (diagnostics)
 */

export type DataSource = 'network' | 'cache' | 'sim' | 'unknown';

export interface ProvenanceMeta {
    /** Request ID from backend (8-char display, full UUID internally) */
    req_id?: string;

    /** Round-trip latency in milliseconds (client-measured if server doesn't provide) */
    latency_ms?: number;

    /** Timestamp when data was finalized (Date.now()) */
    ts: number;

    /** Computed age in seconds (now - ts) */
    age_s: number;

    /** Data source */
    source: DataSource;

    /** HTTP status code (if network request) */
    http_status?: number;

    /** Response Content-Type (for diagnostics) */
    content_type?: string;

    /** API endpoint (short form for display) */
    endpoint?: string;

    /** Last successful fetch timestamp (for fail-closed lastGood display) */
    last_success_ts?: number;
}

/**
 * Compute age in seconds from timestamp
 */
export function computeAgeS(ts: number): number {
    return Math.floor((Date.now() - ts) / 1000);
}

/**
 * Format request ID for compact display (first 4 + last 4 chars)
 * e.g., "550e8400-e29b-41d4-a716-446655440000" → "550e...40000"
 */
export function formatReqId(req_id: string | undefined): string {
    if (!req_id) return 'n/a';
    if (req_id.length <= 8) return req_id;
    return `${req_id.slice(0, 4)}...${req_id.slice(-4)}`;
}

/**
 * Format provenance metadata for footer display
 * Output: "REQ: ab12...cd34 | LAT: 42ms | AGE: 3s | TS: 12:34:56 | SRC: network"
 */
export function formatProvenance(meta: ProvenanceMeta): string {
    const req = formatReqId(meta.req_id);
    const lat = meta.latency_ms !== undefined ? `${meta.latency_ms}ms` : 'n/a';
    const age = `${meta.age_s}s`;
    const ts = new Date(meta.ts).toLocaleTimeString();
    const src = meta.source;

    return `REQ: ${req} | LAT: ${lat} | AGE: ${age} | TS: ${ts} | SRC: ${src}`;
}

/**
 * Normalize endpoint URL for compact display
 * e.g., "http://localhost:3000/api/v1/balances?foo=bar" → "/api/v1/balances"
 */
export function normalizeEndpoint(url: string): string {
    try {
        const parsed = new URL(url, window.location.origin);
        return parsed.pathname;
    } catch {
        // If URL parsing fails, extract path manually
        const match = url.match(/\/api\/[^?#]*/);
        return match ? match[0] : url;
    }
}

/**
 * Check if data is stale based on threshold
 * Default threshold: 10 seconds (UI Constitution standard)
 */
export function isStale(meta: ProvenanceMeta, threshold_s: number = 10): boolean {
    return meta.age_s > threshold_s;
}

/**
 * Get status dot indicator based on error and staleness
 * 🟢 Live (< 10s, no error)
 * ⚪ Stale (> 10s, no error)
 * 🔴 Error
 */
export function getStatusDot(error: Error | null, meta: ProvenanceMeta, threshold_s: number = 10): string {
    if (error) return '🔴';
    return isStale(meta, threshold_s) ? '⚪' : '🟢';
}
