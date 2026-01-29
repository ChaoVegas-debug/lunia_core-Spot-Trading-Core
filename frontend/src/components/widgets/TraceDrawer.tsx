/**
 * TRACE DRAWER — REAL IMPLEMENTATION
 * 
 * Phase F3: Forensic event log for operator visibility.
 * 
 * Subscribes to runtime event bus (EVIDENCE | NET | MUTATION | SYSTEM).
 * Dense table with filters, color-coded severity, expandable JSON payloads.
 * Persists filter state via useLocalStorageState.
 * 
 * Replaces F1/F2 stub.
 */

import React, { useState, useEffect, useRef } from 'react';
import { eventBus, RuntimeEvent } from '../../lib/runtime/eventBus';
import { useLocalStorageState } from '../../hooks/useLocalStorageState';

type FilterSeverity = 'ALL' | 'LOW' | 'MED' | 'HIGH' | 'CRITICAL';

export const TraceDrawer: React.FC = () => {
    const [events, setEvents] = useState<RuntimeEvent[]>([]);
    const [expandedIdx, setExpandedIdx] = useState<number | null>(null);
    const [autoScroll, setAutoScroll] = useLocalStorageState('cockpit:trace_autoscroll', true);
    const [isOpen, setIsOpen] = useLocalStorageState('cockpit:trace_open', true); // REAL toggle with persistence
    const [criticalCount, setCriticalCount] = useState(0);
    const scrollRef = useRef<HTMLDivElement>(null);

    // Filters (persisted)
    const [errorsOnly, setErrorsOnly] = useLocalStorageState('cockpit:trace_errors_only', false);
    const [airlockOnly, setAirlockOnly] = useLocalStorageState('cockpit:trace_airlock_only', false);
    const [netOnly, setNetOnly] = useLocalStorageState('cockpit:trace_net_only', false);
    const [evidenceOnly, setEvidenceOnly] = useLocalStorageState('cockpit:trace_evidence_only', false);
    const [severityFilter, setSeverityFilter] = useLocalStorageState<FilterSeverity>('cockpit:trace_severity', 'ALL');
    const [searchText, setSearchText] = useState('');

    // Subscribe to event bus + critical auto-focus
    useEffect(() => {
        // Load initial buffer
        setEvents(eventBus.getBuffer() as RuntimeEvent[]);

        // Subscribe to new events
        const unsubscribe = eventBus.subscribe((event) => {
            setEvents(prev => [event, ...prev].slice(0, 200)); // Keep last 200

            // Phase F3.3: Critical auto-focus
            const isCritical = event.sev === 'CRITICAL' || event.sev === 'HIGH' ||
                ['NET_ERROR', 'UI_STALLED', 'SYSTEM_SAFETY_ACTION'].includes(event.name);

            if (isCritical) {
                if (autoScroll && isOpen) {
                    // Scroll to newest (top of list)
                    setTimeout(() => {
                        if (scrollRef.current) {
                            scrollRef.current.scrollTop = 0;
                        }
                    }, 100);
                } else {
                    // Increment badge counter
                    setCriticalCount(prev => prev + 1);
                }
            }
        });

        return unsubscribe;
    }, [autoScroll, isOpen]);

    // Clear critical counter when opened
    useEffect(() => {
        if (isOpen) setCriticalCount(0);
    }, [isOpen]);

    // Apply filters
    const filteredEvents = events.filter(evt => {
        // Errors only
        if (errorsOnly && (!evt.error_type && evt.sev !== 'CRITICAL' && evt.sev !== 'HIGH')) {
            return false;
        }

        // Airlock only
        if (airlockOnly && evt.kind !== 'EVIDENCE' && !evt.name.includes('AIRLOCK')) {
            return false;
        }

        // NET only
        if (netOnly && evt.kind !== 'NET') {
            return false;
        }

        // Evidence only (Phase F3.3)
        if (evidenceOnly && evt.kind !== 'EVIDENCE') {
            return false;
        }

        // Severity filter
        if (severityFilter !== 'ALL' && evt.sev !== severityFilter) {
            return false;
        }

        // Text search (endpoint, name, intent_id)
        if (searchText) {
            const lower = searchText.toLowerCase();
            const matches =
                evt.endpoint?.toLowerCase().includes(lower) ||
                evt.name.toLowerCase().includes(lower) ||
                evt.intent_id?.toLowerCase().includes(lower);
            if (!matches) return false;
        }

        return true;
    });

    // Color coding
    const getSevColor = (sev: string): string => {
        switch (sev) {
            case 'CRITICAL': return '#dc2626';
            case 'HIGH': return '#f59e0b';
            case 'MED': return '#f59e0b';
            case 'LOW': return '#10b981';
            default: return '#888';
        }
    };

    const getKindColor = (kind: string, name: string): string => {
        if (kind === 'NET' && name === 'NET_ERROR') return '#dc2626';
        if (kind === 'NET' && name === 'NET_RECOVERED') return '#10b981';
        if (kind === 'EVIDENCE' || name.includes('AIRLOCK')) return '#3b82f6';
        if (name.includes('EXECUTE') && name.includes('RESPONSE')) return '#10b981';
        return '#888';
    };

    // Format timestamp
    const formatTime = (ts: number): string => {
        const d = new Date(ts);
        return d.toLocaleTimeString('en-US', { hour12: false });
    };

    // Truncate text
    const truncate = (text: string | undefined, len: number): string => {
        if (!text) return '-';
        return text.length > len ? text.slice(0, len) + '...' : text;
    };

    return (
        <div style={{
            height: isOpen ? '100%' : '36px', // Collapsed or full height
            display: 'flex',
            flexDirection: 'column',
            background: 'var(--bg-panel)',
            color: 'var(--text-primary)',
            overflow: 'hidden',
            transition: 'height 0.2s ease',
        }}>
            {/* Header: Toggle + Filters */}
            <div style={{
                padding: '8px 12px',
                borderBottom: '1px solid var(--border-color)',
                display: 'flex',
                gap: '12px',
                alignItems: 'center',
                fontSize: '10px',
                flexShrink: 0,
                cursor: isOpen ? 'default' : 'pointer',
            }}
                onClick={() => !isOpen && setIsOpen(true)} // Click header when closed to open
            >
                {/* Toggle chevron */}
                <button
                    onClick={(e) => {
                        e.stopPropagation();
                        setIsOpen(!isOpen);
                    }}
                    style={{
                        background: 'transparent',
                        border: 'none',
                        color: 'var(--text-primary)',
                        fontSize: '12px',
                        cursor: 'pointer',
                        padding: '4px',
                    }}
                    title={isOpen ? 'Collapse drawer' : 'Expand drawer'}
                >
                    {isOpen ? '▼' : '▶'}
                </button>

                <span style={{ fontWeight: 'bold' }}>TRACE DRAWER</span>

                {/* Badge: only show when closed */}
                {!isOpen && criticalCount > 0 && (
                    <div
                        onClick={(e) => {
                            e.stopPropagation();
                            setIsOpen(true); // Click badge to open
                        }}
                        style={{
                            background: '#dc2626',
                            color: '#fff',
                            padding: '4px 8px',
                            borderRadius: '3px',
                            fontSize: '9px',
                            fontWeight: 'bold',
                            animation: 'pulse 2s infinite',
                            cursor: 'pointer',
                        }}
                    >
                        NEW CRITICAL ({criticalCount})
                    </div>
                )}

                {/* Filters: hide when closed */}
                {isOpen && (<>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
                        <input
                            type="checkbox"
                            checked={errorsOnly}
                            onChange={(e) => setErrorsOnly(e.target.checked)}
                        />
                        Errors only
                    </label>

                    <label style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
                        <input
                            type="checkbox"
                            checked={airlockOnly}
                            onChange={(e) => setAirlockOnly(e.target.checked)}
                        />
                        Airlock only
                    </label>

                    <label style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
                        <input
                            type="checkbox"
                            checked={netOnly}
                            onChange={(e) => setNetOnly(e.target.checked)}
                        />
                        NET only
                    </label>

                    {/* Phase F3.3: Evidence filter */}
                    <label style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
                        <input
                            type="checkbox"
                            checked={evidenceOnly}
                            onChange={(e) => setEvidenceOnly(e.target.checked)}
                        />
                        <span style={{ color: '#3b82f6' }}>Evidence</span>
                    </label>

                    {/* Severity dropdown */}
                    <select
                        value={severityFilter}
                        onChange={(e) => setSeverityFilter(e.target.value as FilterSeverity)}
                        style={{
                            background: 'var(--bg-primary)',
                            color: 'var(--text-primary)',
                            border: '1px solid var(--border-color)',
                            padding: '4px',
                            fontSize: '10px',
                            borderRadius: '2px',
                        }}
                    >
                        <option value="ALL">All Severity</option>
                        <option value="LOW">LOW</option>
                        <option value="MED">MED</option>
                        <option value="HIGH">HIGH</option>
                        <option value="CRITICAL">CRITICAL</option>
                    </select>

                    {/* Search */}
                    <input
                        type="text"
                        placeholder="Search endpoint/name/intent..."
                        value={searchText}
                        onChange={(e) => setSearchText(e.target.value)}
                        style={{
                            background: 'var(--bg-primary)',
                            color: 'var(--text-primary)',
                            border: '1px solid var(--border-color)',
                            padding: '4px 8px',
                            fontSize: '10px',
                            borderRadius: '2px',
                            flex: 1,
                            minWidth: '200px',
                        }}
                    />

                    {/* Auto-scroll toggle */}
                    <label style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer', marginLeft: 'auto' }}>
                        <input
                            type="checkbox"
                            checked={autoScroll}
                            onChange={(e) => setAutoScroll(e.target.checked)}
                        />
                        Auto-scroll
                    </label>

                    {/* Event count */}
                    <span style={{ color: '#888', fontFamily: 'monospace' }}>
                        {filteredEvents.length} events
                    </span>

                    {/* Phase F3.3: NEW CRITICAL badge */}
                    {criticalCount > 0 && (
                        <div style={{
                            background: '#dc2626',
                            color: '#fff',
                            padding: '4px 8px',
                            borderRadius: '3px',
                            fontSize: '9px',
                            fontWeight: 'bold',
                            animation: 'pulse 2s infinite',
                        }}>
                            NEW CRITICAL ({criticalCount})
                        </div>
                    )}
                </>)}
            </div>

            {/* Table: only render when open */}
            {isOpen && (
                <div
                    ref={scrollRef}
                    style={{
                        flex: 1,
                        overflow: 'auto',
                        fontSize: '10px',
                        fontFamily: 'monospace',
                    }}>
                    {filteredEvents.length === 0 ? (
                        <div style={{ padding: '2rem', textAlign: 'center', color: '#666' }}>
                            No events to display
                        </div>
                    ) : (
                        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                            <thead style={{
                                position: 'sticky',
                                top: 0,
                                background: 'var(--bg-panel)',
                                borderBottom: '1px solid var(--border-color)',
                            }}>
                                <tr>
                                    <th style={{ padding: '6px', textAlign: 'left' }}>TS</th>
                                    <th style={{ padding: '6px', textAlign: 'left' }}>SEV</th>
                                    <th style={{ padding: '6px', textAlign: 'left' }}>KIND</th>
                                    <th style={{ padding: '6px', textAlign: 'left' }}>NAME</th>
                                    <th style={{ padding: '6px', textAlign: 'left' }}>EP</th>
                                    <th style={{ padding: '6px', textAlign: 'right' }}>STATUS</th>
                                    <th style={{ padding: '6px', textAlign: 'right' }}>LAT</th>
                                    <th style={{ padding: '6px', textAlign: 'left' }}>REQ</th>
                                    <th style={{ padding: '6px', textAlign: 'left' }}>INTENT</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filteredEvents.map((evt, idx) => (
                                    <React.Fragment key={`${evt.ts}-${idx}`}>
                                        <tr
                                            onClick={() => setExpandedIdx(expandedIdx === idx ? null : idx)}
                                            style={{
                                                borderBottom: '1px solid rgba(255,255,255,0.05)',
                                                cursor: 'pointer',
                                                background: expandedIdx === idx ? 'rgba(255,255,255,0.05)' : 'transparent',
                                            }}
                                        >
                                            <td style={{ padding: '6px', color: '#888' }}>
                                                {formatTime(evt.ts)}
                                            </td>
                                            <td style={{
                                                padding: '6px',
                                                color: getSevColor(evt.sev),
                                                fontWeight: 'bold',
                                            }}>
                                                {evt.sev}
                                            </td>
                                            <td style={{ padding: '6px', color: '#aaa' }}>
                                                {evt.kind}
                                            </td>
                                            <td style={{
                                                padding: '6px',
                                                color: getKindColor(evt.kind, evt.name),
                                            }}>
                                                {evt.name}
                                            </td>
                                            <td style={{ padding: '6px', color: '#bbb' }}>
                                                {truncate(evt.endpoint, 30)}
                                            </td>
                                            <td style={{
                                                padding: '6px',
                                                textAlign: 'right',
                                                color: evt.http_status
                                                    ? (evt.http_status >= 500 ? '#dc2626' : evt.http_status >= 400 ? '#f59e0b' : '#10b981')
                                                    : '#666',
                                            }}>
                                                {evt.http_status || '-'}
                                            </td>
                                            <td style={{ padding: '6px', textAlign: 'right', color: '#888' }}>
                                                {evt.latency_ms ? `${evt.latency_ms}ms` : '-'}
                                            </td>
                                            <td style={{ padding: '6px', color: '#888' }}>
                                                {truncate(evt.req_id, 12)}
                                            </td>
                                            <td style={{ padding: '6px', color: '#888' }}>
                                                {truncate(evt.intent_id, 12)}
                                            </td>
                                        </tr>

                                        {/* Expanded row: JSON payload */}
                                        {expandedIdx === idx && (
                                            <tr>
                                                <td colSpan={9} style={{
                                                    padding: '12px',
                                                    background: '#0a0a0a',
                                                    borderBottom: '1px solid var(--border-color)',
                                                }}>
                                                    <div style={{ fontSize: '9px', marginBottom: '8px', color: '#888' }}>
                                                        EVENT PAYLOAD:
                                                    </div>
                                                    <pre style={{
                                                        margin: 0,
                                                        fontSize: '9px',
                                                        color: '#10b981',
                                                        maxHeight: '300px',
                                                        overflow: 'auto',
                                                        whiteSpace: 'pre-wrap',
                                                        wordBreak: 'break-all',
                                                    }}>
                                                        {JSON.stringify(evt, null, 2)}
                                                    </pre>
                                                </td>
                                            </tr>
                                        )}
                                    </React.Fragment>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            )}
        </div>
    );
};
