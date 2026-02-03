import { useState, useCallback, useEffect } from 'react';
import { EvidenceEvent, hashPayload } from '../lib/forensics/evidenceTypes';
import { emitEvent } from '../lib/runtime/eventBus';
import type { RuntimeEventSeverity } from '../lib/runtime/eventBus';

/**
 * EVIDENCE RECORDER HOOK
 * 
 * Records all forensic events to session chain.
 * Events are stored in sessionStorage for persistence across page reloads.
 * 
 * Phase F3.3: Now also emits significant events to EventBus for TraceDrawer visibility.
 */

const EVIDENCE_STORAGE_KEY = 'lunia_evidence_chain';
const MAX_EVENTS = 500; // Prevent unbounded growth

// UUIDv7 Generator (reuse from useForensicSession)
function generateUUIDv7(): string {
    const timestamp = Date.now();
    const timestampHex = timestamp.toString(16).padStart(12, '0');
    const randomBytes = new Uint8Array(10);
    crypto.getRandomValues(randomBytes);
    const uuid = [
        timestampHex.slice(0, 8),
        timestampHex.slice(8, 12),
        '7' + Array.from(randomBytes.slice(0, 3), b => b.toString(16).padStart(2, '0')).join('').slice(0, 3),
        ((randomBytes[3] & 0x3f) | 0x80).toString(16).padStart(2, '0') + Array.from(randomBytes.slice(4, 6), b => b.toString(16).padStart(2, '0')).join(''),
        Array.from(randomBytes.slice(6, 10), b => b.toString(16).padStart(2, '0')).join('')
    ].join('-');
    return uuid;
}

export function useEvidenceRecorder(forensic_session_id?: string) {
    const [events, setEvents] = useState<EvidenceEvent[]>([]);

    // Load existing events from storage
    useEffect(() => {
        const stored = sessionStorage.getItem(EVIDENCE_STORAGE_KEY);
        if (stored) {
            try {
                const parsed = JSON.parse(stored);
                setEvents(parsed);
            } catch (e) {
                console.warn('[Evidence] Failed to parse stored events');
            }
        }
    }, []);

    // Record new evidence event
    const recordEvent = useCallback(async (
        step: EvidenceEvent['step'],
        details: Partial<Omit<EvidenceEvent, 'event_id' | 'ts_ms' | 'forensic_session_id' | 'step'>>
    ): Promise<EvidenceEvent> => {
        if (!forensic_session_id) {
            console.warn('[Evidence] Cannot record event without forensic_session_id');
            return Promise.reject(new Error('No forensic session'));
        }

        const event: EvidenceEvent = {
            event_id: generateUUIDv7(),
            ts_ms: Date.now(),
            forensic_session_id,
            step,
            ...details
        };

        // Hash payload if provided
        if (details.endpoint && !details.payload_hash) {
            const payload = { endpoint: details.endpoint, method: details.method };
            event.payload_hash = await hashPayload(payload);
        }

        setEvents(prev => {
            const updated = [...prev, event];
            // Trim if too large
            const trimmed = updated.slice(-MAX_EVENTS);
            sessionStorage.setItem(EVIDENCE_STORAGE_KEY, JSON.stringify(trimmed));
            return trimmed;
        });

        console.log('[Evidence] Recorded:', step, event.event_id);

        // Phase F3.3: Emit significant events to EventBus (noise-disciplined)
        const significantSteps = [
            'AIRLOCK_OPEN',
            'PREFLIGHT_START',
            'PREFLIGHT_PASS',
            'PREFLIGHT_FAIL',
            'USER_CONFIRM_ACCEPTED',
            'USER_CONFIRM_REJECTED',
            'EXECUTE_REQUEST',
            'EXECUTE_RESPONSE',
            'SYSTEM_SAFETY_ACTION',
        ];

        if (significantSteps.includes(step)) {
            // Map evidence step to severity
            let sev: RuntimeEventSeverity = 'MED';
            if (step === 'PREFLIGHT_FAIL' || step === 'USER_CONFIRM_REJECTED') sev = 'HIGH';
            if (step === 'SYSTEM_SAFETY_ACTION') sev = 'CRITICAL';

            emitEvent({
                ts: event.ts_ms,
                kind: 'EVIDENCE',
                sev,
                name: step,
                intent_id: details.client_intent_id,
                req_id: details.request_id,
                actor: details.notes, // Use notes as actor if available
                endpoint: details.endpoint,
                http_status: typeof details.status === 'number' ? details.status : undefined,
                details: {
                    event_id: event.event_id,
                    forensic_session_id: event.forensic_session_id,
                    method: details.method,
                },
            });
        }

        return event;
    }, [forensic_session_id]);

    // Get events for a specific intent
    const getIntentEvents = useCallback((client_intent_id: string): EvidenceEvent[] => {
        return events.filter(e => e.client_intent_id === client_intent_id);
    }, [events]);

    // Clear all events (use with caution!)
    const clearEvents = useCallback(() => {
        setEvents([]);
        sessionStorage.removeItem(EVIDENCE_STORAGE_KEY);
        console.log('[Evidence] Chain cleared');
    }, []);

    // Export events as JSON
    const exportEvents = useCallback(() => {
        const dataStr = JSON.stringify(events, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(dataBlob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `evidence-${forensic_session_id}-${Date.now()}.json`;
        link.click();
        URL.revokeObjectURL(url);
    }, [events, forensic_session_id]);

    return {
        events,
        recordEvent,
        getIntentEvents,
        clearEvents,
        exportEvents
    };
}
