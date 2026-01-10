import React, { useState } from 'react';
import { useAuth } from '../../hooks/useAuth';

export const AdminUserGovernanceOverrides: React.FC = () => {
    // Mock user list for P3.4
    const [selectedUser, setSelectedUser] = useState('user-123');
    const [actionLog, setActionLog] = useState<string[]>([]);

    const handleAction = (action: string) => {
        if (!confirm(`Confirm governance action: ${action} on ${selectedUser}?`)) return;

        // Push to local log to simulate effect
        const timestamp = new Date().toISOString().split('T')[1].split('.')[0];
        setActionLog(prev => [`[${timestamp}] ${action} executed on ${selectedUser}`, ...prev]);

        // In real app, call API endpoint here
    };

    return (
        <div className="card">
            <div className="card-header">
                <h3>User Governance Overrides</h3>
                <span className="badge danger">ADMIN ONLY</span>
            </div>
            <div className="card-body">
                <div style={{ marginBottom: '1rem' }}>
                    <label className="small muted uppercase">Target User</label>
                    <select className="input" value={selectedUser} onChange={e => setSelectedUser(e.target.value)} style={{ width: '100%' }}>
                        <option value="user-123">user-123 (Demo User)</option>
                        <option value="user-999">user-999 (Rogue Trader)</option>
                    </select>
                </div>

                <div className="grid cols-2" style={{ gap: '12px', marginBottom: '1rem' }}>
                    <button className="button secondary small" onClick={() => handleAction('FORCE_TIER_UPGRADE')}>
                        ▲ Promote Tier
                    </button>
                    <button className="button secondary small" onClick={() => handleAction('FORCE_TIER_DOWNGRADE')}>
                        ▼ Demote Tier
                    </button>
                    <button className="button secondary small" onClick={() => handleAction('RESET_ONBOARDING')}>
                        ↺ Reset Wizard
                    </button>
                    <button className="button secondary small" onClick={() => handleAction('RESET_2FA')}>
                        🔓 Reset 2FA
                    </button>
                </div>

                <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '1rem' }}>
                    <button className="button danger full-width" onClick={() => handleAction('FREEZE_ACCOUNT')}>
                        ❄ EMERGENCY FREEZE
                    </button>
                </div>

                {actionLog.length > 0 && (
                    <div className="logs-container mt-4" style={{ maxHeight: '100px', overflowY: 'auto', background: 'var(--bg-deep)', padding: '8px', fontSize: '0.8rem', fontFamily: 'monospace' }}>
                        {actionLog.map((log, i) => (
                            <div key={i} style={{ color: 'var(--accent-primary)' }}>{log}</div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};
