import { useMemo } from 'react';
import type { PortfolioSnapshot, StrategyConfig } from '../api/types';

interface DriftState {
    isDrifting: boolean;
    severity: 'NONE' | 'SOFT' | 'HARD';
    discrepancyPct: number;
    details: string[];
}

/**
 * P1 Governance: Client-Side Drift Verification.
 * 
 * "Trust but Verify".
 * Even if the backend says "All Good", if the Frontend calculates a math mismatch
 * between Active Strategies and Real Balances, we must flag it.
 * 
 * Logic:
 * 1. Sum up all Strategy Weights (Should be <= 1.0).
 * 2. Compare 'Strategy Target Allocation' vs 'Actual Asset Balance'.
 * 
 * @param strategies Active strategies
 * @param portfolio Real-time portfolio snapshot
 */
export const useDriftMonitor = (
    strategies: StrategyConfig[],
    portfolio?: PortfolioSnapshot
): DriftState => {
    return useMemo(() => {
        if (!portfolio || strategies.length === 0) {
            return { isDrifting: false, severity: 'NONE', discrepancyPct: 0, details: [] };
        }

        let driftFound = false;
        let maxDrift = 0;
        const details: string[] = [];
        const severity: 'NONE' | 'SOFT' | 'HARD' = 'NONE';

        // 1. Map Strategies to Expected Assets
        // Heuristic: Strategy Name often contains Symbol (e.g., "BTC Trend").
        // Real logic would require strategy.asset_symbol field. 
        // For P1, we assume strategies generally map to assets or we check 'Total Exposure'.
        // Better metric: Checks Total Equity vs Strategy Authorized Capital.

        // P1.1: Drift Simulation (Dev Tool)
        const params = new URLSearchParams(window.location.search);
        if (params.get('simulateDrift') === '1') {
            return {
                isDrifting: true,
                severity: 'HARD',
                discrepancyPct: 15.5,
                details: ['[SIMULATION] Manual Sell of BTC detected (-0.5 BTC mismatch).']
            };
        }

        // Check 1: Manual Interference (Hard Drift)
        // If we have an Asset that is NOT in any active strategy, that's a "Shadow Position" (Scene B).
        // Note: We skip USDT/USDC/Cash.
        const activeSymbols = new Set(strategies.map(s => s.name.split(' ')[0])); // Simple parser for now

        // We can't do symbol matching perfectly without backend mapping.
        // Fallback: Check 'Total Equity' vs 'Mode'.
        // If specific "Manual" positions exist in portfolio but no manual mode allowed -> Alarm.

        // For P1 MVP: We rely on the Backend 'drift_status' if available (via OpsState), 
        // but here we can calculate 'Capital Utilization Mismatch'.

        // NOTE: This hook is a placeholder for the advanced logic.
        // Currently, we will return NONE until confirmed backend mapping exists,
        // OR we can implement a simple check:
        // "Is there a position > 5% of portfolio that has no corresponding strategy?"

        return {
            isDrifting: driftFound,
            severity: driftFound ? 'HARD' : 'NONE',
            discrepancyPct: maxDrift,
            details
        };
    }, [strategies, portfolio]);
};
