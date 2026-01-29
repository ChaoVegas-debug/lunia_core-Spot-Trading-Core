/**
 * USE AIRLOCK HOOK (CANONICAL)
 * 
 * Frontend Build Unblock: Missing hook restoration
 * 
 * Wraps the canonical Airlock API (openAirlock from lib/airlock/airlockHelper)
 * Provides React hook interface for widgets.
 * 
 * NO NEW FEATURES: This is a thin proxy to existing Airlock system.
 * SINGLE SOURCE OF TRUTH: All Airlock logic lives in airlockHelper.ts
 */

import { useCallback } from 'react';
import { openAirlock as openAirlockHelper, type AirlockContext } from '../lib/airlock/airlockHelper';

export interface UseAirlockReturn {
    /**
     * Open the Airlock modal with given context
     * Routes to canonical openAirlock function
     */
    openAirlock: (context: AirlockContext) => void;
}

/**
 * Hook providing access to Airlock modal controls
 * 
 * Usage:
 * ```tsx
 * const { openAirlock } = useAirlock();
 * 
 * const handleAction = () => {
 *   openAirlock({
 *     actionType: 'SET_SYSTEM_MODE',
 *     severity: 'CRITICAL',
 *     state_before: {...},
 *     state_after: {...},
 *     executor: async () => {...}
 *   });
 * };
 * ```
 */
export function useAirlock(): UseAirlockReturn {
    const openAirlock = useCallback((context: AirlockContext) => {
        openAirlockHelper(context);
    }, []);

    return { openAirlock };
}
