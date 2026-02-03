/**
 * USE LAST MUTATION
 * 
 * Phase F3.2: Derive last mutation from event stream
 * 
 * Backend may be silent on last_actor/intent. This hook listens to eventBus
 * and derives the last successful mutation event for display in SystemState.
 * 
 * Returns:
 * - action: Human-readable action (e.g., "MODE_CHANGE: MANUAL→AUTO")
 * - actor: Actor string (email/role, defaults to "unknown")
 * - intent_id: Intent ID (short format: id8)
 * - ts: Timestamp (milliseconds)
 * - derived: true (always, since we're deriving from events)
 * - sourceEventKind: Original event kind
 * - endpoint: Endpoint (if available)
 * - http_status: HTTP status (if available)
 */

import { useState, useEffect } from 'react';
import { eventBus } from '../lib/runtime/eventBus';
import type { RuntimeEvent } from '../lib/runtime/eventBus';

export interface LastMutation {
    action: string;
    actor: string;
    intent_id: string;
    ts: number;
    derived: true;
    sourceEventKind: string;
    endpoint?: string;
    http_status?: number;
}

export interface UseLastMutationOptions {
    /** Endpoint pattern to match (e.g., /api/ops/mode) */
    endpointPattern?: string | RegExp;

    /** Event names to consider (e.g., EXECUTE_RESPONSE, MODE_CHANGE) */
    nameAllowList?: string[];

    /** Only consider successful events (http_status 200-299) */
    requireSuccess?: boolean;

    /** Optional freshness window in ms (ignore events older than this) */
    windowMs?: number;
}

const DEFAULT_OPTIONS: UseLastMutationOptions = {
    nameAllowList: ['EXECUTE_RESPONSE', 'MODE_CHANGE', 'SYSTEM_SAFETY_ACTION'],
    requireSuccess: true,
};

/**
 * Hook to derive last mutation from event stream
 */
export function useLastMutation(options: UseLastMutationOptions = {}): LastMutation | null {
    const opts = { ...DEFAULT_OPTIONS, ...options };
    const [lastMutation, setLastMutation] = useState<LastMutation | null>(null);

    useEffect(() => {
        const handleEvent = (event: RuntimeEvent) => {
            // Apply filters
            if (opts.nameAllowList && !opts.nameAllowList.includes(event.name)) {
                return;
            }

            if (opts.endpointPattern) {
                if (!event.endpoint) return;

                const pattern = opts.endpointPattern;
                const matches = typeof pattern === 'string'
                    ? event.endpoint.includes(pattern)
                    : pattern.test(event.endpoint);

                if (!matches) return;
            }

            if (opts.requireSuccess && event.http_status) {
                if (event.http_status < 200 || event.http_status >= 300) {
                    return;
                }
            }

            if (opts.windowMs) {
                const age = Date.now() - event.ts;
                if (age > opts.windowMs) return;
            }

            // Derive action from event
            let action = event.name;
            if (event.details) {
                const details = event.details as any;

                // Try to extract mode change info
                if (details.mode || details.new_mode || details.target_mode) {
                    const newMode = details.mode || details.new_mode || details.target_mode;
                    const oldMode = details.old_mode || details.previous_mode;

                    if (oldMode) {
                        action = `MODE_CHANGE: ${oldMode}→${newMode}`;
                    } else {
                        action = `MODE_CHANGE: ${newMode}`;
                    }
                }

                // Try to extract other action info
                if (details.action) {
                    action = details.action;
                }
            }

            // Build mutation record
            // Phase F3 Hardening: Actor derivation (forensic integrity)
            // - Never use details.notes (may contain secrets/tokens)
            // - Strict actor source: event.actor OR event.details.actor
            // - Normalize for deterministic identicon (same actor = same icon)
            const rawActor = event.actor || (event.details as any)?.actor || 'unknown';
            const normalizedActor = rawActor.trim().toLowerCase() || 'unknown';

            const mutation: LastMutation = {
                action,
                actor: normalizedActor,
                intent_id: event.intent_id ? formatIntentId(event.intent_id) : 'n/a',
                ts: event.ts,
                derived: true,
                sourceEventKind: event.kind,
                endpoint: event.endpoint,
                http_status: event.http_status,
            };

            setLastMutation(mutation);
        };

        // Subscribe to event bus
        const unsubscribe = eventBus.subscribe(handleEvent);

        // Also check buffer for existing events
        const buffer = eventBus.getBuffer();
        const relevantEvents = buffer.filter(evt => {
            if (opts.nameAllowList && !opts.nameAllowList.includes(evt.name)) return false;
            if (opts.requireSuccess && evt.http_status && (evt.http_status < 200 || evt.http_status >= 300)) return false;
            return true;
        });

        if (relevantEvents.length > 0) {
            // Use most recent
            handleEvent(relevantEvents[0]);
        }

        return unsubscribe;
    }, [opts.endpointPattern, opts.nameAllowList, opts.requireSuccess, opts.windowMs]);

    return lastMutation;
}

/**
 * Format intent ID to short format (first 8 chars)
 */
function formatIntentId(id: string): string {
    if (!id) return 'n/a';
    if (id.length <= 8) return id;
    return id.substring(0, 8);
}
