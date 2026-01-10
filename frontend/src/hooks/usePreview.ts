import { useSyncExternalStore } from 'react';
import { previewStore } from '../preview/PreviewStore';

export const usePreview = () => {
    // Check ENV for global preview flag
    const isPreviewEnv = import.meta.env.VITE_PREVIEW_MODE === '1';

    // Subscribe to store updates
    const storeState = useSyncExternalStore(previewStore.subscribe, previewStore.getState);

    // Derived state
    const isSimulated = isPreviewEnv || !storeState.backend_reachable || storeState.force_sim;

    return {
        isPreview: isSimulated,
        previewStore,
        state: storeState,
        // Helper to check if we should enforce SIM behavior
        shouldSimulate: (endpointAvailable: boolean) => isSimulated || !endpointAvailable
    };
};
