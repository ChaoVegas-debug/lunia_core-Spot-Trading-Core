import React, { useMemo, useState } from 'react';
import { usePolledResource } from '../../hooks/usePolledResource';
import { useAuth } from '../../hooks/useAuth';
import { getLogs } from '../../api/adapter';
import { useJournal } from '../../hooks/useJournal';
import type { LogsResponse } from '../../api/types';

export const ExecutionTimelineWidget: React.FC = () => {
    const auth = useAuth();
    const client = { role: auth.role, opsToken: auth.opsToken };
    const { entries: localEntries } = useJournal();

    const logs = usePolledResource<LogsResponse>((s) => getLogs(s, client), 3000, []);

    const [filter, setFilter] = useState<'ALL' | 'SYSTEM' | 'USER'>('ALL');

    const combinedTimeline = useMemo(() => {
        const serverLogs = logs.data?.items || [];

        // Normalize formats
        const normalizedServer = serverLogs.map(l => ({
            id: `server-${l.ts}-${l.message.substr(0, 10)}`,
            ts: l.ts,
            source: 'SYSTEM' as const,
            message: l.message,
            level: l.level
        }));

        const normalizedLocal = localEntries.map((l, i) => ({
            id: `local-${l.ts}-${i}`,
            ts: l.ts,
            source: 'USER' as const,
            message: l.action,
            details: l.details,
            level: 'INFO'
        }));

        // Merge and Sort Descending
        return [...normalizedServer, ...normalizedLocal]
            .sort((a, b) => new Date(b.ts).getTime() - new Date(a.ts).getTime())
            .filter(item => {
                if (filter === 'ALL') return true;
                return item.source === filter;
            });

    }, [logs.data, localEntries, filter]);

    return (
        <div className="card" style={{ height: '300px', display: 'flex', flexDirection: 'column' }}>
            <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3>Execution Timeline</h3>
                <div className="filter-pills small">
                    <span
                        className={filter === 'ALL' ? 'active' : ''}
                        onClick={() => setFilter('ALL')}
                    >ALL</span>
                    <span
                        className={filter === 'USER' ? 'active' : ''}
                        onClick={() => setFilter('USER')}
                    >USER</span>
                    <span
                        className={filter === 'SYSTEM' ? 'active' : ''}
                        onClick={() => setFilter('SYSTEM')}
                    >SYS</span>
                </div>
            </div>
            <div className="card-body scrollable-y">
                {combinedTimeline.length === 0 ? (
                    <div className="empty-state">No recorded activity.</div>
                ) : (
                    <div className="timeline-list">
                        {combinedTimeline.map(item => (
                            <div key={item.id} className={`timeline-item ${item.source.toLowerCase()}`}>
                                <div className="timeline-time">
                                    {new Date(item.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                                </div>
                                <div className="timeline-content">
                                    <div className="timeline-message">
                                        {item.source === 'USER' && <span className="icon-user">👤 </span>}
                                        {item.message}
                                    </div>
                                    {/* Optional: Show details or level */}
                                    {item.level === 'ERROR' && <span className="tag error">ERR</span>}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
            <style>{`
                .timeline-list {
                    display: flex;
                    flex-direction: column;
                    gap: 8px;
                }
                .timeline-item {
                    display: flex;
                    gap: 12px;
                    padding: 8px;
                    border-bottom: 1px solid var(--border-color);
                    background: rgba(255,255,255,0.02);
                }
                .timeline-item.user {
                    border-left: 3px solid var(--primary-color);
                    background: rgba(var(--primary-rgb), 0.05);
                }
                .timeline-item.system {
                    border-left: 3px solid var(--text-muted);
                }
                .timeline-time {
                    font-size: 0.75rem;
                    color: var(--text-muted);
                    min-width: 60px;
                    font-family: monospace;
                }
                .timeline-message {
                    font-size: 0.85rem;
                    color: var(--text-color);
                }
                .icon-user {
                    font-size: 0.8rem;
                    margin-right: 4px;
                }
                .filter-pills span {
                    cursor: pointer;
                    padding: 2px 6px;
                    border-radius: 4px;
                    margin-left: 4px;
                    font-size: 0.7rem;
                    background: var(--bg-deep);
                    color: var(--text-muted);
                }
                .filter-pills span.active {
                    background: var(--primary-color);
                    color: white;
                }
            `}</style>
        </div>
    );
};
