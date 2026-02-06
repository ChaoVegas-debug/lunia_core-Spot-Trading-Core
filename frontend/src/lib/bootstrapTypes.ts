/**
 * Integration Gate I.1 — Bootstrap State Types
 * 
 * Canonical state machine for application bootstrap.
 */

export enum BootstrapState {
    BOOTING = 'BOOTING',
    READY = 'READY',
    BACKEND_UNREACHABLE = 'BACKEND_UNREACHABLE',
    BACKEND_ERROR = 'BACKEND_ERROR',
    UNAUTHORIZED = 'UNAUTHORIZED',
    FORBIDDEN = 'FORBIDDEN',
    GLOBAL_STOP = 'GLOBAL_STOP',
    GOVERNANCE_BLOCK = 'GOVERNANCE_BLOCK',
}

export interface BootstrapContext {
    state: BootstrapState;
    lastProbeTime?: string;
    lastProbeStatus?: number | 'timeout' | 'error';
    backendUrl: string;
    errorMessage?: string;
    governanceReason?: string; // veto_reason, drift, airlock
    retry: () => void;
    elapsedSeconds?: number; // HARDENED: Visible progress during BOOTING
}
