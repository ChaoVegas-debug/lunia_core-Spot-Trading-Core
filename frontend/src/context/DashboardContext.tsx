import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

export type ToastType = 'INFO' | 'SUCCESS' | 'WARNING' | 'ERROR';

export interface ToastMessage {
    id: string;
    type: ToastType;
    title?: string;
    message: string;
    duration?: number;
}

interface DashboardContextType {
    toasts: ToastMessage[];
    addToast: (msg: Omit<ToastMessage, 'id'>) => void;
    removeToast: (id: string) => void;

    // Global Diagnostics State
    showDiagnostics: boolean;
    toggleDiagnostics: () => void;

    // Wiring Inspector (Last API Calls)
    apiCalls: { id: string, endpoint: string, status: number, ts: number }[];
    logApiCall: (endpoint: string, status: number) => void;
}

const DashboardContext = createContext<DashboardContextType | undefined>(undefined);

export const DashboardProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [toasts, setToasts] = useState<ToastMessage[]>([]);
    const [showDiagnostics, setShowDiagnostics] = useState(false);
    const [apiCalls, setApiCalls] = useState<{ id: string, endpoint: string, status: number, ts: number }[]>([]);

    const addToast = useCallback((msg: Omit<ToastMessage, 'id'>) => {
        const id = crypto.randomUUID();
        const newToast = { ...msg, id };
        setToasts(prev => [...prev, newToast]);

        if (msg.duration !== 0) {
            setTimeout(() => {
                setToasts(prev => prev.filter(t => t.id !== id));
            }, msg.duration || 5000);
        }
    }, []);

    const removeToast = useCallback((id: string) => {
        setToasts(prev => prev.filter(t => t.id !== id));
    }, []);

    const toggleDiagnostics = useCallback(() => setShowDiagnostics(prev => !prev), []);

    const logApiCall = useCallback((endpoint: string, status: number) => {
        const entry = { id: crypto.randomUUID(), endpoint, status, ts: Date.now() };
        setApiCalls(prev => [entry, ...prev].slice(0, 10)); // Keep last 10
    }, []);

    return (
        <DashboardContext.Provider value={{
            toasts,
            addToast,
            removeToast,
            showDiagnostics,
            toggleDiagnostics,
            apiCalls,
            logApiCall
        }}>
            {children}
            <ToastContainer toasts={toasts} onRemove={removeToast} />
            {showDiagnostics && <WiringDiagnosticsPanel calls={apiCalls} />}
        </DashboardContext.Provider>
    );
};

export const useDashboard = () => {
    const context = useContext(DashboardContext);
    if (!context) throw new Error("useDashboard must be used within DashboardProvider");
    return context;
};

// --- INTERNAL COMPONENTS ---

const ToastContainer: React.FC<{ toasts: ToastMessage[], onRemove: (id: string) => void }> = ({ toasts, onRemove }) => {
    return (
        <div style={{
            position: 'fixed',
            bottom: '24px',
            right: '24px',
            zIndex: 9999,
            display: 'flex',
            flexDirection: 'column',
            gap: '12px'
        }}>
            {toasts.map(t => (
                <div key={t.id} className={`toast toast-${t.type.toLowerCase()}`} style={{
                    minWidth: '300px',
                    padding: '16px',
                    borderRadius: '4px',
                    background: '#1a1a1a',
                    borderLeft: `4px solid ${getColor(t.type)}`,
                    boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
                    color: 'white',
                    animation: 'slideIn 0.3s ease-out'
                }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                        <div>
                            {t.title && <strong style={{ display: 'block', marginBottom: '4px' }}>{t.title}</strong>}
                            <span style={{ fontSize: '0.9em', opacity: 0.9 }}>{t.message}</span>
                        </div>
                        <button
                            onClick={() => onRemove(t.id)}
                            style={{ background: 'none', border: 'none', color: '#666', cursor: 'pointer', marginLeft: '12px' }}
                        >
                            ✕
                        </button>
                    </div>
                </div>
            ))}
        </div>
    );
};

const WiringDiagnosticsPanel: React.FC<{ calls: any[] }> = ({ calls }) => {
    return (
        <div style={{
            position: 'fixed',
            bottom: '24px',
            left: '24px',
            width: '320px',
            background: 'rgba(0,0,0,0.9)',
            border: '1px solid #333',
            borderRadius: '4px',
            zIndex: 9998,
            fontFamily: 'monospace',
            color: '#0f0'
        }}>
            <div style={{ padding: '8px', borderBottom: '1px solid #333', display: 'flex', justifyContent: 'space-between' }}>
                <strong>🔌 Wiring Diagnostics</strong>
            </div>
            <div style={{ padding: '8px', maxHeight: '200px', overflowY: 'auto', fontSize: '10px' }}>
                {calls.length === 0 && <div className="muted">No API calls checked yet.</div>}
                {calls.map(c => (
                    <div key={c.id} style={{ marginBottom: '4px', display: 'flex', justifyContent: 'space-between' }}>
                        <span>{new Date(c.ts).toLocaleTimeString().split(' ')[0]}</span>
                        <span style={{ flex: 1, margin: '0 8px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {c.endpoint}
                        </span>
                        <span style={{ color: c.status >= 400 ? 'red' : 'inherit' }}>{c.status}</span>
                    </div>
                ))}
            </div>
        </div>
    );
}

function getColor(type: ToastType) {
    switch (type) {
        case 'SUCCESS': return '#22c55e';
        case 'WARNING': return '#eab308';
        case 'ERROR': return '#ef4444';
        default: return '#3b82f6';
    }
}
