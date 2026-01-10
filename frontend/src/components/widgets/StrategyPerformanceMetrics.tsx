import React from 'react';
import type { StrategyConfig } from '../../api/types';

interface MetricProps {
    strategyId: string;
    roi: number;
    sharpe: number;
    drawdown: number;
    winRate: number;
}

export const StrategyPerformanceMetrics: React.FC<MetricProps> = ({ roi, sharpe, drawdown, winRate }) => {
    return (
        <div className="grid cols-4 gap-2 p-2 bg-dark rounded mt-2">
            <div className="text-center">
                <div className="tiny muted">ROI (7d)</div>
                <div className={`font-bold ${roi >= 0 ? 'text-green' : 'text-red'}`}>
                    {roi > 0 ? '+' : ''}{roi.toFixed(2)}%
                </div>
            </div>
            <div className="text-center">
                <div className="tiny muted">Sharpe</div>
                <div className="font-bold text-blue">{sharpe.toFixed(2)}</div>
            </div>
            <div className="text-center">
                <div className="tiny muted">Max DD</div>
                <div className="font-bold text-red">-{drawdown.toFixed(2)}%</div>
            </div>
            <div className="text-center">
                <div className="tiny muted">Win Rate</div>
                <div className="font-bold text-primary">{winRate.toFixed(0)}%</div>
            </div>
        </div>
    );
};
