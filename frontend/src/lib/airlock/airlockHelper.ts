/**
 * AIRLOCK V3.1 HELPER
 * 
 * Global state for opening/closing the Airlock modal.
 * In a real app with state management (Redux/Zustand/etc.), this would live there.
 * For now, using a simple pub/sub pattern.
 */

/**
 * AIRLOCK V3.1 PROTOCOL CONTEXT
 * 
 * Passed from caller when opening the airlock
 */
export interface AirlockContext {
    actionType: string; // e.g., "SET_SYSTEM_MODE", "HALT_STRATEGIES", "GLOBAL_EMERGENCY_STOP"
    severity: 'MEDIUM' | 'HIGH' | 'CRITICAL';
    state_before: any;
    state_after: any;
    dependencies?: string[]; // Affected components
    entry_exit_plan?: {
        entry_conditions?: string[];
        exit_triggers?: string[];
        reversion_method?: string;
    };
    executor: () => Promise<{ request_id?: string; latency_ms?: number; status: number }>;
    fastPath?: boolean; // For risk-reducing actions (STOP, etc.), enables 0.5-1.0s hold
}

type AirlockListener = (context: AirlockContext | null) => void;

const listeners: Set<AirlockListener> = new Set();
let currentContext: AirlockContext | null = null;

export function subscribeToAirlock(listener: AirlockListener): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
}

export function openAirlock(context: AirlockContext): void {
    currentContext = context;
    listeners.forEach(listener => listener(context));
}

export function closeAirlock(): void {
    currentContext = null;
    listeners.forEach(listener => listener(null));
}

export function getCurrentAirlockContext(): AirlockContext | null {
    return currentContext;
}

/**
 * Example usage:
 * 
 * // In your component:
 * import { openAirlock } from '../../lib/airlock/airlockHelper';
 * import { setSystemMode } from '../../api/adapter';
 * 
 * const handleAutoClick = () => {
 *     openAirlock({
 *         actionType: 'SET_SYSTEM_MODE',
 *         severity: 'CRITICAL',
 *         state_before: { mode: 'MANUAL', auto_mode: false },
 *         state_after: { mode: 'AUTO', auto_mode: true },
 *         dependencies: ['RiskEngine', 'ExecutionGateway', 'AuditLog'],
 *         entry_exit_plan: {
 *             entry_conditions: ['All preflight checks PASS', 'Operator authenticated'],
 *             exit_triggers: ['Hard drift detected', 'Risk engine unavailable'],
 *             reversion_method: 'Auto-downgrade to MANUAL + position freeze'
 *         },
 *         executor: async () => {
 *             const result = await setSystemMode('AUTO', new AbortController().signal, client);
 *             return {
 *                 request_id: result.headers?.['x-request-id'],
 *                 latency_ms: 0, // populated by Airlock
 *                 status: 200
 *             };
 *         }
 *     });
 * };
 */
