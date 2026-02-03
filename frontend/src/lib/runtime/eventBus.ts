/**
 * RUNTIME EVENT BUS
 * 
 * Phase F3: Centralized event stream for institutional terminal.
 * 
 * Provides:
 * - Ring buffer (capacity 200, most recent first)
 * - subscribe(listener) API
 * - Event types: EVIDENCE | NET | MUTATION | SYSTEM
 * - Noise filter support via fingerprint
 * 
 * Consumed by:
 * - TraceDrawer (forensic event log)
 * - Activity Ticker (significant events only)
 * - Network Quality (latency p95)
 * - Global Data Age (derived from NET events)
 */

export type RuntimeEventKind = 'EVIDENCE' | 'NET' | 'MUTATION' | 'SYSTEM';
export type RuntimeEventSeverity = 'LOW' | 'MED' | 'HIGH' | 'CRITICAL';

export interface RuntimeEvent {
    ts: number;                      // Date.now()
    kind: RuntimeEventKind;
    sev: RuntimeEventSeverity;
    name: string;                    // e.g., 'AIRLOCK_OPEN', 'NET_RESPONSE', 'MODE_CHANGE'

    // Network events
    endpoint?: string;
    http_status?: number;
    latency_ms?: number;
    content_type?: string;
    error_type?: string;             // 'NonJsonResponseError', 'HttpError', etc.
    hint?: string;                   // diagnostic hint for NonJsonResponseError
    snippet?: string;                // response snippet (redacted)

    // Mutation/Evidence events
    req_id?: string;
    intent_id?: string;
    actor?: string;                  // role/email if available

    // Generic details (sanitized)
    details?: Record<string, any>;

    // Noise filter grouping
    fingerprint?: string;            // e.g., "/api/balances|200|OK"
}

type Listener = (event: RuntimeEvent) => void;

class EventBus {
    private buffer: RuntimeEvent[] = [];
    private readonly capacity = 200;
    private listeners: Set<Listener> = new Set();

    /**
     * Emit event to all listeners and add to ring buffer
     */
    emit(event: RuntimeEvent): void {
        // Add to ring buffer (most recent first)
        this.buffer.unshift(event);

        // Trim to capacity
        if (this.buffer.length > this.capacity) {
            this.buffer = this.buffer.slice(0, this.capacity);
        }

        // Notify all listeners
        this.listeners.forEach(listener => {
            try {
                listener(event);
            } catch (err) {
                console.error('[EventBus] Listener error:', err);
            }
        });
    }

    /**
     * Subscribe to events
     * @returns unsubscribe function
     */
    subscribe(listener: Listener): () => void {
        this.listeners.add(listener);

        return () => {
            this.listeners.delete(listener);
        };
    }

    /**
     * Get current buffer snapshot (most recent first)
     */
    getBuffer(): readonly RuntimeEvent[] {
        return [...this.buffer];
    }

    /**
     * Clear buffer (for testing/debugging)
     */
    clear(): void {
        this.buffer = [];
    }
}

// Singleton instance
export const eventBus = new EventBus();

/**
 * Emit helper with defaults
 */
export function emitEvent(
    kind: RuntimeEventKind,
    name: string,
    severity: RuntimeEventSeverity,
    details?: Partial<RuntimeEvent>
): void {
    eventBus.emit({
        ts: Date.now(),
        kind,
        sev: severity,
        name,
        ...details,
    });
}

/**
 * Emit SYSTEM event (UI stalls, bootstrap, etc.)
 */
export function emitSystemEvent(
    name: string,
    severity: RuntimeEventSeverity,
    details?: Record<string, any>
): void {
    emitEvent('SYSTEM', name, severity, { details });
}

/**
 * Emit MUTATION event (mode changes, strategy actions, etc.)
 */
export function emitMutationEvent(
    name: string,
    severity: RuntimeEventSeverity,
    options: {
        req_id?: string;
        intent_id?: string;
        actor?: string;
        details?: Record<string, any>;
    }
): void {
    emitEvent('MUTATION', name, severity, options);
}
