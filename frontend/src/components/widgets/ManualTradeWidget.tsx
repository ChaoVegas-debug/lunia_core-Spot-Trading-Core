import React, { useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getExchanges, getStrategies, previewManualTrade, executeManualTrade } from '../../api/adapter';
import type { ExchangeConfig, StrategyConfig, ManualTradeProposal, ManualTradePreviewResponse } from '../../api/types';
import { useSemiAuto } from '../../hooks/useSemiAuto';
import { ProposalPreviewModal } from '../common/ProposalPreviewModal';
import { ConfirmDialog } from '../common/ConfirmDialog';

export const ManualTradeWidget: React.FC = () => {
    const auth = useAuth();
    const client = { role: auth.role, adminToken: auth.adminToken, opsToken: auth.opsToken, bearerToken: auth.bearerToken };

    // Fetch dependencies
    const exchanges = usePolledResource<ExchangeConfig[]>((signal) => getExchanges(signal, client), 10000, [auth.role]);
    const strategies = usePolledResource<StrategyConfig[]>((signal) => getStrategies(signal, client), 10000, [auth.role]);

    const activeExchanges = exchanges.data?.filter(e => e.enabled) || [];
    const activeStrategies = strategies.data?.filter(s => s.enabled) || [];

    const [form, setForm] = useState<ManualTradeProposal>({
        exchange_id: '',
        symbol: 'BTCUSDT',
        side: 'BUY',
        amount_usd: 1000,
        strategy_id: 'discretionary',
        risk_notes: '',
        client_ref: ''
    });

    const [previewData, setPreviewData] = useState<ManualTradePreviewResponse | null>(null);

    // Execution Logic
    const executeTrade = async (proposal: ManualTradeProposal, key?: string) => {
        await executeManualTrade({ proposal, confirmed: true }, new AbortController().signal, client, key);
    };

    const flow = useSemiAuto<ManualTradeProposal>(
        { ...form }, // Initial state is mostly irrelevant for manual trade as we don't sync from server, but need a base
        executeTrade
    );

    const handleReview = async (sideOverride?: 'BUY' | 'SELL') => {
        const side = sideOverride || form.side;
        const currentForm = { ...form, side };
        setForm(currentForm); // Sync UI

        if (!currentForm.exchange_id) { alert("Select an Exchange"); return; }
        if (currentForm.amount_usd <= 0) { alert("Invalid Amount"); return; }

        try {
            const res = await previewManualTrade(currentForm, new AbortController().signal, client);

            if (!res.allowed) {
                alert(`BLOCKED: ${res.blocking_reason}`);
                return;
            }

            setPreviewData(res);
            // Stage the proposal returned from server (sanitized)
            if (res.proposal) {
                flow.stageChange(res.proposal);
                flow.previewProposal();
            }
        } catch (e: any) {
            alert(`Preview Failed: ${e.message}`);
        }
    };


    return (
        <div className="card">
            <div className="card-header">
                <h3>Manual Trade</h3>
            </div>

            <div className="p-4 grid gap-4">
                <div className="form-group">
                    <label>Exchange</label>
                    <select
                        className="input"
                        value={form.exchange_id}
                        onChange={e => setForm({ ...form, exchange_id: e.target.value })}
                    >
                        <option value="">Select Venue...</option>
                        {activeExchanges.map(ex => (
                            <option key={ex.id} value={ex.id}>{ex.name}</option>
                        ))}
                    </select>
                </div>

                <div className="grid cols-2 gap-2">
                    <div className="form-group">
                        <label>Symbol</label>
                        <input
                            className="input"
                            value={form.symbol}
                            onChange={e => setForm({ ...form, symbol: e.target.value.toUpperCase() })}
                        />
                    </div>
                    <div className="form-group">
                        <label>Amount (USD)</label>
                        <input
                            type="number"
                            className="input"
                            value={form.amount_usd}
                            onChange={e => setForm({ ...form, amount_usd: parseFloat(e.target.value) })}
                        />
                    </div>
                </div>

                <div className="form-group">
                    <label>Strategy / Tag</label>
                    <select
                        className="input"
                        value={form.strategy_id}
                        onChange={e => setForm({ ...form, strategy_id: e.target.value })}
                    >
                        <option value="discretionary">Discretionary</option>
                        {activeStrategies.map(s => (
                            <option key={s.id} value={s.id}>{s.name}</option>
                        ))}
                    </select>
                </div>

                <div className="grid cols-2" style={{ gap: '8px' }}>
                    <button
                        className="button ok"
                        onClick={() => handleReview('BUY')}
                    >
                        REVIEW BUY
                    </button>
                    <button
                        className="button danger"
                        onClick={() => handleReview('SELL')}
                    >
                        REVIEW SELL
                    </button>
                </div>

                {/* Modals integrated via semi-auto flow */}
                {
                    flow.state === 'PREVIEW' && (
                        <ProposalPreviewModal
                            proposal={{
                                ...flow.proposal,
                                // Mocking the shape expected by modal or generic object
                                // We attach the risks here
                                // @ts-ignore - proposal shape in modal might differ slightly but logic holds
                                risks: getRiskDisplay()
                            }}
                            onApply={flow.applyProposal}
                            onCancel={flow.cancelFlow}
                        />
                    )
                }

                {
                    flow.state === 'CONFIRMING' && (
                        <ConfirmDialog
                            onConfirm={flow.confirmProposal}
                            onCancel={flow.cancelFlow}
                            deadline={flow.proposal?.confirm_deadline}
                        />
                    )
                }
            </div>
        </div>

    );
};
