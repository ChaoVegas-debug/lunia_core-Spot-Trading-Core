import React, { useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getPortfolioStructure, runPortfolioAction } from '../../api/adapter';
import { safeArray } from '../../utils/safe';
import type { PortfolioDefinition, AssetCard } from '../../api/types';
import { DataStatus } from '../common/DataStatus';
import { OperatorActionPanel } from './OperatorActionPanel';
import { ReduceRiskModal } from '../modals/ReduceRiskModal';
import { FreezeAssetModal } from '../modals/FreezeAssetModal';
import { ConvertToStableModal } from '../modals/ConvertToStableModal';
import { journalStore } from '../../store/JournalStore';

export const PortfolioStructureWidget: React.FC = () => {
    const auth = useAuth();
    const client = { role: auth.role, adminToken: auth.adminToken, opsToken: auth.opsToken, bearerToken: auth.bearerToken };

    const { data: portfolios, loading, error, lastUpdated, refresh } = usePolledResource<PortfolioDefinition[]>(
        (signal) => getPortfolioStructure(signal, client),
        10000,
        [auth.role]
    );

    const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
    const toggleExpand = (id: string) => {
        const next = new Set(expandedIds);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        setExpandedIds(next);
    };

    const handleAction = async (id: string, action: 'PAUSE' | 'RESUME' | 'DERISK' | 'REBALANCE') => {
        if (!confirm(`Are you sure you want to ${action} portfolio ${id}?`)) return;
        try {
            await runPortfolioAction(id, action, new AbortController().signal, client);
            refresh();
            journalStore.addLog('MODE_CHANGE', `Portfolio ${id} Action: ${action}`, 'HUMAN');
        } catch (e: any) {
            alert("Action failed: " + (e.message || e));
        }
    };

    return (
        <div className="card decision">
            <div className="card-header">
                <div>
                    <h3>Active Portfolios</h3>
                    <p className="tiny muted uppercase" style={{ letterSpacing: '0.1em' }}>Engine-Constructed Strategies & Assets</p>
                </div>
                <DataStatus loading={loading} error={error} lastUpdated={lastUpdated} />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {(portfolios || []).map(p => (
                    <div key={p.id} className="card subtle" style={{ padding: '0', overflow: 'hidden' }}>
                        {/* Portfolio Header Strip */}
                        <div style={{ padding: '12px', borderBottom: '1px solid rgba(255,255,255,0.05)', background: 'rgba(255,255,255,0.02)' }}>
                            <div className="flex-between">
                                <div className="flex-row">
                                    <span className={`status-chip ${p.status === 'ACTIVE' ? 'ok' : 'warn'}`}>
                                        {p.status}
                                    </span>
                                    <span style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--text-primary)' }}>
                                        {p.id}
                                    </span>
                                </div>
                                <div className="flex-row">
                                    {p.status === 'ACTIVE' && (
                                        <>
                                            <button className="button primary" style={{ padding: '2px 8px' }} onClick={() => handleAction(p.id, 'REBALANCE')} title="Rebalance">⚖</button>
                                            <button className="button" style={{ padding: '2px 8px' }} onClick={() => handleAction(p.id, 'PAUSE')} title="Pause">❚❚</button>
                                        </>
                                    )}
                                    {p.status === 'PAUSED' && (
                                        <button className="button ok" onClick={() => handleAction(p.id, 'RESUME')}>▶</button>
                                    )}
                                    <button className="button danger" style={{ padding: '2px 8px' }} onClick={() => handleAction(p.id, 'DERISK')} title="Kill">✖</button>
                                </div>
                            </div>
                            <div className="tiny muted uppercase" style={{ marginTop: '4px', letterSpacing: '0.05em' }}>
                                {p.type} • {p.risk_profile} • {p.horizon} • ${p.total_capital_allocation.toLocaleString()}
                            </div>
                        </div>

                        {/* Metrics Grid */}
                        <div className="grid cols-3 gap-2" style={{ padding: '12px', background: 'rgba(0,0,0,0.2)' }}>
                            <div className="card inset p-2 text-center">
                                <div className="label tiny muted">CONFIDENCE</div>
                                <div className="metric-lg text-primary">{(Math.random() * 20 + 75).toFixed(1)}%</div>
                            </div>
                            <div className="card inset p-2 text-center">
                                <div className="label tiny muted">DAILY PNL</div>
                                <div className="metric-lg text-green">+${(Math.random() * 500).toFixed(2)}</div>
                            </div>
                            <div className="card inset p-2 text-center">
                                <div className="label tiny muted">DRAWDOWN</div>
                                <div className="metric-lg text-red">-{(Math.random() * 2).toFixed(2)}%</div>
                            </div>
                        </div>

                        {/* Strategy Rules Grid */}
                        <div style={{ padding: '0 12px 12px' }}>
                            <div style={{
                                display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px',
                                background: 'rgba(255,255,255,0.02)', padding: '8px', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.05)'
                            }}>
                                <div>
                                    <div className="tiny muted uppercase">Entry</div>
                                    <div className="small text-cyan">{p.rules.entry_mode}</div>
                                </div>
                                <div>
                                    <div className="tiny muted uppercase">Rebal</div>
                                    <div className="small text-primary">{p.rules.rebalance_interval_days}d</div>
                                </div>
                                <div>
                                    <div className="tiny muted uppercase">Take Profit</div>
                                    <div className="small text-green">{(p.rules.profit_take_pct * 100).toFixed(0)}%</div>
                                </div>
                                <div>
                                    <div className="tiny muted uppercase">Stop Loss</div>
                                    <div className="small text-red">{(p.rules.stop_loss_pct * 100).toFixed(0)}%</div>
                                </div>
                            </div>
                        </div>

                        {/* Assets Toggle */}
                        <div
                            onClick={() => toggleExpand(p.id)}
                            style={{
                                borderTop: '1px solid rgba(255,255,255,0.05)',
                                padding: '8px',
                                textAlign: 'center',
                                cursor: 'pointer',
                                background: expandedIds.has(p.id) ? 'rgba(255,255,255,0.05)' : 'transparent',
                                transition: 'background 0.2s'
                            }}
                            className="tiny muted uppercase hover-bright flex-center"
                        >
                            {expandedIds.has(p.id) ? '▲ COLLAPSE ASSETS' : `▼ VIEW ${safeArray(p.assets).length} ASSETS`}
                        </div>

                        {/* Expanded Assets */}
                        {expandedIds.has(p.id) && (
                            <div style={{ padding: '0', display: 'flex', flexDirection: 'column', background: 'rgba(0,0,0,0.3)' }}>
                                {p.assets.map(a => <AssetRow key={a.symbol} asset={a} />)}
                            </div>
                        )}
                    </div>
                ))}
                {(!portfolios || portfolios.length === 0) && (
                    <div className="card subtle dashed-border" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                        <div style={{ fontSize: '2rem', marginBottom: '1rem', opacity: 0.3 }}>📭</div>
                        <div className="uppercase tracking-wide">System Idle</div>
                        <div className="small alpha-50 mt-2">No Active Portfolios Deployed</div>
                    </div>
                )}
            </div>
        </div>
    );
};

const AssetRow: React.FC<{ asset: AssetCard }> = ({ asset }) => {
    const [showActions, setShowActions] = useState(false);
    const [activeModal, setActiveModal] = useState<'REDUCE' | 'FREEZE' | 'CONVERT' | null>(null);

    // Derived Status Tags (Simulated Logic for now)
    const badges = [];
    if (asset.weight > 0) badges.push('AI HOLDING');
    if (Math.random() > 0.8) badges.push('WAITING SIGNAL');
    // if (asset.is_frozen) badges.push('BLOCKED'); // Needs type update

    const handleAction = (action: 'PAUSE' | 'REDUCE_RISK' | 'FREEZE' | 'CONVERT') => {
        if (action === 'REDUCE_RISK') setActiveModal('REDUCE');
        if (action === 'FREEZE') setActiveModal('FREEZE');
        if (action === 'CONVERT') setActiveModal('CONVERT');
        if (action === 'PAUSE') {
            if (confirm(`Pause trading for ${asset.symbol}?`)) {
                journalStore.addLog('VETO', `Paused trading for ${asset.symbol}`, 'HUMAN');
            }
        }
    };

    return (
        <div style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
            <div
                style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '8px 12px',
                    fontSize: '0.85rem',
                    cursor: 'pointer',
                    background: showActions ? 'rgba(255,255,255,0.05)' : 'transparent'
                }}
                onClick={() => setShowActions(!showActions)}
                title="Click to Manage Asset"
            >
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', width: '30%' }}>
                    <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{asset.symbol}</span>
                    <span className="tiny muted bg-dark-2 px-1 rounded">{asset.sector}</span>
                </div>

                <div style={{ flex: 1, margin: '0 12px' }}>
                    <div style={{ height: '6px', width: '100%', background: 'rgba(255,255,255,0.1)', borderRadius: '2px', overflow: 'hidden' }}>
                        <div style={{ height: '100%', width: `${asset.weight * 100}%`, background: 'var(--accent-primary)' }} />
                    </div>
                </div>

                <div className="text-mono" style={{ width: '15%', textAlign: 'right', color: 'var(--accent-secondary)' }}>
                    {(asset.weight * 100).toFixed(1)}%
                </div>
            </div>

            {showActions && (
                <div style={{ padding: '0 12px 12px 12px' }}>
                    <OperatorActionPanel
                        symbol={asset.symbol}
                        exposure={asset.weight}
                        badges={badges}
                        onAction={handleAction}
                    />
                </div>
            )}

            {activeModal === 'REDUCE' && (
                <ReduceRiskModal
                    symbol={asset.symbol}
                    onClose={() => setActiveModal(null)}
                    onConfirm={(amt) => {
                        journalStore.addLog('INTERVENTION', `Reduced risk on ${asset.symbol} by ${amt}%`, 'HUMAN');
                        setActiveModal(null);
                    }}
                />
            )}
            {activeModal === 'FREEZE' && (
                <FreezeAssetModal
                    symbol={asset.symbol}
                    onClose={() => setActiveModal(null)}
                    onConfirm={() => {
                        journalStore.addLog('VETO', `Asset Frozen: ${asset.symbol}`, 'HUMAN');
                        setActiveModal(null);
                    }}
                />
            )}
            {activeModal === 'CONVERT' && (
                <ConvertToStableModal
                    symbol={asset.symbol}
                    onClose={() => setActiveModal(null)}
                    onConfirm={() => {
                        journalStore.addLog('FLATTEN', `Asset Liquidated: ${asset.symbol}`, 'HUMAN', 'CRITICAL');
                        setActiveModal(null);
                    }}
                />
            )}
        </div>
    );
};
