/**
 * ADVISOR WIDGET - SYNTHETIC INTELLIGENCE SURFACE (Phase 7.5)
 * 
 * GOVERNANCE:
 * - AI has ZERO execution authority
 * - Shadow Mode awareness (badge visible)
 * - Fail-closed rendering (survive missing/malformed data)
 * - Read-only intelligence display
 * 
 * PURPOSE:
 * Make AI's secondary interpretation of deterministic signals visible,
 * auditable, and subject to operator feedback.
 * 
 * LAW 3: Fail-Closed (defensive rendering, empty states)
 * LAW 4: Provenance (model, latency, timestamp)
 */

import React, { useState } from 'react';
import { usePoller } from '../../hooks/usePoller';
import { fetchJSON } from '../../lib/api/normalizeResponse';
import { endpoints } from '../../lib/runtime/endpoints';
import { FailClosedPanel } from '../common/FailClosedPanel';
import { ProvenanceFooter } from '../common/ProvenanceFooter';

interface AIAnalysis {
    id: string;
    summary: string | null;
    risk_flags: string[];
    confirmation: boolean | null;
    confidence_score: number | null;
    confidence_reason: string | null;
    conflicts_with_core: boolean;
    conflict_reason: string | null;
    model_revision: string;
    latency_ms: number | null;
    cost_usd: number;
    operator_feedback: string | null;
    created_at: string;
}

interface SignalEvent {
    id: string;
    symbol: string;
    signal_type: string;
    confidence: number;
    timestamp: string;
    ai_analysis: AIAnalysis | null;
}

interface JournalResponse {
    signals: SignalEvent[];
    count: number;
}

const getLatestSignalWithAI = async (): Promise<AIAnalysis | null> => {
    try {
        const response = await fetchJSON<JournalResponse>(`${endpoints.api_base}/journal/signals?limit=10`);

        // Find first signal with AI analysis
        if (Array.isArray(response?.signals)) {
            for (const signal of response.signals) {
                if (signal?.ai_analysis) {
                    return signal.ai_analysis;
                }
            }
        }

        return null;
    } catch (err) {
        console.error('[AdvisorWidget] Failed to fetch AI analysis:', err);
        return null;
    }
};

const submitFeedback = async (analysisId: string, feedback: 'thumbs_up' | 'thumbs_down', comment?: string): Promise<void> => {
    try {
        await fetch(`${endpoints.api_base}/journal/feedback`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`,
            },
            body: JSON.stringify({
                analysis_id: analysisId,
                feedback,
                comment,
            }),
        });
    } catch (err) {
        console.error('[AdvisorWidget] Failed to submit feedback:', err);
    }
};

export const AdvisorWidget: React.FC = () => {
    const [feedbackComment, setFeedbackComment] = useState<string>('');
    const [showCommentBox, setShowCommentBox] = useState<boolean>(false);

    const { data: aiAnalysis, error, meta, isStale } = usePoller<AIAnalysis | null>({
        key: 'ai_advisor',
        endpoint: `${endpoints.api_base}/journal/signals?limit=10`,
        fetcher: getLatestSignalWithAI,
        interval_ms: 10000, // 10s refresh
        stale_threshold_s: 15,
        pause_when_hidden: true,
    });

    const handleFeedback = async (type: 'thumbs_up' | 'thumbs_down') => {
        if (!aiAnalysis?.id) return;

        if (type === 'thumbs_down' && !showCommentBox) {
            setShowCommentBox(true);
            return;
        }

        await submitFeedback(aiAnalysis.id, type, feedbackComment || undefined);
        setShowCommentBox(false);
        setFeedbackComment('');
    };

    const statusDot = error ? '🔴' : isStale ? '⚪' : '🟢';

    // Shadow Mode detection (if no AI analysis exists, assume shadow mode)
    const isShadowMode = !aiAnalysis;

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
                        🧠 AI ADVISOR
                    </span>
                    {isShadowMode && (
                        <span style={{
                            fontSize: '9px',
                            padding: '2px 4px',
                            background: '#fb923c',
                            color: '#000',
                            borderRadius: '2px',
                            fontWeight: 'bold'
                        }}>
                            SHADOW MODE
                        </span>
                    )}
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
            </div>

            {/* FAIL-CLOSED PANEL */}
            <FailClosedPanel
                title="AI Advisor"
                error={error}
                meta={meta}
            >
                <div style={{
                    flex: 1,
                    overflow: 'auto',
                    opacity: isStale ? 0.6 : 1,
                    filter: isStale ? 'grayscale(50%)' : 'none'
                }}>
                    {isShadowMode ? (
                        /* SHADOW MODE EMPTY STATE */
                        <div style={{
                            padding: '1rem',
                            textAlign: 'center',
                            color: '#888',
                            fontSize: '11px',
                            lineHeight: '1.6'
                        }}>
                            <div style={{ fontSize: '20px', marginBottom: '0.5rem' }}>🔒</div>
                            <div style={{ fontWeight: 'bold', marginBottom: '0.25rem' }}>
                                SHADOW MODE ACTIVE
                            </div>
                            <div style={{ fontSize: '10px', color: '#666' }}>
                                AI analysis running in background.
                                <br />
                                Not visible until verified.
                            </div>
                        </div>
                    ) : aiAnalysis ? (
                        /* AI ANALYSIS DISPLAY */
                        <div style={{ padding: '0.5rem', fontSize: '11px' }}>
                            {/* CONFLICT WARNING */}
                            {aiAnalysis.conflicts_with_core && (
                                <div style={{
                                    padding: '0.5rem',
                                    marginBottom: '0.5rem',
                                    background: 'rgba(251, 146, 60, 0.15)',
                                    border: '1px solid #fb923c',
                                    borderRadius: '3px',
                                    fontSize: '10px',
                                    color: '#fb923c',
                                    fontWeight: 'bold'
                                }}>
                                    ⚠️ SECONDARY — CORE DISAGREES
                                    {aiAnalysis.conflict_reason && (
                                        <div style={{ marginTop: '0.25rem', fontWeight: 'normal', fontSize: '9px' }}>
                                            {aiAnalysis.conflict_reason}
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* SUMMARY */}
                            <div style={{
                                marginBottom: '0.75rem',
                                lineHeight: '1.5',
                                color: '#ccc'
                            }}>
                                {aiAnalysis.summary || 'No summary provided'}
                            </div>

                            {/* RISK FLAGS */}
                            {Array.isArray(aiAnalysis.risk_flags) && aiAnalysis.risk_flags.length > 0 && (
                                <div style={{ marginBottom: '0.75rem' }}>
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
                                        {aiAnalysis.risk_flags.map((flag, idx) => (
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

                            {/* CONFIDENCE */}
                            {typeof aiAnalysis.confidence_score === 'number' && (
                                <div style={{ marginBottom: '0.75rem' }}>
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
                                        height: '6px',
                                        background: '#333',
                                        borderRadius: '3px',
                                        overflow: 'hidden',
                                        marginBottom: '0.25rem'
                                    }}>
                                        <div style={{
                                            width: `${aiAnalysis.confidence_score * 100}%`,
                                            height: '100%',
                                            background: aiAnalysis.confidence_score > 0.7 ? '#10b981' : aiAnalysis.confidence_score > 0.4 ? '#f59e0b' : '#dc2626'
                                        }} />
                                    </div>
                                    <div style={{ fontSize: '9px', color: '#666' }}>
                                        {(aiAnalysis.confidence_score * 100).toFixed(1)}%
                                        {aiAnalysis.confidence_reason && ` — ${aiAnalysis.confidence_reason}`}
                                    </div>
                                </div>
                            )}

                            {/* PROVENANCE CHIPS */}
                            <div style={{
                                display: 'flex',
                                flexWrap: 'wrap',
                                gap: '0.25rem',
                                marginBottom: '0.75rem',
                                paddingTop: '0.5rem',
                                borderTop: '1px solid #333'
                            }}>
                                <span style={{
                                    fontSize: '9px',
                                    padding: '2px 4px',
                                    background: '#1a1a1a',
                                    border: '1px solid #333',
                                    borderRadius: '2px',
                                    color: '#888'
                                }}>
                                    {aiAnalysis.model_revision}
                                </span>
                                {typeof aiAnalysis.latency_ms === 'number' && (
                                    <span style={{
                                        fontSize: '9px',
                                        padding: '2px 4px',
                                        background: '#1a1a1a',
                                        border: '1px solid #333',
                                        borderRadius: '2px',
                                        color: '#888'
                                    }}>
                                        {aiAnalysis.latency_ms}ms
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
                                    ${aiAnalysis.cost_usd.toFixed(6)}
                                </span>
                            </div>

                            {/* OPERATOR FEEDBACK BUTTONS */}
                            <div style={{
                                display: 'flex',
                                gap: '0.5rem',
                                paddingTop: '0.5rem',
                                borderTop: '1px solid #333'
                            }}>
                                <button
                                    onClick={() => handleFeedback('thumbs_up')}
                                    disabled={!!aiAnalysis.operator_feedback}
                                    style={{
                                        flex: 1,
                                        padding: '0.5rem',
                                        fontSize: '10px',
                                        fontWeight: 'bold',
                                        background: aiAnalysis.operator_feedback === 'thumbs_up' ? '#10b981' : '#1a1a1a',
                                        border: '1px solid #333',
                                        color: aiAnalysis.operator_feedback === 'thumbs_up' ? '#000' : '#ccc',
                                        borderRadius: '3px',
                                        cursor: aiAnalysis.operator_feedback ? 'not-allowed' : 'pointer',
                                        opacity: aiAnalysis.operator_feedback && aiAnalysis.operator_feedback !== 'thumbs_up' ? 0.5 : 1
                                    }}
                                >
                                    👍 Helpful
                                </button>
                                <button
                                    onClick={() => handleFeedback('thumbs_down')}
                                    disabled={!!aiAnalysis.operator_feedback}
                                    style={{
                                        flex: 1,
                                        padding: '0.5rem',
                                        fontSize: '10px',
                                        fontWeight: 'bold',
                                        background: aiAnalysis.operator_feedback === 'thumbs_down' ? '#dc2626' : '#1a1a1a',
                                        border: '1px solid #333',
                                        color: aiAnalysis.operator_feedback === 'thumbs_down' ? '#fff' : '#ccc',
                                        borderRadius: '3px',
                                        cursor: aiAnalysis.operator_feedback ? 'not-allowed' : 'pointer',
                                        opacity: aiAnalysis.operator_feedback && aiAnalysis.operator_feedback !== 'thumbs_down' ? 0.5 : 1
                                    }}
                                >
                                    👎 Hallucination
                                </button>
                            </div>

                            {/* COMMENT BOX (for hallucination feedback) */}
                            {showCommentBox && (
                                <div style={{ marginTop: '0.5rem' }}>
                                    <textarea
                                        value={feedbackComment}
                                        onChange={(e) => setFeedbackComment(e.target.value)}
                                        placeholder="Describe the hallucination (optional)"
                                        style={{
                                            width: '100%',
                                            minHeight: '50px',
                                            padding: '0.5rem',
                                            fontSize: '10px',
                                            background: '#1a1a1a',
                                            border: '1px solid #333',
                                            borderRadius: '3px',
                                            color: '#ccc',
                                            fontFamily: 'monospace',
                                            resize: 'vertical'
                                        }}
                                    />
                                    <button
                                        onClick={() => handleFeedback('thumbs_down')}
                                        style={{
                                            marginTop: '0.25rem',
                                            padding: '0.5rem',
                                            fontSize: '10px',
                                            fontWeight: 'bold',
                                            background: '#dc2626',
                                            border: 'none',
                                            color: '#fff',
                                            borderRadius: '3px',
                                            cursor: 'pointer',
                                            width: '100%'
                                        }}
                                    >
                                        Submit Feedback
                                    </button>
                                </div>
                            )}
                        </div>
                    ) : (
                        /* NO DATA EMPTY STATE */
                        <div style={{
                            padding: '1rem',
                            textAlign: 'center',
                            color: '#666',
                            fontSize: '11px'
                        }}>
                            No AI analysis available
                        </div>
                    )}
                </div>
            </FailClosedPanel>

            {/* PROVENANCE FOOTER */}
            <ProvenanceFooter meta={meta} showEndpoint={false} />
        </div>
    );
};
