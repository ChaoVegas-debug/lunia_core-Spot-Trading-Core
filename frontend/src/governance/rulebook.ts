export interface GovernanceRule {
    id: string;
    title: string;
    description: string;
    severity: 'WARNING' | 'CRITICAL' | 'FATAL';
    recoverySteps: string[];
}

export const RULEBOOK: Record<string, GovernanceRule> = {
    'GLOBAL_STOP': {
        id: 'GLOBAL_STOP',
        title: 'Global Emergency Stop Active',
        description: 'The system global kill switch has been engaged manually or automatically. All execution loops are halted.',
        severity: 'FATAL',
        recoverySteps: [
            'Verify exchange connectivity in System Page',
            'Manually cancel any hanging orders on venue',
            'Resolve the root cause of the emergency',
            'Admin must manually disengage Stop mode in System Page'
        ]
    },
    'DRIFT_LIMIT': {
        id: 'DRIFT_LIMIT',
        title: 'Portfolio Model Drift Exceeded',
        description: 'Actual exchange balances deviate from the internal strategy model by more than the allowed 5% threshold.',
        severity: 'CRITICAL',
        recoverySteps: [
            'Inspect Portfolio Reality Widget for mismatch details',
            'Use "Intervention Panel" to Accept Reality or Revert',
            'Check for unauthorized manual trades or deposits',
            'System forced to MANUAL mode until resolved'
        ]
    },
    'RISK_VETO': {
        id: 'RISK_VETO',
        title: 'Risk Engine Veto',
        description: 'A proposed trade was blocked by the Risk Engine because it violated hard constraints.',
        severity: 'WARNING',
        recoverySteps: [
            'Check Risk Budget Dashboard for utilization',
            'Verify Capital Caps in System Page',
            'Ensure asset is in Approved list',
            'Wait for volatility to decrease if Varo VaR limits were hit'
        ]
    },
    'TIER_LOCK': {
        id: 'TIER_LOCK',
        title: 'Institutional Trust Ceiling',
        description: 'The requested action exceeds the capabilities of your current Trust Tier/Subscription Plan.',
        severity: 'WARNING',
        recoverySteps: [
            'Upgrade to PRO or INSTITUTIONAL plan',
            'Request Tier override from Admin',
            'Reduce capital usage to stay within tier limits'
        ]
    },
    'OFFLINE': {
        id: 'OFFLINE',
        title: 'System Offline / Heartbeat Lost',
        description: 'Communication with the Backend Control Plane has been lost.',
        severity: 'FATAL',
        recoverySteps: [
            'Check internet connection',
            'Verify Backend Service status',
            'Restart Client Session'
        ]
    }
};

export function getRule(id: string): GovernanceRule {
    return RULEBOOK[id] || {
        id: 'UNKNOWN',
        title: 'Governance Event',
        description: 'An unspecified governance rule was triggered.',
        severity: 'WARNING',
        recoverySteps: ['Contact Support', 'Check System Logs']
    };
}
