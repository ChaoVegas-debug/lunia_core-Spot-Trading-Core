import React, { useMemo, useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getPortfolioSnapshot, getBalances, getOpsCapital, setSystemMode } from '../../api/adapter';
import { safeArray } from '../../utils/safe';
import { buildClient } from '../../api/client';
import type { PortfolioAggregate, BalancesResponse, OpsCapital } from '../../api/types';
import { useNavigate } from 'react-router-dom';

// Helper for symbol normalization
const getBaseAsset = (symbol: string): string => {
    if (!symbol) return '';
    if (symbol.includes('/')) return symbol.split('/')[0];
    if (symbol.includes('-')) return symbol.split('-')[0];
    if (symbol.endsWith('USDT')) return symbol.replace('USDT', '');
    if (symbol.endsWith('USD')) return symbol.replace('USD', '');
    return symbol;
};

export const GovernanceBanners: React.FC = () => {
    const auth = useAuth();
    const navigate = useNavigate();
    const client = buildClient(auth); // Unified Client

    const portfolio = usePolledResource<PortfolioAggregate>((s) => getPortfolioSnapshot(s, client), 5000, []);
    const balances = usePolledResource<BalancesResponse>((s) => getBalances(s, client), 5000, []);
    const capital = usePolledResource<OpsCapital>((s) => getOpsCapital(s, client), 5000, []);

    const [processing, setProcessing] = useState(false);
    const [showFixModal, setShowFixModal] = useState(false);

    // 1. Position Drift Detection
    const driftWarning = useMemo(() => {
        if (!portfolio.data?.positions || !balances.data?.balances) return null;

        const drifters: string[] = [];
        const DUST_THRESHOLD = 0.0001;

        for (const pos of safeArray(portfolio.data?.positions)) {
            const baseAsset = getBaseAsset(pos.symbol);
            const bal = balances.data.balances.find(b => b.asset === baseAsset);
            const actualQty = bal ? (bal.free + bal.locked) : 0;

            if (pos.quantity > DUST_THRESHOLD && actualQty < (pos.quantity * 0.95)) {
                drifters.push(`${pos.symbol} (Exp: ${pos.quantity.toFixed(4)} vs Act: ${actualQty.toFixed(4)})`);
            }
        }
        return drifters.length > 0 ? drifters : null;

    }, [portfolio.data, balances.data]);

    // 2. Allocation / Capital Violation
    const allocationWarning = useMemo(() => {
        if (!capital.data) return null;
        if (capital.data.usable_cap_pct !== undefined) {
            if (capital.data.usable_cap_pct < 0) {
                return {
                    deficit: Math.abs(capital.data.usable_cap_pct),
                    msg: `Deficit: ${(Math.abs(capital.data.usable_cap_pct) * 100).toFixed(2)}%`
                };
            }
        }
        return null;
    }, [capital.data]);

    const handleReSync = async () => {
        portfolio.refresh();
        balances.refresh();
        alert("State Refreshed. If drift persists, external resolution is required.");
    };

    const handleEmergencyStop = async () => {
        if (!confirm("CONFIRM EMERGENCY STOP?\n\nThis will halt all trading algorithms immediately.")) return;
        setProcessing(true);
        try {
            await setSystemMode('STOP', new AbortController().signal, client);
        } catch (e) {
            alert("Stop Failed: Check API Connectivity");
        } finally {
            setProcessing(false);
        }
    };

    const handleConvertToStable = () => {
        // GAP Handling
        alert("Feature Unavailable: 'Liquidate to Stable' endpoint requires backend implementation.\n\nPlease perform this action manually on the exchange.");
    };

    if (!driftWarning && !allocationWarning) return null;

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1rem' }}>

            {/* DRIFT BANNER */}
            {driftWarning && (
                <div className="card" style={{
                    border: '1px solid var(--accent-danger)',
                    background: 'rgba(239, 68, 68, 0.1)',
                    padding: '1rem'
                }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                            <div style={{ color: 'var(--accent-danger)', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <span>⚠ POSITION DRIFT DETECTED</span>
                            </div>
                            <p className="small muted" style={{ marginTop: '0.5rem' }}>
                                Assets on exchange do not match Portfolio model. Risk Verification Failed.
                                {driftWarning.map(d => <span key={d} style={{ display: 'block', fontFamily: 'monospace' }}>- {d}</span>)}
                            </p>
                        </div>
                        <div style={{ display: 'flex', gap: '8px' }}>
                            <button className="button danger small" onClick={handleEmergencyStop} disabled={processing}>
                                {processing ? 'HALTING...' : 'EMERGENCY STOP'}
                            </button>
                        </div>
                    </div>

                    {/* Resolution Panel */}
                    <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid rgba(239, 68, 68, 0.3)', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                        <span className="tiny uppercase muted" style={{ alignSelf: 'center', marginRight: '8px' }}>Resolution Options:</span>
                        <button className="button small outline" onClick={handleReSync}>
                            ↻ Re-Sync State
                        </button>
                        <button className="button small outline" onClick={() => setShowFixModal(true)}>
                            🔧 Fix on Exchange
                        </button>
                        <button className="button small outline" onClick={handleConvertToStable} title="Emergency Liquidation">
                            Conversion (Escrow)
                        </button>
                    </div>
                </div>
            )}

            {/* CAPITAL ALLOCATION BANNER */}
            {allocationWarning && (
                <div className="card" style={{
                    border: '1px solid var(--accent-warning)',
                    background: 'rgba(245, 158, 11, 0.1)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '1rem'
                }}>
                    <div>
                        <div style={{ color: 'var(--accent-warning)', fontWeight: 700 }}>
                            ⚠ CAPITAL ALLOCATION VIOLATION
                        </div>
                        <p className="small muted" style={{ marginTop: '0.5rem' }}>
                            Insufficient funds. {allocationWarning.msg}. System downgraded to SAFE mode.
                        </p>
                        <p className="tiny muted" style={{ marginTop: '0.25rem' }}>
                            Usable Cap: <span className="text-warn">{capital.data?.usable_cap_pct?.toFixed(2) ?? 'N/A'}%</span> (Threshold: 0%)
                        </p>
                    </div>
                    <button className="button secondary small" onClick={() => navigate('/account')}>
                        Review Cap Settings
                    </button>
                </div>
            )}

            {/* FIX MODAL (INLINE) */}
            {showFixModal && (
                <div className="modal-backdrop">
                    <div className="card modal-content" style={{ width: '500px' }}>
                        <div className="card-header">
                            <h3>Manual Resolution Guide</h3>
                        </div>
                        <div style={{ padding: '1rem' }}>
                            <p className="small muted" style={{ marginBottom: '1rem' }}>
                                To resolve drift, your exchange balance must match the portfolio target.
                            </p>
                            <ol className="small muted" style={{ paddingLeft: '1.2rem', lineHeight: '1.6' }}>
                                <li>Log in to your Exchange Account (Binance/Bybit).</li>
                                <li>Navigate to Spot Wallet.</li>
                                <li>Manually buy/sell the affected assets to match the Expected Quantity shown in the banner.</li>
                                <li>Wait 30 seconds.</li>
                                <li>Click "Re-Sync State" in the banner.</li>
                            </ol>
                            <div className="alert info small" style={{ marginTop: '1rem' }}>
                                <strong>Why?</strong> The Governance Engine cannot execute orders if the starting state is invalid (Risk Safety Lock).
                            </div>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '1rem', borderTop: '1px solid #333' }}>
                            <button className="button primary" onClick={() => setShowFixModal(false)}>Understood</button>
                        </div>
                    </div>
                </div>
            )}

        </div>
    );
};
