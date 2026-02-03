import { Proposal, ProposalStatus, ProposalAction, ProposalPriority, ProposalRiskLabel, ProposalHorizon, ProposalFactorAttribution } from '../api/epoch_a_types';

/**
 * Rich Scenario-Based Proposal Generator for EPOCH A
 * Implements 6 required scenarios (A-F) per spec
 */

const generateUUID = () => `prop-${Math.random().toString(36).substr(2, 9)}`;

const now = Date.now();

export const generateRichProposals = (): Proposal[] => {
    const baseTimestamp = new Date(now - 3600000).toISOString(); // 1h ago
    const recentTimestamp = new Date(now - 600000).toISOString(); // 10min ago

    return [
        // SCENARIO A: Perfect Trade
        {
            id: generateUUID(),
            asset: 'BTC',
            action: 'BUY' as ProposalAction,
            status: 'PENDING_USER' as ProposalStatus,
            confidence: 88,
            priority: 'HIGH' as ProposalPriority,
            riskLabel: 'MEDIUM_RISK' as ProposalRiskLabel,
            riskRewardRatio: 3.2,
            horizon: 'POSITION' as ProposalHorizon,
            thesisSummary: 'Strong institutional accumulation detected across multiple timeframes. On-chain metrics show whale activity accelerating. Technical confluence at key demand zone.',
            factorAttribution: [
                { factor: 'Technical Analysis', weight: 35, confidence: 92 },
                { factor: 'On-Chain Metrics', weight: 30, confidence: 85 },
                { factor: 'Institutional Flow', weight: 25, confidence: 88 },
                { factor: 'Sentiment', weight: 10, confidence: 75 }
            ],
            expiresAt: new Date(now + 7200000).toISOString(), // 2h from now
            createdAt: baseTimestamp,
            updatedAt: recentTimestamp
        },

        // SCENARIO B: Governance Blocked (Global Stop)
        {
            id: generateUUID(),
            asset: 'ETH',
            action: 'SELL' as ProposalAction,
            status: 'PENDING_USER' as ProposalStatus,
            confidence: 82,
            priority: 'URGENT' as ProposalPriority,
            riskLabel: 'LOW_RISK' as ProposalRiskLabel,
            riskRewardRatio: 2.8,
            horizon: 'SWING' as ProposalHorizon,
            thesisSummary: 'Bearish divergence on daily timeframe. Gas fees spiking indicating network congestion. Smart money distribution pattern.',
            factorAttribution: [
                { factor: 'Technical Divergence', weight: 40, confidence: 85 },
                { factor: 'Network Metrics', weight: 30, confidence: 90 },
                { factor: 'Smart Money', weight: 20, confidence: 78 },
                { factor: 'Macro Correlation', weight: 10, confidence: 70 }
            ],
            expiresAt: new Date(now + 3600000).toISOString(), // 1h from now
            createdAt: baseTimestamp,
            updatedAt: recentTimestamp
        },

        // SCENARIO C: Stale Data (will trigger lockdown if freshness != FRESH)
        {
            id: generateUUID(),
            asset: 'SOL',
            action: 'BUY' as ProposalAction,
            status: 'PENDING_USER' as ProposalStatus,
            confidence: 91,
            priority: 'HIGH' as ProposalPriority,
            riskLabel: 'MEDIUM_RISK' as ProposalRiskLabel,
            riskRewardRatio: 4.1,
            horizon: 'POSITION' as ProposalHorizon,
            thesisSummary: 'Ecosystem growth accelerating. New DEX volumes breaking records. Developer activity at ATH. Breakout from 6-month base confirmed.',
            factorAttribution: [
                { factor: 'Ecosystem Growth', weight: 35, confidence: 95 },
                { factor: 'Technical Breakout', weight: 30, confidence: 88 },
                { factor: 'Developer Activity', weight: 20, confidence: 92 },
                { factor: 'Volume Profile', weight: 15, confidence: 85 }
            ],
            expiresAt: new Date(now + 5400000).toISOString(), // 1.5h from now
            createdAt: baseTimestamp,
            updatedAt: recentTimestamp
        },

        // SCENARIO D: Expired
        {
            id: generateUUID(),
            asset: 'AVAX',
            action: 'HEDGE' as ProposalAction,
            status: 'EXPIRED' as ProposalStatus,
            confidence: 75,
            priority: 'MEDIUM' as ProposalPriority,
            riskLabel: 'HIGH_RISK' as ProposalRiskLabel,
            riskRewardRatio: 1.8,
            horizon: 'INTRADAY' as ProposalHorizon,
            thesisSummary: 'Short-term volatility hedge recommended due to upcoming macro event. Window has closed.',
            factorAttribution: [
                { factor: 'Volatility Analysis', weight: 50, confidence: 80 },
                { factor: 'Event Risk', weight: 30, confidence: 85 },
                { factor: 'Correlation', weight: 20, confidence: 70 }
            ],
            expiresAt: new Date(now - 600000).toISOString(), // expired 10min ago
            createdAt: new Date(now - 7200000).toISOString(),
            updatedAt: new Date(now - 3600000).toISOString()
        },

        // SCENARIO E: Extreme Risk
        {
            id: generateUUID(),
            asset: 'DOGE',
            action: 'BUY' as ProposalAction,
            status: 'PENDING_USER' as ProposalStatus,
            confidence: 62,
            priority: 'LOW' as ProposalPriority,
            riskLabel: 'EXTREME_RISK' as ProposalRiskLabel,
            riskRewardRatio: 5.5,
            horizon: 'INTRADAY' as ProposalHorizon,
            thesisSummary: 'Extremely speculative setup. Social media momentum building. High volatility expected. Only for risk-tolerant strategies with strict stops.',
            factorAttribution: [
                { factor: 'Social Momentum', weight: 60, confidence: 70 },
                { factor: 'Technical Setup', weight: 25, confidence: 50 },
                { factor: 'Whale Activity', weight: 15, confidence: 65 }
            ],
            expiresAt: new Date(now + 1800000).toISOString(), // 30min from now
            createdAt: recentTimestamp,
            updatedAt: recentTimestamp
        },

        // SCENARIO F: Conflict Detected (EPOCH C preview)
        {
            id: generateUUID(),
            asset: 'LINK',
            action: 'BUY' as ProposalAction,
            status: 'REQUEST_CHANGES' as ProposalStatus,
            confidence: 79,
            priority: 'MEDIUM' as ProposalPriority,
            riskLabel: 'MEDIUM_RISK' as ProposalRiskLabel,
            riskRewardRatio: 2.9,
            horizon: 'SWING' as ProposalHorizon,
            thesisSummary: 'Oracle network expansion bullish. However, conflicts detected with existing BAND position (correlation 0.87). Requires size adjustment.',
            factorAttribution: [
                { factor: 'Fundamental News', weight: 35, confidence: 85 },
                { factor: 'Technical Pattern', weight: 30, confidence: 75 },
                { factor: 'Sector Rotation', weight: 20, confidence: 80 },
                { factor: 'Conflict Warning', weight: 15, confidence: 90 }
            ],
            expiresAt: new Date(now + 10800000).toISOString(), // 3h from now
            createdAt: baseTimestamp,
            updatedAt: recentTimestamp
        },

        // Additional variety proposals
        {
            id: generateUUID(),
            asset: 'MATIC',
            action: 'SELL' as ProposalAction,
            status: 'APPROVED' as ProposalStatus,
            confidence: 85,
            priority: 'HIGH' as ProposalPriority,
            riskLabel: 'LOW_RISK' as ProposalRiskLabel,
            riskRewardRatio: 3.0,
            horizon: 'POSITION' as ProposalHorizon,
            thesisSummary: 'Profit-taking signal after strong run. Resistance cluster ahead. Risk-reward favors exit.',
            factorAttribution: [
                { factor: 'Profit Target', weight: 40, confidence: 90 },
                { factor: 'Resistance Analysis', weight: 35, confidence: 85 },
                { factor: 'Market Structure', weight: 25, confidence: 80 }
            ],
            expiresAt: new Date(now + 14400000).toISOString(), // 4h from now
            createdAt: new Date(now - 5400000).toISOString(),
            updatedAt: new Date(now - 1800000).toISOString(),
            approvedAt: new Date(now - 900000).toISOString()
        },

        {
            id: generateUUID(),
            asset: 'ADA',
            action: 'REBALANCE' as ProposalAction,
            status: 'PENDING_USER' as ProposalStatus,
            confidence: 73,
            priority: 'MEDIUM' as ProposalPriority,
            riskLabel: 'LOW_RISK' as ProposalRiskLabel,
            riskRewardRatio: 2.2,
            horizon: 'LONG_TERM' as ProposalHorizon,
            thesisSummary: 'Portfolio rebalancing required. Position has drifted 2.5% above target allocation. Reduce to maintain risk profile.',
            factorAttribution: [
                { factor: 'Portfolio Drift', weight: 50, confidence: 95 },
                { factor: 'Risk Management', weight: 30, confidence: 90 },
                { factor: 'Correlation Shift', weight: 20, confidence: 80 }
            ],
            expiresAt: new Date(now + 86400000).toISOString(), // 24h from now
            createdAt: new Date(now - 7200000).toISOString(),
            updatedAt: new Date(now - 1200000).toISOString()
        },

        {
            id: generateUUID(),
            asset: 'ATOM',
            action: 'BUY' as ProposalAction,
            status: 'REJECTED' as ProposalStatus,
            confidence: 68,
            priority: 'LOW' as ProposalPriority,
            riskLabel: 'HIGH_RISK' as ProposalRiskLabel,
            riskRewardRatio: 1.9,
            horizon: 'SWING' as ProposalHorizon,
            thesisSummary: 'Interchain ecosystem development positive. However, macro headwinds and technical weakness outweigh fundamentals.',
            factorAttribution: [
                { factor: 'Fundamentals', weight: 35, confidence: 75 },
                { factor: 'Technical Weakness', weight: 35, confidence: 80 },
                { factor: 'Macro Headwinds', weight: 30, confidence: 85 }
            ],
            createdAt: new Date(now - 10800000).toISOString(),
            updatedAt: new Date(now - 7200000).toISOString(),
            rejectedAt: new Date(now - 7200000).toISOString(),
            rejectionReason: 'TIMING_POOR'
        },

        {
            id: generateUUID(),
            asset: 'DOT',
            action: 'BUY' as ProposalAction,
            status: 'PENDING_USER' as ProposalStatus,
            confidence: 77,
            priority: 'MEDIUM' as ProposalPriority,
            riskLabel: 'MEDIUM_RISK' as ProposalRiskLabel,
            riskRewardRatio: 2.7,
            horizon: 'POSITION' as ProposalHorizon,
            thesisSummary: 'Parachain auctions driving demand. accumulation phase identified. Entry zone approaching key support.',
            factorAttribution: [
                { factor: 'On-Chain Activity', weight: 35, confidence: 82 },
                { factor: 'Accumulation Pattern', weight: 30, confidence: 75 },
                { factor: 'Support Zone', weight: 25, confidence: 80 },
                { factor: 'Ecosystem Growth', weight: 10, confidence: 70 }
            ],
            expiresAt: new Date(now + 9000000).toISOString(), // 2.5h from now
            createdAt: new Date(now - 4800000).toISOString(),
            updatedAt: new Date(now - 1800000).toISOString()
        }
    ];
};
