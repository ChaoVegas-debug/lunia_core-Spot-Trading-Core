import React, { useState, useEffect } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { WidgetWrapper } from '../common/WidgetWrapper';

interface Proposal {
    id: string;
    asset: string;
    side: 'BUY' | 'SELL';
    sizeUsd: number;
    price: number;
    confidence: number;
    reason: string;
    timestamp: number;
}

export const AIProposalsWidget: React.FC = () => {
    // Mock Data State
    const [proposals, setProposals] = useState<Proposal[]>([
        {
            id: 'p1',
            asset: 'BTC/USDT',
            side: 'BUY',
            sizeUsd: 50000,
            price: 64230.50,
            confidence: 0.87,
            reason: 'RSI Divergence 4h + Volume Spike > 2.0x',
            timestamp: Date.now() - 30000
        },
        {
            id: 'p2',
            asset: 'ETH/USDT',
            side: 'SELL',
            sizeUsd: 25000,
            price: 3450.20,
            confidence: 0.92,
            reason: 'Approaching Resistance L3 + MACD Bearish Cross',
            timestamp: Date.now() - 120000
        }
    ]);

    const handleAction = (id: string, action: 'APPROVE' | 'REJECT') => {
        console.log(`User ${action} proposal ${id}`);
        setProposals(prev => prev.filter(p => p.id !== id));
    };

    return (
        <WidgetWrapper
            id="AIProposalsWidget"
            title="AI Trade Proposals"
            rightElem={<div className="badge warning">{proposals.length} PENDING</div>}
        >
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {proposals.length === 0 && (
                    <div style={{ padding: '2rem', textAlign: 'center', opacity: 0.5 }}>
                        <span style={{ fontSize: '2rem' }}>⚡</span>
                        <p>No active proposals. AI is scanning...</p>
                    </div>
                )}

                {proposals.map(p => (
                    <div key={p.id} style={{
                        background: 'rgba(255,255,255,0.03)',
                        border: '1px solid var(--border-color)',
                        borderRadius: '4px',
                        padding: '1rem',
                        position: 'relative',
                        overflow: 'hidden'
                    }}>
                        {/* Confidence Bar */}
                        <div style={{
                            position: 'absolute',
                            bottom: 0,
                            left: 0,
                            width: `${p.confidence * 100}%`,
                            height: '2px',
                            background: p.confidence > 0.8 ? 'var(--accent-primary)' : 'var(--accent-warning)',
                            boxShadow: `0 0 10px ${p.confidence > 0.8 ? 'var(--accent-primary)' : 'var(--accent-warning)'}`
                        }} />

                        <div className="flex-between">
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                                <span style={{ fontWeight: 700, fontSize: '1.1rem' }}>{p.asset}</span>
                                <span className={`badge ${p.side === 'BUY' ? 'success' : 'danger'}`}>{p.side}</span>
                            </div>
                            <div className="font-mono small">
                                ${p.sizeUsd.toLocaleString()} @ {p.price.toLocaleString()}
                            </div>
                        </div>

                        <div style={{ marginTop: '0.75rem', marginBottom: '1rem' }}>
                            <div className="small muted" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                <span style={{ opacity: 0.7 }}>🤖 Logic:</span>
                                <span style={{ color: 'var(--text-primary)' }}>{p.reason}</span>
                            </div>
                            <div className="small muted" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.25rem' }}>
                                <span style={{ opacity: 0.7 }}>🧠 Confidence:</span>
                                <span style={{ color: p.confidence > 0.8 ? 'var(--accent-primary)' : 'var(--text-secondary)' }}>
                                    {(p.confidence * 100).toFixed(0)}%
                                </span>
                            </div>
                        </div>

                        <div className="grid cols-2" style={{ gap: '0.5rem' }}>
                            <button
                                className="button danger"
                                style={{ opacity: 0.8 }}
                                onClick={() => handleAction(p.id, 'REJECT')}
                            >
                                ✖ Reject
                            </button>
                            <button
                                className="button primary"
                                onClick={() => handleAction(p.id, 'APPROVE')}
                            >
                                ✔ Approve Execution
                            </button>
                        </div>
                    </div>
                ))}
            </div>
        </WidgetWrapper>
    );
};
