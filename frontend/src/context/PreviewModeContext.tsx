import React, { createContext, useContext, useState, useEffect, useMemo, ReactNode } from 'react';
import { PREVIEW_MODE, PREVIEW_SIMULATION } from '../config/preview';
import { previewStore, PreviewState } from '../preview/PreviewStore';
import { OpsState, HealthcheckResponse } from '../api/types';

interface PreviewModeContextType {
    // Config
    isPreview: boolean;
    isSimulation: boolean;
    toggleSimulation: () => void;

    // State
    state: PreviewState; // Full state access
    simOps: OpsState;    // Shortcut for frequent access
    simHealth: HealthcheckResponse;

    // Actions
    actions: typeof previewStore; // Access to store methods like setExecMode
}

const PreviewModeContext = createContext<PreviewModeContextType | undefined>(undefined);

export const PreviewModeProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    // 1. Initial Config
    const [isSimulation, setIsSimulation] = useState(() => {
        const stored = localStorage.getItem('lunia_preview_simulation_enabled');
        return stored !== null ? stored === 'true' : PREVIEW_MODE && PREVIEW_SIMULATION;
    });

    // 2. React State synced with PreviewStore
    const [storeState, setStoreState] = useState<PreviewState>(previewStore.getState());

    // 3. Subscription to Store
    useEffect(() => {
        const unsubscribe = previewStore.subscribe(() => {
            setStoreState({ ...previewStore.getState() }); // Clone to trigger re-render
        });
        return unsubscribe;
    }, []);

    // 4. Persistence of toggle
    useEffect(() => {
        localStorage.setItem('lunia_preview_simulation_enabled', String(isSimulation));
    }, [isSimulation]);

    // Destructure state
    const { force_sim, backend_reachable, health, ops } = storeState;

    const toggleSimulation = () => setIsSimulation(prev => !prev);

    // Actions - Exposed
    const setForceSim = (val: boolean) => previewStore.setForceSim(val);
    const setBackendReachable = (val: boolean) => previewStore.setBackendReachable(val);
    const setSimExecMode = (mode: string) => previewStore.setExecMode(mode as any); // Use Store Action
    const setSimGlobalStop = (stop: boolean) => previewStore.setGlobalStop(stop); // Use Store Action 

    const value = useMemo(() => ({
        isPreview: PREVIEW_MODE,
        isSimulation,
        toggleSimulation,

        forceSim: force_sim, // Map snake_case to camelCase if context expects it, or just pass state
        setForceSim,

        backendReachable: backend_reachable,
        setBackendReachable,

        simHealth: health,
        simOps: ops,

        state: storeState,
        actions: previewStore,

        setSimExecMode,
        setSimGlobalStop
    }), [PREVIEW_MODE, isSimulation, force_sim, backend_reachable, health, ops]); // Dep array fixed

    return (
        <PreviewModeContext.Provider value={value}>
            {children}
        </PreviewModeContext.Provider>
    );
};

export const usePreview = () => {
    const context = useContext(PreviewModeContext);
    if (!context) {
        throw new Error('usePreview must be used within a PreviewModeProvider');
    }
    return context;
};

