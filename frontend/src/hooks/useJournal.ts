import { useState, useEffect, useCallback } from 'react';

export interface JournalEntry {
    ts: string;
    action: string;
    details?: any;
}

const STORAGE_KEY = 'client_journal';
const MAX_ENTRIES = 50;

export const useJournal = () => {
    const [entries, setEntries] = useState<JournalEntry[]>([]);

    const loadEntries = useCallback(() => {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (raw) {
                setEntries(JSON.parse(raw));
            }
        } catch (e) {
            console.error("Failed to load journal", e);
        }
    }, []);

    useEffect(() => {
        loadEntries();
        // Optional: listen for storage events if multiple tabs need sync, 
        // but for now local single-tab updates are sufficient via logAction updating state.
    }, [loadEntries]);

    const logAction = useCallback((action: string, details?: any) => {
        const entry: JournalEntry = {
            ts: new Date().toISOString(),
            action,
            details
        };

        setEntries(prev => {
            const updated = [entry, ...prev].slice(0, MAX_ENTRIES);
            try {
                localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
            } catch (e) {
                console.error("Failed to save journal", e);
            }
            return updated;
        });
    }, []);

    const clearJournal = useCallback(() => {
        localStorage.removeItem(STORAGE_KEY);
        setEntries([]);
    }, []);

    return {
        entries,
        logAction,
        clearJournal,
        refresh: loadEntries
    };
};
