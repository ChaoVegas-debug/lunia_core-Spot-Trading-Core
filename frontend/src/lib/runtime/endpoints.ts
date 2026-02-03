/**
 * ENDPOINT REGISTRY
 * 
 * UI Constitution LAW F — Wiring Discipline & Endpoint Canonicalization
 * 
 * Single source of truth for all API endpoints.
 * All widgets MUST reference endpoints via this registry (no inline strings).
 * 
 * Endpoint Status:
 * - LIVE: Endpoint exists and returns JSON
 * - MOCKED: Endpoint 404/missing, widget uses MOCK PROTOCOL (amber badge, meta.source='sim')
 * - ERROR: Endpoint exists but returns non-JSON (FailClosed overlay with diagnostics)
 */

export const endpoints = {
    // Ops & System
    ops_state: '/ops/state',
    ops_incidents: '/ops/incidents',

    // Capital & Execution
    balances: '/balances',
    positions: '/positions',
    orders_active: '/orders/active',
    pnl_history: '/pnl/history',

    // Risk & Intel
    signals_active: '/signals/active',
    risk_limits: '/risk/limits',
    risk_drift: '/risk/drift',

    // Strategy & Allocation
    strategies: '/strategies',
    allocations: '/allocations',
} as const;

/**
 * Known Issues & Endpoint Notes
 * 
 * Track backend contract mismatches for reference.
 */
export const endpointNotes = {
    signals_active: 'Currently returns HTML instead of JSON - FailClosed overlay will show NonJsonResponseError diagnostics',
} as const;

/**
 * Type helper for endpoint keys
 */
export type EndpointKey = keyof typeof endpoints;
