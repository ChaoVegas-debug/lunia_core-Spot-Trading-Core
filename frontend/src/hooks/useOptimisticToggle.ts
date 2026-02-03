import { useState, useCallback, useRef } from 'react';

interface ToggleState {
    localValue: boolean;
    isPending: boolean;
}

interface UseOptimisticToggleOptions {
    initialValue: boolean;
    onToggle: (newValue: boolean) => Promise<void>;
    onError?: (error: Error, rolledBackTo: boolean) => void;
}

/**
 * Optimistic toggle with rollback:
 * - Immediate visual flip on click (<50ms perceived)
 * - Background API request
 * - Rollback + error callback on failure
 */
export function useOptimisticToggle({
    initialValue,
    onToggle,
    onError
}: UseOptimisticToggleOptions) {
    const [state, setState] = useState<ToggleState>({
        localValue: initialValue,
        isPending: false
    });

    const lastConfirmedValue = useRef(initialValue);

    // Sync with external value changes (e.g., polling updates)
    const syncValue = useCallback((externalValue: boolean) => {
        if (!state.isPending && externalValue !== lastConfirmedValue.current) {
            setState(prev => ({ ...prev, localValue: externalValue }));
            lastConfirmedValue.current = externalValue;
        }
    }, [state.isPending]);

    // Handle toggle - optimistic update
    const handleToggle = useCallback(async () => {
        const newValue = !state.localValue;

        // Optimistic update - instant visual flip
        setState({ localValue: newValue, isPending: true });

        try {
            await onToggle(newValue);
            lastConfirmedValue.current = newValue;
        } catch (error) {
            // Rollback on error
            const rolledBackTo = lastConfirmedValue.current;
            setState({ localValue: rolledBackTo, isPending: false });

            if (onError) {
                onError(error as Error, rolledBackTo);
            } else {
                console.error('[useOptimisticToggle] Toggle failed, rolled back:', error);
            }
            return;
        }

        setState(prev => ({ ...prev, isPending: false }));
    }, [state.localValue, onToggle, onError]);

    return {
        value: state.localValue,
        isPending: state.isPending,
        handleToggle,
        syncValue
    };
}
