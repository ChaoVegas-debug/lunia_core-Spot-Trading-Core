import React, { createContext, useContext, useState, useCallback, useMemo } from 'react';

export type WidgetStatus = 'OK' | 'BLOCKED' | 'LOADING' | 'ERROR' | 'UNKNOWN';

export interface WidgetState {
    id: string; // Component Name
    status: WidgetStatus;
    reason?: string; // e.g. "AUTH_FAIL", "NET_ERROR"
    lastUpdated: number;
}

interface WidgetRegistryContextType {
    widgets: Record<string, WidgetState>;
    registerWidget: (id: string, status: WidgetStatus, reason?: string) => void;
}

const WidgetRegistryContext = createContext<WidgetRegistryContextType | undefined>(undefined);

export const WidgetRegistryProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [widgets, setWidgets] = useState<Record<string, WidgetState>>({});

    const registerWidget = useCallback((id: string, status: WidgetStatus, reason?: string) => {
        setWidgets(prev => {
            // Optimization: Only update if changed
            const current = prev[id];
            if (current && current.status === status && current.reason === reason) {
                return prev;
            }
            return {
                ...prev,
                [id]: { id, status, reason, lastUpdated: Date.now() }
            };
        });
    }, []);

    const value = useMemo(() => ({ widgets, registerWidget }), [widgets, registerWidget]);

    return (
        <WidgetRegistryContext.Provider value={value}>
            {children}
        </WidgetRegistryContext.Provider>
    );
};

export const useWidgetRegistry = () => {
    const ctx = useContext(WidgetRegistryContext);
    if (!ctx) throw new Error("useWidgetRegistry must be used within WidgetRegistryProvider");
    return ctx;
};

// Hook for individual widgets to report their status
export const useWidgetRegistration = (id: string) => {
    const { registerWidget } = useWidgetRegistry();
    // Helper to report status
    const reportStatus = useCallback((status: WidgetStatus, reason?: string) => {
        registerWidget(id, status, reason);
    }, [id, registerWidget]);

    return { reportStatus };
};
