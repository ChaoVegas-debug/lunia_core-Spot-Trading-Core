import { usePreview } from '../context/PreviewModeContext';
import { usePoller } from './usePoller';

export interface DataResourceState<T> {
    data?: T;
    error?: Error;
    loading: boolean;
    refresh: () => void;
    source: 'LIVE' | 'SIMULATION';
}

/**
 * Higher-order hook that tries to fetch from real backend, but seamlessly falls back to 
 * PreviewStore simulation if backend is unreachable or if force-simulation is on.
 * 
 * @param realFetcher Function that calls the real API
 * @param simSelector Function that selects data from the PreviewStore state
 * @param intervalMs Polling interval
 */
export function useDataResource<T>(
    realFetcher: (signal: AbortSignal) => Promise<T>,
    simSelector: (state: any) => T,
    intervalMs: number = 5000,
    deps: unknown[] = []
): DataResourceState<T> {
    const { isPreview, isSimulation, state: simState } = usePreview();

    // Migrated from usePolledResource to usePoller
    const { data, error, refresh } = usePoller<T>({
        key: 'data_resource_wrapper',
        endpoint: '/api/unknown',
        fetcher: () => realFetcher(new AbortController().signal),
        interval_ms: intervalMs,
        critical: false
    });

    const resource = { data, error: error || undefined, loading: false, refresh };

    // Fallback Logic:
    // 1. If we are NOT in preview/simulation, effectively pass through the real resource.
    if (!isPreview || !isSimulation) {
        return {
            ...resource,
            source: 'LIVE'
        };
    }

    // 2. If in Preview Simulation:
    // Determine if we should use Sim Data.
    // Conditions: 
    // - Real request failed (error)
    // - OR real request returned "bad status" (logic dependent, but here generic)
    // - OR we just prefer simulation speed (optional, for now we prefer Live if avail)

    // For now: "If Error or Loading (initially) and Simulation is allowed, show Sim".
    // Actually, showing Sim while loading prevents "flicker" or "empty".
    const useSim = resource.error || (!resource.data) || simState.sim_offline;

    if (useSim) {
        // Select data from the latest store state
        let simData: T | undefined;
        try {
            simData = simSelector(simState);
        } catch (e) {
            console.warn("Sim selector failed", e);
        }

        return {
            data: simData,
            loading: false, // Sim is instant
            error: undefined, // Mask the backend error
            refresh: resource.refresh, // Trying to refresh real backend is fine
            source: 'SIMULATION'
        };
    }

    return {
        ...resource,
        source: 'LIVE'
    };
}
