import { useState, useRef, useCallback } from 'react';

interface SliderState {
    localValue: number;
    isSaving: boolean;
}

interface UseOptimisticSliderOptions {
    initialValue: number;
    onCommit: (value: number) => Promise<void>;
    debounceMs?: number;
}

/**
 * Two-phase slider control:
 * - `localValue`: immediate UI state for smooth dragging
 * - `handleChange`: updates local state only (no API calls)
 * - `handleCommit`: fires API on mouseup/touchend
 * - `isSaving`: shows saving indicator during commit
 */
export function useOptimisticSlider({
    initialValue,
    onCommit,
    debounceMs = 0
}: UseOptimisticSliderOptions) {
    const [state, setState] = useState<SliderState>({
        localValue: initialValue,
        isSaving: false
    });

    const commitTimeoutRef = useRef<number | null>(null);
    const lastCommittedValue = useRef(initialValue);

    // Sync with external value changes (e.g., polling updates)
    const syncValue = useCallback((externalValue: number) => {
        if (!state.isSaving && Math.abs(externalValue - lastCommittedValue.current) > 0.0001) {
            setState(prev => ({ ...prev, localValue: externalValue }));
            lastCommittedValue.current = externalValue;
        }
    }, [state.isSaving]);

    // Handle slider change - UI only, no API
    const handleChange = useCallback((value: number) => {
        setState(prev => ({ ...prev, localValue: value }));

        // Clear any pending debounced commit
        if (commitTimeoutRef.current) {
            window.clearTimeout(commitTimeoutRef.current);
            commitTimeoutRef.current = null;
        }
    }, []);

    // Commit to server - called on mouseup/touchend
    const handleCommit = useCallback(async () => {
        const valueToCommit = state.localValue;

        // Skip if value hasn't changed
        if (Math.abs(valueToCommit - lastCommittedValue.current) < 0.0001) {
            return;
        }

        setState(prev => ({ ...prev, isSaving: true }));

        try {
            await onCommit(valueToCommit);
            lastCommittedValue.current = valueToCommit;
        } catch (error) {
            // Rollback on error
            setState(prev => ({ ...prev, localValue: lastCommittedValue.current }));
            console.error('[useOptimisticSlider] Commit failed:', error);
        } finally {
            setState(prev => ({ ...prev, isSaving: false }));
        }
    }, [state.localValue, onCommit]);

    // Optional: debounced auto-commit (fallback if mouseup not captured)
    const handleChangeWithDebounce = useCallback((value: number) => {
        handleChange(value);

        if (debounceMs > 0) {
            if (commitTimeoutRef.current) {
                window.clearTimeout(commitTimeoutRef.current);
            }
            commitTimeoutRef.current = window.setTimeout(() => {
                handleCommit();
            }, debounceMs);
        }
    }, [handleChange, handleCommit, debounceMs]);

    return {
        localValue: state.localValue,
        isSaving: state.isSaving,
        handleChange: debounceMs > 0 ? handleChangeWithDebounce : handleChange,
        handleCommit,
        syncValue
    };
}
