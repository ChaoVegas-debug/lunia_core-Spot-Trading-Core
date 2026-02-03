import React, { useState } from 'react';
import { getAdminFlags, setAdminFlag } from '../../../api/endpoints';
import { useAuth } from '../../../hooks/useAuth';
import { usePreview } from '../../../hooks/usePreview';
import type { FeatureFlag } from '../../../api/types';
import { ConfirmDialog } from '../../common/ConfirmDialog';
import { useDashboard } from '../../../context/DashboardContext';

export const FeatureFlagsWidget: React.FC = () => {
    const auth = useAuth();
    const { isPreview, previewStore } = usePreview();
    const { addToast } = useDashboard();
    const client = { role: auth.role, adminToken: auth.adminToken };

    const { data, error, refresh } = usePoller<FeatureFlag[]>({
        key: 'data_FeatureFlagsWidget',
        endpoint: '/api/unknown',
        fetcher: () => getAdminFlags(new AbortController().signal, client),
        interval_ms: 5000,
        critical: false
    });
    const loading = false;
    const lastUpdated = undefined;

    // Use simulated flags in Preview Mode
    const displayFlags = isPreview
        ? previewStore.getState().feature_flags.map(f => ({
            key: f.key,
            value: f.value,
            updated_at: new Date().toISOString()
        } as FeatureFlag))
        : (apiFlags || []);

    const [pendingFlag, setPendingFlag] = useState<{ key: string, value: any } | null>(null);

    const handleToggle = (flag: FeatureFlag) => {
        // Toggle boolean logic
        const current = !!flag.value;
        setPendingFlag({ key: flag.key, value: !current });
    };

    const confirmToggle = async () => {
        if (!pendingFlag) return;
        try {
            if (isPreview) {
                previewStore.toggleFeatureFlag(pendingFlag.key);
            } else {
                await setAdminFlag(pendingFlag.key, String(pendingFlag.value), new AbortController().signal, client);
                refresh();
            }
            setPendingFlag(null);
        } catch (e) {
            addToast({ type: 'ERROR', message: "Failed to update flag" });
        }
    };

    if (loading && !apiFlags && !isPreview) return <div className="card">Loading Flags...</div>;

    return (
        <div className="card">
            <div className="card-header">
                <h3>System Feature Flags</h3>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '0' }}>
                {displayFlags.map(flag => (
                    <div key={flag.key} className="flex-between" style={{ padding: '12px 0', borderBottom: '1px solid #374151' }}>
                        <div>
                            <div className="font-mono small">{flag.key}</div>
                            <div className="tiny muted">Last updated: {new Date(flag.updated_at).toLocaleString()}</div>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                            <div className={`badge ${!!flag.value ? 'success' : 'secondary'}`}>
                                {!!flag.value ? 'ENABLED' : 'DISABLED'}
                            </div>
                            <button className="button secondary tiny" onClick={() => handleToggle(flag)}>
                                Toggle
                            </button>
                        </div>
                    </div>
                ))}
            </div>

            {/* Confirmation Dialog */}
            {pendingFlag && (
                <ConfirmDialog
                    title="Change System Flag?"
                    message={`Are you sure you want to set ${pendingFlag.key} to ${pendingFlag.value}? This will affect all users immediately.`}
                    onConfirm={confirmToggle}
                    onCancel={() => setPendingFlag(null)}
                />
            )}
        </div>
    );
};
