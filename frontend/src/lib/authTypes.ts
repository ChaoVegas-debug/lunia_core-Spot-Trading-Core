/**
 * Integration Gate I.2 — Auth Types
 * 
 * Auth state enum and context for auth controller.
 * Parallel to bootstrapTypes.ts but for session/identity resolution.
 */

export enum AuthState {
    AUTH_BOOTING = 'AUTH_BOOTING',                 // Initial auth probe
    AUTH_READY = 'AUTH_READY',                     // Valid session, user identified
    AUTH_UNAUTHORIZED = 'AUTH_UNAUTHORIZED',       // 401 or no valid session
    AUTH_FORBIDDEN = 'AUTH_FORBIDDEN',             // 403 insufficient role/tier
    AUTH_ERROR_TRANSPORT = 'AUTH_ERROR_TRANSPORT', // Network/timeout failure
    AUTH_ERROR_SERVER = 'AUTH_ERROR_SERVER',       // 5xx backend error
}

export interface AuthControllerContext {
    state: AuthState;
    role?: string;
    user?: any; // UserProfile from existing types
    errorMessage?: string;
    lastProbeTime?: string;
    lastProbeStatus?: number | string;
    elapsedSeconds?: number;
    retry: () => void;
}
