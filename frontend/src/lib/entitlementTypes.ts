/**
 * Integration Gate I.3 — Entitlement Types
 * 
 * Entitlement state enum and context for subscription/tier validation.
 * Parallel to bootstrapTypes.ts and authTypes.ts but for tier/plan enforcement.
 */

export enum EntitlementState {
    ENT_BOOTING = 'ENT_BOOTING',                   // Initial tier validation
    ENT_READY = 'ENT_READY',                       // Valid tier, plan loaded
    ENT_FORBIDDEN = 'ENT_FORBIDDEN',               // 403 or auth-level block
    ENT_EXPIRED = 'ENT_EXPIRED',                   // Subscription expired (future)
    ENT_MALFORMED = 'ENT_MALFORMED',               // Tier field invalid/missing
    ENT_ERROR_TRANSPORT = 'ENT_ERROR_TRANSPORT',   // Network/timeout failure
    ENT_ERROR_SERVER = 'ENT_ERROR_SERVER',         // 5xx backend error
}

export interface EntitlementControllerContext {
    state: EntitlementState;
    tier?: string;
    plan?: any; // SubscriptionPlan from domain/subscription/plans
    errorMessage?: string;
    lastProbeTime?: string;
    lastProbeStatus?: number | string;
    elapsedSeconds?: number;
    retry: () => void;
}
