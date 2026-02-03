/**
 * EVIDENCE EVENT TYPES
 * 
 * Defines the evidence event structure for forensic audit trail.
 * All actions are recorded as evidence events for chain-of-custody.
 */

export interface EvidenceEvent {
    event_id: string; // UUIDv7
    ts_ms: number;
    forensic_session_id: string;
    client_intent_id?: string;
    step: EvidenceStep;
    endpoint?: string;
    method?: string;
    status: number | string; // HTTP status or custom
    latency_ms?: number;
    request_id?: string; // from x-request-id header
    payload_hash?: string; // SHA256(JSON.stringify(payload))
    notes?: string;
    anomaly_flags?: Array<{
        type: string;
        severity: string;
        message: string;
    }>;
}

export type EvidenceStep =
    | 'SESSION_START'
    | 'SESSION_PRESENT'
    | 'INTENT_CREATED'
    | 'UI_OPENED'
    | 'PREFLIGHT_CHECK'
    | 'USER_CONFIRM'
    | 'USER_REASON_SET'
    | 'USER_CONFIRM_HELD'
    | 'USER_CONFIRM_ACCEPTED'
    | 'USER_CANCELLED'
    | 'EXECUTE_REQUEST'
    | 'EXECUTE_RESPONSE'
    | 'BUNDLE_EXPORTED'
    | 'BUNDLE_VERIFIED'
    | 'EMERGENCY_HALT'
    | 'BLACK_BOX_DUMP'
    | 'SYSTEM_SAFETY_ACTION'
    | 'CONTEXT_SWITCH_REQUESTED'
    | 'CONTEXT_SWITCH_CONFIRMED';

export interface EvidenceBundle {
    bundle_id: string;
    forensic_session_id: string;
    client_intent_id: string;
    created_at: number;
    manifest: {
        files: Array<{
            name: string;
            sha256: string;
            size_bytes: number;
        }>;
        merkle_root?: string;
    };
    bundle_data: {
        intent: any;
        preflight_history: EvidenceEvent[];
        execution_trace: EvidenceEvent[];
        user_reason: string;
        final_status: 'SUCCESS' | 'PARTIAL' | 'FAILED';
    };
    seal: {
        bundle_hash: string;
        merkle_root?: string;
        notarized_timestamp?: string;
    };
}

// Simple SHA-256 hashing for payloads (browser-compatible)
export async function hashPayload(payload: any): Promise<string> {
    const text = JSON.stringify(payload, Object.keys(payload).sort());
    const encoder = new TextEncoder();
    const data = encoder.encode(text);
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}
