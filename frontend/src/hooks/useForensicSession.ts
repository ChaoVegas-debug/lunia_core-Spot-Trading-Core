import { useState, useEffect, useCallback } from 'react';

/**
 * FORENSIC SESSION HOOK
 * 
 * Generates and manages forensic session IDs and client intent IDs.
 * Implements UUIDv7 (timestamp-based) for chronological ordering.
 * 
 * Chain-of-Custody Pattern:
 * login → forensic_session_id (persisted) → client_intent_id (per action)
 */

// UUIDv7 Generator (timestamp-based for chronological ordering)
function generateUUIDv7(): string {
    const timestamp = Date.now();
    const timestampHex = timestamp.toString(16).padStart(12, '0');

    // Generate random bits for variant and node
    const randomBytes = new Uint8Array(10);
    crypto.getRandomValues(randomBytes);

    // Format: xxxxxxxx-xxxx-7xxx-yxxx-xxxxxxxxxxxx
    // where y is 8, 9, A, or B (variant bits)
    const uuid = [
        timestampHex.slice(0, 8),
        timestampHex.slice(8, 12),
        '7' + Array.from(randomBytes.slice(0, 3), b => b.toString(16).padStart(2, '0')).join('').slice(0, 3),
        ((randomBytes[3] & 0x3f) | 0x80).toString(16).padStart(2, '0') + Array.from(randomBytes.slice(4, 6), b => b.toString(16).padStart(2, '0')).join(''),
        Array.from(randomBytes.slice(6, 10), b => b.toString(16).padStart(2, '0')).join('')
    ].join('-');

    return uuid;
}

// Session metadata
export interface ForensicSessionMetadata {
    forensic_session_id: string;
    user_id?: string;
    started_at: number;
    ip_address?: string;
    user_agent: string;
    geo_location?: {
        country?: string;
        region?: string;
        timezone: string;
    };
}

// Intent metadata
export interface ClientIntentMetadata {
    client_intent_id: string;
    forensic_session_id: string;
    action_type: string;
    severity: 'MEDIUM' | 'HIGH' | 'CRITICAL';
    created_at: number;
    ttl_ms: number;
}

// Anomaly flags
export interface AnomalyFlag {
    type: 'UNUSUAL_TIME' | 'GEO_MISMATCH' | 'HIGH_VELOCITY' | 'DEVICE_CHANGE';
    severity: 'INFO' | 'WARNING' | 'CRITICAL';
    message: string;
    detected_at: number;
}

const SESSION_STORAGE_KEY = 'lunia_forensic_session';

/**
 * Initialize or retrieve forensic session
 */
export function useForensicSession() {
    const [session, setSession] = useState<ForensicSessionMetadata | null>(null);

    useEffect(() => {
        // Try to retrieve existing session
        const stored = sessionStorage.getItem(SESSION_STORAGE_KEY);
        if (stored) {
            try {
                const parsed = JSON.parse(stored);
                setSession(parsed);
                return;
            } catch (e) {
                console.warn('[Forensic] Failed to parse stored session, creating new');
            }
        }

        // Create new session
        const newSession: ForensicSessionMetadata = {
            forensic_session_id: generateUUIDv7(),
            started_at: Date.now(),
            user_agent: navigator.userAgent,
            geo_location: {
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
            }
        };

        sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(newSession));
        setSession(newSession);

        console.log('[Forensic] Session initialized:', newSession.forensic_session_id);
    }, []);

    return session;
}

/**
 * Generate client intent ID for a specific action
 */
export function useClientIntent(
    actionType: string,
    severity: 'MEDIUM' | 'HIGH' | 'CRITICAL',
    ttl_ms: number = 300000 // 5 minutes default
) {
    const session = useForensicSession();

    const generateIntent = useCallback((): ClientIntentMetadata | null => {
        if (!session) {
            console.error('[Forensic] Cannot generate intent without session');
            return null;
        }

        return {
            client_intent_id: generateUUIDv7(),
            forensic_session_id: session.forensic_session_id,
            action_type: actionType,
            severity,
            created_at: Date.now(),
            ttl_ms
        };
    }, [session, actionType, severity, ttl_ms]);

    return { session, generateIntent };
}

/**
 * Detect anomalies in current session context
 */
export function useAnomalyDetection(intent?: ClientIntentMetadata): AnomalyFlag[] {
    const [anomalies, setAnomalies] = useState<AnomalyFlag[]>([]);

    useEffect(() => {
        if (!intent) return;

        const detected: AnomalyFlag[] = [];
        const now = new Date();
        const hour = now.getHours();

        // ANOMALY 1: Unusual Time (outside business hours)
        if (hour < 6 || hour > 22) {
            detected.push({
                type: 'UNUSUAL_TIME',
                severity: intent.severity === 'CRITICAL' ? 'WARNING' : 'INFO',
                message: `Action attempted at ${hour}:00 (outside 06:00-22:00)`,
                detected_at: Date.now()
            });
        }

        // ANOMALY 2: High Velocity (multiple intents in short time)
        // This would require tracking intent history - for now, mock
        const recentIntents = sessionStorage.getItem('lunia_recent_intents');
        if (recentIntents) {
            const count = JSON.parse(recentIntents).length;
            if (count > 5) {
                detected.push({
                    type: 'HIGH_VELOCITY',
                    severity: 'WARNING',
                    message: `${count} intents in last 5 minutes`,
                    detected_at: Date.now()
                });
            }
        }

        // ANOMALY 3: Geo Mismatch (would require backend IP geolocation)
        // MOCK: Detect timezone mismatch if you want
        // For now, we'll skip this one

        // ANOMALY 4: Device Change (detect user agent changes mid-session)
        // This would require comparing session user_agent with current
        // For now, mock

        setAnomalies(detected);
    }, [intent]);

    return anomalies;
}

/**
 * Check if intent is expired
 */
export function isIntentExpired(intent: ClientIntentMetadata): boolean {
    return Date.now() > (intent.created_at + intent.ttl_ms);
}

/**
 * Get time remaining for intent (in milliseconds)
 */
export function getIntentTimeRemaining(intent: ClientIntentMetadata): number {
    const remaining = (intent.created_at + intent.ttl_ms) - Date.now();
    return Math.max(0, remaining);
}
