/**
 * EXECUTION JOURNAL MODAL - DUAL-PANE REASONING DISPLAY (Phase 7.5)
 * 
 * GOVERNANCE:
 * - Shows deterministic reasoning (PRIMARY) vs AI analysis (SECONDARY)
 * - Visual conflict indicator when AI disagrees with core
 * - Fail-closed rendering (survive missing AI data)
 * - Read-only display, no execution authority
 * 
 * PURPOSE:
 * Answer the question "WHY did this signal happen?" with full provenance.
 * 
 * LAYOUT:
 * LEFT: Core deterministic reasoning (TRUTH)
 * RIGHT: AI synthetic reasoning (SECONDARY)
 */

import React, { useEffect, useState } from 'react';
import { fetchJSON } from '../../lib/api/normalizeResponse';
import { endpoints } from '../../lib/runtime/endpoints';

interface AIAnalysis {
    id: string;
    summary: string | null;
    risk_flags: string[];
    confirmation: boolean | null;
    confidence_score: number | null;
    confidence_reason: string | null;
    conflicts_with_core: boolean;
    conflict_reason: string | null;
    invalid_if: string[];
    model_revision: string;
    latency_ms: number | null;
    cost_usd: number;
    operator_feedback: string | null;
    created_at: string;
}

interface SignalDetail {
    id: string;
    strategy_id: string;
    symbol: string;
    signal_type: string;
    confidence: number;
    timestamp: string;
    market_context: Record<string, any>;
    risk_filters_applied: Record<string, any>;
    deterministic_reasoning: string | null;
    created_at: string;
    ai_analysis: AIAnalysis | null;
}

interface ExecutionJournalModalProps {
    open: boolean;
    onClose: () => void;
    signalEventId: string;
}

export const ExecutionJournalModal: React.FC<ExecutionJournalModalProps> = ({
    open,
    onClose,
    signalEventId
}) => {
    const [signal, setSignal] = useState<SignalDetail | null>(null);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (open && signalEventId) {
            fetchSignalDetail();
        }
    }, [open, signalEventId]);

    const fetchSignalDetail = async () => {
        setLoading(true);
        setError(null);

        try {
            const data = await fetchJSON<SignalDetail>(
                `${endpoints.api_base}/journal/signal/${signalEventId}`
            );
            setSignal(data);
        } catch (err) {
            console.error('[ExecutionJournalModal] Failed to fetch signal:', err);
            setError('Failed to load signal detail');
        } finally {
            setLoading(false);
        }
    };

    if (!open) return null;

    const hasConflict = signal?.ai_analysis?.conflicts_with_core;
    const borderColor = hasConflict ? '#fb923c' : '#333';

    return (
        <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.85)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
            padding: '2rem'
        }}>
            <div style={{
                background: '#0a0a0a',
                border: `2px solid ${borderColor}`,
                borderRadius: '6px',
                maxWidth: '1200px',
                width: '100%',
                maxHeight: '80vh',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden'
            }}>
                {/* HEADER */}
                <div style={{
                    padding: '1rem',
                    borderBottom: `1px solid ${borderColor}`,
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center'
                }}>
                    <div>
                        <div style={{ fontSize: '14px', fontWeight: 'bold', marginBottom: '0.25rem' }}>
                            🧠 EXECUTION JOURNAL
                        </div>
                        {signal && (
                            <div style={{ fontSize: '10px', color: '#888', fontFamily: 'monospace' }}>
                                {signal.symbol} • {signal.signal_type} • {signal.strategy_id}
                            </div>
                        )}
                    </div>
                    <button
                        onClick={onClose}
                        style={{
                            padding: '0.5rem 1rem',
                            fontSize: '11px',
                            fontWeight: 'bold',
                            background: '#1a1a1a',
                            border: '1px solid #333',
                            color: '#ccc',
                            borderRadius: '3px',
                            cursor: 'pointer'
                        }}
                    >
                        CLOSE
                    </button>
                </div>

                {/* CONFLICT WARNING */}
                {hasConflict && (
                    <div style={{
                        padding: '0.75rem 1rem',
                        background: 'rgba(251, 146, 60, 0.15)',
                        borderBottom: '1px solid #fb923c',
                        fontSize: '11px',
                        color: '#fb923c',
                        fontWeight: 'bold',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem'
                    }}>
                        <span>⚠️</span>
                        <div>
                            <div>SECONDARY — CORE DISAGREES</div>
                            {signal?.ai_analysis?.conflict_reason && (
                                <div style={{ fontWeight: 'normal', fontSize: '10px', marginTop: '0.25rem' }}>
                                    {signal.ai_analysis.conflict_reason}
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* CONTENT */}
                <div style={{ flex: 1, overflow: 'auto' }}>
                    {loading ? (
                        <div style={{
                            padding: '2rem',
                            textAlign: 'center',
                            color: '#888',
                            fontSize: '12px'
                        }}>
                            Loading signal detail...
                        </div>
                    ) : error ? (
                        <div style={{
                            padding: '2rem',
                            textAlign: 'center',
                            color: '#dc2626',
                            fontSize: '12px'
                        }}>
                            {error}
                        </div>
                    ) : signal ? (
                        <div style={{
                            display: 'grid',
                            gridTemplateColumns: '1fr 1fr',
                            gap: '1px',
                            background: '#333',
                            minHeight: '100%'
                        }}>
                            {/* LEFT PANE - DETERMINISTIC (PRIMARY) */}
                            <div style={{
                                background: '#0a0a0a',
                                padding: '1rem',
                                overflow: 'auto'
                            }}>
                                <div style={{
                                    fontSize: '11px',
                                    fontWeight: 'bold',
                                    textTransform: 'uppercase',
                                    marginBottom: '0.75rem',
                                    color: '#10b981',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '0.5rem'
                                }}>
                                    <span>⚙️</span>
                                    DETERMINISTIC CORE (PRIMARY)
                                </div>

                                {/* Reasoning */}
                                <div style={{ marginBottom: '1rem' }}>
                                    <div style={{
                                        fontSize: '9px',
                                        color: '#888',
                                        marginBottom: '0.25rem',
                                        textTransform: 'uppercase',
                                        fontWeight: 'bold'
                                    }}>
                                        Reasoning
                                    </div>
                                    <div style={{
                                        fontSize: '11px',
                                        lineHeight: '1.5',
                                        color: '#ccc',
                                        padding: '0.5rem',
                                        background: '#1a1a1a',
                                        border: '1px solid #333',
                                        borderRadius: '3px'
                                    }}>
                                        {signal.deterministic_reasoning || 'No reasoning provided'}
                                    </div>
                                </div>

                                {/* Risk Filters */}
                                <div style={{ marginBottom: '1rem' }}>
                                    <div style={{
                                        fontSize: '9px',
                                        color: '#888',
                                        marginBottom: '0.25rem',
                                        textTransform: 'uppercase',
                                        fontWeight: 'bold'
                                    }}>
                                        Risk Filters Applied
                                    </div>
                                    <div style={{
                                        fontSize: '10px',
                                        fontFamily: 'monospace',
                                        color: '#ccc',
                                        padding: '0.5rem',
                                        background: '#1a1a1a',
                                        border: '1px solid #333',
                                        borderRadius: '3px',
                                        maxHeight: '200px',
                                        overflow: 'auto'
                                    }}>
                                        <pre style={{ margin: 0, fontSize: '9px' }}>
                                            {JSON.stringify(signal.risk_filters_applied || {}, null, 2)}
                                        </pre>
                                    </div>
                                </div>

                                {/* Market Context */}
                                <div style={{ marginBottom: '1rem' }}>
                                    <div style={{
                                        fontSize: '9px',
                                        color: '#888',
                                        marginBottom: '0.25rem',
                                        textTransform: 'uppercase',
                                        fontWeight: 'bold'
                                    }}>
                                        Market Context Snapshot
                                    </div>
                                    <div style={{
                                        fontSize: '10px',
                                        fontFamily: 'monospace',
                                        color: '#ccc',
                                        padding: '0.5rem',
                                        background: '#1a1a1a',
                                        border: '1px solid #333',
                                        borderRadius: '3px',
                                        maxHeight: '200px',
                                        overflow: 'auto'
                                    }}>
                                        <pre style={{ margin: 0, fontSize: '9px' }}>
                                            {JSON.stringify(signal.market_context || {}, null, 2)}
                                        </pre>
                                    </div>
                                </div>

                                {/* Metadata */}
                                <div>
                                    <div style={{
                                        fontSize: '9px',
                                        color: '#888',
                                        marginBottom: '0.25rem',
                                        textTransform: 'uppercase',
                                        fontWeight: 'bold'
                                    }}>
                                        Metadata
                                    </div>
                                    <div style={{
                                        fontSize: '10px',
                                        color: '#888',
                                        fontFamily: 'monospace',
                                        lineHeight: '1.6'
                                    }}>
                                        <div>Signal ID: {signal.id}</div>
                                        <div>Timestamp: {signal.timestamp}</div>
                                        <div>Confidence: {(signal.confidence * 100).toFixed(1)}%</div>
                                    </div>
                                </div>
                            </div>

                            {/* RIGHT PANE - AI ANALYSIS (SECONDARY) */}
                            <div style={{
                                background: '#0a0a0a',
                                padding: '1rem',
                                overflow: 'auto',
                                borderLeft: hasConflict ? '2px solid #fb923c' : 'none'
                            }}>
                                <div style={{
                                    fontSize: '11px',
                                    fontWeight: 'bold',
                                    textTransform: 'uppercase',
                                    marginBottom: '0.75rem',
                                    color: signal.ai_analysis ? '#3b82f6' : '#666',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '0.5rem'
                                }}>
                                    <span>🧠</span>
                                    AI ANALYSIS (SECONDARY)
                                </div>

                                {signal.ai_analysis ? (
                                    <>
                                        {/* Summary */}
                                        <div style={{ marginBottom: '1rem' }}>
                                            <div style={{
                                                fontSize: '9px',
                                                color: '#888',
                                                marginBottom: '0.25rem',
                                                textTransform: 'uppercase',
                                                fontWeight: 'bold'
                                            }}>
                                                Summary
                                            </div>
                                            <div style={{
                                                fontSize: '11px',
                                                lineHeight: '1.5',
                                                color: '#ccc',
                                                padding: '0.5rem',
                                                background: '#1a1a1a',
                                                border: '1px solid #333',
                                                borderRadius: '3px'
                                            }}>
                                                {signal.ai_analysis.summary || 'No summary provided'}
                                            </div>
                                        </div>

                                        {/* Confidence */}
                                        {typeof signal.ai_analysis.confidence_score === 'number' && (
                                            <div style={{ marginBottom: '1rem' }}>
                                                <div style={{
                                                    fontSize: '9px',
                                                    color: '#888',
                                                    marginBottom: '0.25rem',
                                                    textTransform: 'uppercase',
                                                    fontWeight: 'bold'
                                                }}>
                                                    AI Confidence
                                                </div>
                                                <div style={{
                                                    width: '100%',
                                                    height: '8px',
                                                    background: '#333',
                                                    borderRadius: '3px',
                                                    overflow: 'hidden',
                                                    marginBottom: '0.25rem'
                                                }}>
                                                    <div style={{
                                                        width: `${signal.ai_analysis.confidence_score * 100}%`,
                                                        height: '100%',
                                                        background: signal.ai_analysis.confidence_score > 0.7 ? '#10b981' : signal.ai_analysis.confidence_score > 0.4 ? '#f59e0b' : '#dc2626'
                                                    }} />
                                                </div>
                                                <div style={{ fontSize: '10px', color: '#666' }}>
                                                    {(signal.ai_analysis.confidence_score * 100).toFixed(1)}%
                                                    {signal.ai_analysis.confidence_reason && ` — ${signal.ai_analysis.confidence_reason}`}
                                                </div>
                                            </div>
                                        )}

                                        {/* Risk Flags */}
                                        {Array.isArray(signal.ai_analysis.risk_flags) && signal.ai_analysis.risk_flags.length > 0 && (
                                            <div style={{ marginBottom: '1rem' }}>
                                                <div style={{
                                                    fontSize: '9px',
                                                    color: '#888',
                                                    marginBottom: '0.25rem',
                                                    textTransform: 'uppercase',
                                                    fontWeight: 'bold'
                                                }}>
                                                    Risk Flags
                                                </div>
                                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem' }}>
                                                    {signal.ai_analysis.risk_flags.map((flag, idx) => (
                                                        <span key={idx} style={{
                                                            fontSize: '9px',
                                                            padding: '3px 6px',
                                                            background: '#dc2626',
                                                            color: '#fff',
                                                            borderRadius: '2px',
                                                            fontWeight: 'bold'
                                                        }}>
                                                            {flag}
                                                        </span>
                                                    ))}
                                                </div>
                                            </div>
                                        )}

                                        {/* Invalid If */}
                                        {Array.isArray(signal.ai_analysis.invalid_if) && signal.ai_analysis.invalid_if.length > 0 && (
                                            <div style={{ marginBottom: '1rem' }}>
                                                <div style={{
                                                    fontSize: '9px',
                                                    color: '#888',
                                                    marginBottom: '0.25rem',
                                                    textTransform: 'uppercase',
                                                    fontWeight: 'bold'
                                                }}>
                                                    Invalidation Conditions
                                                </div>
                                                <ul style={{
                                                    margin: 0,
                                                    paddingLeft: '1.5rem',
                                                    fontSize: '10px',
                                                    color: '#ccc',
                                                    lineHeight: '1.6'
                                                }}>
                                                    {signal.ai_analysis.invalid_if.map((condition, idx) => (
                                                        <li key={idx}>{condition}</li>
                                                    ))}
                                                </ul>
                                            </div>
                                        )}

                                        {/* Provenance */}
                                        <div style={{
                                            paddingTop: '0.75rem',
                                            borderTop: '1px solid #333'
                                        }}>
                                            <div style={{
                                                fontSize: '9px',
                                                color: '#888',
                                                marginBottom: '0.25rem',
                                                textTransform: 'uppercase',
                                                fontWeight: 'bold'
                                            }}>
                                                Provenance
                                            </div>
                                            <div style={{
                                                display: 'flex',
                                                flexWrap: 'wrap',
                                                gap: '0.25rem'
                                            }}>
                                                <span style={{
                                                    fontSize: '9px',
                                                    padding: '2px 4px',
                                                    background: '#1a1a1a',
                                                    border: '1px solid #333',
                                                    borderRadius: '2px',
                                                    color: '#888'
                                                }}>
                                                    {signal.ai_analysis.model_revision}
                                                </span>
                                                {typeof signal.ai_analysis.latency_ms === 'number' && (
                                                    <span style={{
                                                        fontSize: '9px',
                                                        padding: '2px 4px',
                                                        background: '#1a1a1a',
                                                        border: '1px solid #333',
                                                        borderRadius: '2px',
                                                        color: '#888'
                                                    }}>
                                                        {signal.ai_analysis.latency_ms}ms
                                                    </span>
                                                )}
                                                <span style={{
                                                    fontSize: '9px',
                                                    padding: '2px 4px',
                                                    background: '#1a1a1a',
                                                    border: '1px solid #333',
                                                    borderRadius: '2px',
                                                    color: '#888'
                                                }}>
                                                    ${signal.ai_analysis.cost_usd.toFixed(6)}
                                                </span>
                                            </div>
                                        </div>
                                    </>
                                ) : (
                                    <div style={{
                                        padding: '2rem',
                                        textAlign: 'center',
                                        color: '#666',
                                        fontSize: '11px',
                                        lineHeight: '1.6'
                                    }}>
                                        <div style={{ fontSize: '20px', marginBottom: '0.5rem' }}>🔒</div>
                                        <div style={{ fontWeight: 'bold', marginBottom: '0.25rem' }}>
                                            NO AI ANALYSIS
                                        </div>
                                        <div style={{ fontSize: '10px' }}>
                                            Shadow Mode or analysis pending
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    ) : null}
                </div>
            </div>
        </div>
    );
};
