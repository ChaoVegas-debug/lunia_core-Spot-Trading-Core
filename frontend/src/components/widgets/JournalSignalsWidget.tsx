/**
 * JOURNAL SIGNALS WIDGET - EXECUTION JOURNAL DISPLAY (Phase 7.5)
 * 
 * GOVERNANCE:
 * - Read-only display of signal events from Execution Journal
 * - Fail-closed rendering (survive missing/malformed data)
 * - Shadow mode awareness
 * - 🧠 Brain icon opens ExecutionJournalModal
 * 
 * PURPOSE:
 * Display recent signal events with access to full execution journal
 * (deterministic + AI reasoning).
 */

import React, { useState } from 'react';
import { usePoller } from '../../hooks/usePoller';
import { fetchJSON } from '../../lib/api/normalizeResponse';
import { endpoints } from '../../lib/runtime/endpoints';
import { FailClosedPanel } from '../common/FailClosedPanel';
import { ProvenanceFooter } from '../common/ProvenanceFooter';
import { ExecutionJournalModal } from '../modals/ExecutionJournalModal';

interface AIAnalysisPreview {
    model_revision: string;
    conflicts_with_core: boolean;
    confidence_score: number | null;
}

interface SignalEvent {
    id: string;
    strategy_id: string;
    symbol: string;
    signal_type: string;
    confidence: number;
    timestamp: string;
    ai_analysis: AIAnalysisPreview | null;
}

interface JournalResponse {
    signals: SignalEvent[];
    count: number;
}

const getJournalSignals = async (): Promise<JournalResponse> => {
    return await fetchJSON<JournalResponse>(`${endpoints.api_base}/journal/signals?limit=20`);
};

export const JournalSignalsWidget: React.FC = () => {
    const [selectedSignalId, setSelectedSignalId] = useState<string | null>(null);
    const [showJournal, setShowJournal] = useState<boolean>(false);

    const { data, error, meta, isStale } = usePoller<JournalResponse>({
        key: 'journal_signals',
        endpoint: `${endpoints.api_base}/journal/signals`,
        fetcher: getJournalSignals,
        interval_ms: 10000, // 10s refresh
        stale_threshold_s: 15,
        pause_when_hidden: true,
    });

    const handleOpenJournal = (signalId: string) => {
        setSelectedSignalId(signalId);
        setShowJournal(true);
    };

    const handleCloseJournal = () => {
        setShowJournal(false);
        setSelectedSignalId(null);
    };

    const signals = Array.isArray(data?.signals) ? data.signals : [];
    const statusDot = error ? '🔴' : isStale ? '⚪' : '🟢';

    return (
        <div style={{
            background: 'var(--bg-panel)',
            border: '1px solid var(--border-color)',
            borderRadius: '4px',
            padding: '0.5rem',
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
        }}>
            {/* HEADER */}
            <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '0.5rem',
                paddingBottom: '0.5rem',
                borderBottom: '1px solid var(--border-color)'
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ fontSize: '12px' }}>{statusDot}</span>
                    <span style={{ fontWeight: 'bold', fontSize: '12px', textTransform: 'uppercase' }}>
                        📝 EXECUTION JOURNAL
                    </span>
                    {isStale && (
                        <span style={{
                            fontSize: '9px',
                            padding: '2px 4px',
                            background: '#f59e0b',
                            color: '#000',
                            borderRadius: '2px',
                            fontWeight: 'bold'
                        }}>
                            STALE
                        </span>
                    )}
                </div>
                <div style={{ fontSize: '10px', color: '#666' }}>
                    {signals.length} signals
                </div>
            </div>

            {/* FAIL-CLOSED PANEL */}
            <FailClosedPanel
                title="Execution Journal"
                error={error}
                meta={meta}
            >
                <div style={{
                    flex: 1,
                    overflow: 'auto',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.5rem',
                    opacity: isStale ? 0.6 : 1,
                    filter: isStale ? 'grayscale(50%)' : 'none'
                }}>
                    {signals.length === 0 ? (
                        <div style={{
                            padding: '1rem',
                            textAlign: 'center',
                            color: '#666',
                            fontSize: '11px'
                        }}>
                            No signals in execution journal
                        </div>
                    ) : (
                        signals.map(signal => {
                            const hasAI = !!signal.ai_analysis;
                            const hasConflict = signal.ai_analysis?.conflicts_with_core;
                            const time = new Date(signal.timestamp).toLocaleTimeString();

                            return (
                                <div
                                    key={signal.id}
                                    style={{
                                        background: '#1a1a1a',
                                        border: hasConflict ? '1px solid #fb923c' : '1px solid #333',
                                        borderRadius: '3px',
                                        padding: '0.5rem',
                                        fontSize: '11px',
                                        fontFamily: 'monospace',
                                        position: 'relative'
                                    }}
                                >
                                    {/* BRAIN ICON */}
                                    <button
                                        onClick={() => handleOpenJournal(signal.id)}
                                        title="View Full Reasoning"
                                        style={{
                                            position: 'absolute',
                                            top: '0.5rem',
                                            right: '0.5rem',
                                            padding: '4px 8px',
                                            fontSize: '14px',
                                            background: '#1a1a1a',
                                            border: `1px solid ${hasConflict ? '#fb923c' : hasAI ? '#3b82f6' : '#666'}`,
                                            borderRadius: '3px',
                                            cursor: 'pointer',
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            lineHeight: 1,
                                            transition: 'all 0.2s'
                                        }}
                                        onMouseEnter={(e) => {
                                            e.currentTarget.style.background = hasConflict ? '#fb923c' : hasAI ? '#3b82f6' : '#666';
                                            e.currentTarget.style.transform = 'scale(1.1)';
                                        }}
                                        onMouseLeave={(e) => {
                                            e.currentTarget.style.background = '#1a1a1a';
                                            e.currentTarget.style.transform = 'scale(1)';
                                        }}
                                    >
                                        🧠
                                    </button>

                                    {/* CONFLICT BADGE */}
                                    {hasConflict && (
                                        <div style={{
                                            fontSize: '8px',
                                            padding: '2px 4px',
                                            background: '#fb923c',
                                            color: '#000',
                                            borderRadius: '2px',
                                            fontWeight: 'bold',
                                            display: 'inline-block',
                                            marginBottom: '0.25rem'
                                        }}>
                                            ⚠️ AI CONFLICT
                                        </div>
                                    )}

                                    <div style={{
                                        display: 'flex',
                                        justifyContent: 'space-between',
                                        marginBottom: '0.25rem',
                                        fontSize: '10px',
                                        color: '#888',
                                        paddingRight: '2.5rem'
                                    }}>
                                        <span>[{time}] {signal.strategy_id}</span>
                                        {hasAI && (
                                            <span style={{ color: '#3b82f6' }}>AI ✓</span>
                                        )}
                                    </div>

                                    <div style={{
                                        marginBottom: '0.25rem',
                                        fontWeight: 'bold',
                                        fontSize: '12px',
                                        color: signal.signal_type === 'BUY' ? '#10b981' : signal.signal_type === 'SELL' ? '#dc2626' : '#888'
                                    }}>
                                        {signal.signal_type} • {signal.symbol}
                                    </div>

                                    <div style={{
                                        width: '100%',
                                        height: '6px',
                                        background: '#333',
                                        borderRadius: '3px',
                                        overflow: 'hidden'
                                    }}>
                                        <div style={{
                                            width: `${signal.confidence * 100}%`,
                                            height: '100%',
                                            background: signal.confidence > 0.7 ? '#10b981' : signal.confidence > 0.4 ? '#f59e0b' : '#dc2626'
                                        }} />
                                    </div>

                                    <div style={{ fontSize: '9px', color: '#666', marginTop: '0.25rem' }}>
                                        Core Confidence: {(signal.confidence * 100).toFixed(1)}%
                                        {hasAI && typeof signal.ai_analysis?.confidence_score === 'number' && (
                                            <span style={{ marginLeft: '0.5rem', color: '#3b82f6' }}>
                                                AI: {(signal.ai_analysis.confidence_score * 100).toFixed(1)}%
                                            </span>
                                        )}
                                    </div>
                                </div>
                            );
                        })
                    )}
                </div>
            </FailClosedPanel>

            {/* PROVENANCE FOOTER */}
            <ProvenanceFooter meta={meta} showEndpoint={false} />

            {/* EXECUTION JOURNAL MODAL */}
            {selectedSignalId && (
                <ExecutionJournalModal
                    open={showJournal}
                    onClose={handleCloseJournal}
                    signalEventId={selectedSignalId}
                />
            )}
        </div>
    );
};
