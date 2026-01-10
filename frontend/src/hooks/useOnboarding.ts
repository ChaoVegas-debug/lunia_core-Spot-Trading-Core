import { useState, useEffect, useCallback } from 'react';
import { useAuth } from './useAuth';

export type OnboardingStatus = 'NOT_STARTED' | 'IN_PROGRESS' | 'COMPLETED';

interface OnboardingState {
    step: number; // 1-indexed
    status: OnboardingStatus;
}

const DEFAULT_STATE: OnboardingState = {
    step: 1,
    status: 'NOT_STARTED'
};

export const useOnboarding = () => {
    const { user } = useAuth();
    const userId = user?.id;
    const STORAGE_KEY = userId ? `LUNIA_ONBOARDING_${userId}` : null;

    const [state, setState] = useState<OnboardingState>(() => {
        // Piority 1: Server Truth (if loaded)
        if (user?.onboarding_completed) {
            return { status: 'COMPLETED', step: 4 };
        }

        if (!STORAGE_KEY) return DEFAULT_STATE;
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) {
            try {
                return JSON.parse(stored);
            } catch (e) {
                console.warn("Corrupt Onboarding State", e);
            }
        }
        return DEFAULT_STATE;
    });

    // Sync to storage
    useEffect(() => {
        if (STORAGE_KEY) {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
        }
    }, [state, STORAGE_KEY]);

    // Sync from User Profile (Server Truth)
    useEffect(() => {
        if (user?.onboarding_completed && state.status !== 'COMPLETED') {
            console.log('[Onboarding] Auto-completing based on User Profile');
            setState(prev => ({ ...prev, status: 'COMPLETED', step: 4 }));
        }
    }, [user, state.status]);

    useEffect(() => {
        if (!STORAGE_KEY) {
            // If user is logged out, reset state unless we want to persist guest progress? 
            // For now, reset to avoid leaks.
            setState(DEFAULT_STATE);
            return;
        }
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) {
            try {
                setState(JSON.parse(stored));
            } catch (e) { /* ignore */ }
        } else {
            // If no storage, but user is completed, set completed
            if (user?.onboarding_completed) {
                setState({ status: 'COMPLETED', step: 4 });
            } else {
                setState(DEFAULT_STATE);
            }
        }
    }, [STORAGE_KEY]);

    const setStep = useCallback((step: number) => {
        setState(prev => ({
            ...prev,
            step,
            status: 'IN_PROGRESS'
        }));
    }, []);

    const complete = useCallback(() => {
        setState(prev => ({
            ...prev,
            status: 'COMPLETED',
            step: 4 // Ensure max
        }));
    }, []);

    const reset = useCallback(() => {
        setState(DEFAULT_STATE);
    }, []);

    return {
        step: state.step,
        status: state.status,
        setStep,
        complete,
        reset,
        isCompleted: state.status === 'COMPLETED'
    };
};
