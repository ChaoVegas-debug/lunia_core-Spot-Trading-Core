
export interface JournalEvent {
    id: string;
    timestamp: string;
    type: 'MODE_CHANGE' | 'AIRLOCK' | 'DRIFT' | 'STOP' | 'VETO' | 'INTERVENTION' | 'INFO';
    message: string;
    actor: 'HUMAN' | 'AI' | 'SYSTEM';
    severity: 'INFO' | 'WARNING' | 'CRITICAL';
}

class JournalStoreService {
    private logs: JournalEvent[] = [];
    private listeners: Set<() => void> = new Set();

    constructor() {
        this.addLog('INFO', 'Client Journal Initialized', 'SYSTEM');
    }

    getLogs = () => this.logs;
    getLastEvent = () => this.logs[0];

    addLog(type: JournalEvent['type'], message: string, actor: JournalEvent['actor'] = 'HUMAN', severity: JournalEvent['severity'] = 'INFO') {
        const event: JournalEvent = {
            id: `je-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
            timestamp: new Date().toISOString(),
            type,
            message,
            actor,
            severity
        };
        this.logs.unshift(event);
        if (this.logs.length > 100) this.logs.pop();
        this.notify();
    }

    subscribe = (listener: () => void) => {
        this.listeners.add(listener);
        return () => this.listeners.delete(listener);
    };

    private notify = () => {
        this.listeners.forEach(l => l());
    };
}

export const journalStore = new JournalStoreService();
