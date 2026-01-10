import { useState, useCallback } from 'react';
import { useDashboard } from '../context/DashboardContext';

export type SemiAutoState = 'IDLE' | 'STAGED' | 'PREVIEW' | 'CONFIRMING' | 'EXECUTING' | 'DONE';

interface Proposal<T> {
    id: string;
    previous: T;
    staged: T;
    risks: string[];
    confidence: number;
    confirm_deadline?: number;
}

export function useSemiAuto<T>(initialData: T, executeFn: (data: T, idempotencyKey: string) => Promise<void>) {
    const [state, setState] = useState<SemiAutoState>('IDLE');
    const { addToast } = useDashboard();
    const [stagedData, setStagedData] = useState<T>(initialData);
    const [proposal, setProposal] = useState<Proposal<T> | null>(null);
    const [idempotencyKey, setIdempotencyKey] = useState<string>('');

    // Stage a change (local only)
    const stageChange = useCallback((newData: T) => {
        setStagedData(newData);
        setState('STAGED');
    }, []);

    // Initiates the Flow: AI Proposal / User Edit -> Preview
    const previewProposal = useCallback(() => {
        const id = Math.random().toString(36).substring(7).toUpperCase();
        // Generate Idempotency Key unique to this "Intent"
        const newKey = crypto.randomUUID();
        setIdempotencyKey(newKey);

        setProposal({
            id: `PROP-${id}`,
            previous: initialData, // Ideally valid deep copy
            staged: stagedData,
            risks: ['Changes strategy weights', 'Impacts capital allocation'], // Mocked risk logic
            confidence: 0.92,
            confirm_deadline: Date.now() + 30000 // 30s TTL
        });
        setState('PREVIEW');
    }, [initialData, stagedData]);

    // Apply (Lock)
    const applyProposal = useCallback(() => {
        setState('CONFIRMING');
    }, []);

    // Confirm (Execute)
    const confirmProposal = useCallback(async () => {
        if (!proposal) return;

        // TTL Check Logic
        if (proposal.confirm_deadline && Date.now() > proposal.confirm_deadline) {
            addToast({ type: 'ERROR', message: "Confirmation Expired (TTL)" });
            setState('PREVIEW'); // Force re-review
            return; // Block execution
        }

        setState('EXECUTING');
        try {
            await executeFn(proposal.staged, idempotencyKey);
            setState('IDLE'); // Reset to IDLE after success, live data query will verify
            setProposal(null);
            setIdempotencyKey('');
        } catch (e) {
            console.error(e);
            addToast({ type: 'ERROR', message: "Execution Failed" });
            setState('STAGED'); // Revert to staged on failure
        }
    }, [executeFn, proposal, idempotencyKey]);

    const cancelFlow = useCallback(() => {
        setStagedData(initialData); // Revert
        setProposal(null);
        setIdempotencyKey('');
        setState('IDLE');
    }, [initialData]);

    return {
        state,
        stagedData,
        proposal,
        idempotencyKey,
        stageChange,
        previewProposal,
        applyProposal,
        confirmProposal,
        cancelFlow
    };
}
