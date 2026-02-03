/**
 * USE GLOBAL PULSE
 * 
 * Phase F3: Header pulse components hook.
 * 
 * Provides:
 * - activityTicker: Last 5 significant events (AIRLOCK, NET_ERROR, EXECUTE, MODE_CHANGE, etc.)
 * - globalDataAge: Max age across active pollers (placeholder - returns 0 for now)
 * - networkQuality: p95 latency from last 50 NET events
 */

import { useState, useEffect } from 'react';
import { eventBus, RuntimeEvent } from '../lib/runtime/eventBus';

export interface ActivityEvent {
    ts: number;
    display: string; // Formatted display text
    color: string;   // Color for emphasis
}

export interface NetworkQuality {
    p95_ms: number;
    status: 'GOOD' | 'SLOW' | 'BAD';
    color: string;
}

export function useGlobalPulse() {
    const [activityTicker, setActivityTicker] = useState<ActivityEvent[]>([]);
    const [networkQuality, setNetworkQuality] = useState<NetworkQuality>({
        p95_ms: 0,
        status: 'GOOD',
        color: '#10b981',
    });

    useEffect(() => {
        // Track latencies for network quality (last 50)
        const latencies: number[] = [];

        // Subscribe to event bus
        const unsubscribe = eventBus.subscribe((event) => {
            // Update activity ticker (significant events only)
            if (isSignificantEvent(event)) {
                const activityEvent = formatActivityEvent(event);
                setActivityTicker(prev => [activityEvent, ...prev].slice(0, 5));
            }

            // Update network quality (NET events with latency)
            if (event.kind === 'NET' && event.latency_ms != null) {
                latencies.push(event.latency_ms);
                if (latencies.length > 50) {
                    latencies.shift(); // Keep last 50
                }

                // Compute p95
                if (latencies.length > 0) {
                    const sorted = [...latencies].sort((a, b) => a - b);
                    const p95_idx = Math.floor(sorted.length * 0.95);
                    const p95_ms = sorted[p95_idx];

                    const status = p95_ms < 200 ? 'GOOD' : p95_ms < 500 ? 'SLOW' : 'BAD';
                    const color = status === 'GOOD' ? '#10b981' : status === 'SLOW' ? '#f59e0b' : '#dc2626';

                    setNetworkQuality({ p95_ms, status, color });
                }
            }
        });

        return unsubscribe;
    }, []);

    return {
        activityTicker,
        networkQuality,
        globalDataAge: 0, // TODO F3.1: Compute max age across pollers
    };
}

// Filter significant events for activity ticker
function isSignificantEvent(event: RuntimeEvent): boolean {
    const significant = [
        'AIRLOCK_OPEN',
        'USER_CONFIRM_ACCEPTED',
        'EXECUTE_REQUEST',
        'EXECUTE_RESPONSE',
        'SYSTEM_SAFETY_ACTION',
        'NET_ERROR',
        'NET_RECOVERED',
        'DRIFT_HARD',
        'RISK_VETO',
        'MODE_CHANGE',
        'UI_STALLED',
    ];

    return significant.includes(event.name);
}

// Format event for activity ticker display
function formatActivityEvent(event: RuntimeEvent): ActivityEvent {
    const time = new Date(event.ts).toLocaleTimeString('en-US', { hour12: false });
    const endpoint = event.endpoint ? event.endpoint.split('/').pop() : '';
    const intent = event.intent_id ? event.intent_id.slice(0, 6) : '';

    let display = '';
    let color = '#888';

    switch (event.name) {
        case 'NET_ERROR':
            display = `[${time}] NET_ERROR ${endpoint || '?'} ${event.http_status} ${event.error_type}`;
            color = '#dc2626';
            break;
        case 'NET_RECOVERED':
            display = `[${time}] NET_RECOVERED ${endpoint || '?'}`;
            color = '#10b981';
            break;
        case 'AIRLOCK_OPEN':
            display = `[${time}] AIRLOCK_OPEN ${intent} (${event.sev})`;
            color = '#3b82f6';
            break;
        case 'EXECUTE_RESPONSE':
            display = `[${time}] EXECUTE ${intent}`;
            color = '#10b981';
            break;
        case 'MODE_CHANGE':
            display = `[${time}] MODE_CHANGE`;
            color = '#f59e0b';
            break;
        case 'UI_STALLED':
            display = `[${time}] UI_STALLED`;
            color = '#dc2626';
            break;
        default:
            display = `[${time}] ${event.name}`;
            color = event.sev === 'CRITICAL' ? '#dc2626' : event.sev === 'HIGH' ? '#f59e0b' : '#888';
    }

    return { ts: event.ts, display, color };
}
