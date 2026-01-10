import React from 'react';

interface OperatorActionPanelProps {
    symbol: string;
    exposure: number;
    badges?: string[];
    onAction: (action: 'PAUSE' | 'REDUCE_RISK' | 'FREEZE' | 'CONVERT') => void;
}

export const OperatorActionPanel: React.FC<OperatorActionPanelProps> = ({ symbol, exposure, badges = [], onAction }) => {
    // Actions only enabled if exposure exists
    const enabled = Math.abs(exposure) > 0;

    return (
        <div className="operator-action-panel p-2 mt-2 bg-dark rounded flex-between" style={{ borderTop: '1px solid var(--border-color)' }}>
            <div className="badges flex gap-2">
                {badges.length > 0 ? badges.map(b => (
                    <span key={b} className="tiny badge text-blue border-blue">{b}</span>
                )) : (
                    <span className="tiny badge muted">IDLE</span>
                )}
            </div>

            <div className="actions flex gap-2">
                <button
                    className="button tiny outline"
                    title="Pause Trading for this Asset"
                    onClick={() => onAction('PAUSE')}
                >
                    ⏸ PAUSE
                </button>
                <button
                    className="button tiny outline"
                    title="Reduce Risk (Sell Portion)"
                    disabled={!enabled}
                    onClick={() => onAction('REDUCE_RISK')}
                >
                    📉 REDUCE
                </button>
                <button
                    className="button tiny outline danger"
                    title="Freeze Asset (Cancel Orders + Block)"
                    onClick={() => onAction('FREEZE')}
                >
                    ❄ FREEZE
                </button>
                <button
                    className="button tiny danger"
                    title="Convert to Stable (Liquidate Position)"
                    disabled={!enabled}
                    onClick={() => onAction('CONVERT')}
                >
                    $ STABLE
                </button>
            </div>
        </div>
    );
};
