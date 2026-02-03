/**
 * USE LOCAL STORAGE STATE
 * 
 * Implements layout persistence for operator preferences.
 * UI Constitution compliance: LAW 1 (Chinese Wall) - workspace prefix required.
 * 
 * Usage:
 *   const [traceOpen, setTraceOpen] = useLocalStorageState('trader:trace_open', false);
 */

import { useState, useEffect, useCallback } from 'react';

export function useLocalStorageState<T>(
    key: string,
    defaultValue: T
): [T, (value: T) => void] {
    // Initialize from localStorage or default
    const [value, setValue] = useState<T>(() => {
        try {
            const stored = localStorage.getItem(key);
            return stored ? JSON.parse(stored) : defaultValue;
        } catch {
            return defaultValue;
        }
    });

    // Update localStorage whenever value changes
    useEffect(() => {
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch (error) {
            console.warn(`Failed to persist ${key} to localStorage:`, error);
        }
    }, [key, value]);

    // Wrapped setter for cleaner API
    const setValueWrapper = useCallback((newValue: T) => {
        setValue(newValue);
    }, []);

    return [value, setValueWrapper];
}
