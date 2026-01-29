/**
 * SYSTEM STATE WIDGET F1
 * 
 * Phase F3.2: Wrapper-first migration to F1 standard
 * 
 * Wraps existing SystemStateWidget with:
 * - WidgetShell (FailClosedPanel + ProvenanceFooter)
 * - usePoller (replaces usePolledResource for ops state)
 * - Last Mutation panel (derived from eventBus)
 * 
 * PRESERVES all governance logic from inner component:
 * - Veto overlays, undo tokens, plan gating
 * - Airlock routing, modals, drift banners
 */

import React from 'react';
import { WidgetShell } from '../cockpit/WidgetShell';
import { usePoller } from '../../hooks/usePoller';
import { useLastMutation } from '../../hooks/useLastMutation';
import { Identicon } from '../../lib/runtime/identicon';
import { fetchJSON } from '../../lib/api/normalizeResponse';
import { endpoints } from '../../lib/runtime/endpoints';
import { SystemStateWidget } from './SystemStateWidget';
import type { OpsState } from '../../api/types';

export const SystemStateWidgetF1: React.FC = () => {
    // Phase F3.2: F1 Data Plane (LAW F compliant)
    const ops = usePoller<OpsState>({
        key: 'ops',
        endpoint: endpoints.ops_state,
        fetcher: () => fetchJSON<OpsState>(endpoints.ops_state),
        interval_ms: 2000,
        critical: true, // Feeds pulseStore for global AGE
    });

    // Phase F3.2: Last Mutation Derivation
    const lastMutation = useLastMutation({
        nameAllowList: ['EXECUTE_RESPONSE', 'MODE_CHANGE', 'SYSTEM_SAFETY_ACTION'],
        requireSuccess: true,
    });

    return (
        <WidgetShell
            title="SYSTEM STATE"
            badgeType={ops.error ? 'DATA_NOT_CONNECTED' : ops.meta.source === 'sim' ? 'MOCKED' : 'LIVE'}
            statusDot={ops.error ? '🔴' : ops.isStale ? '⚪' : '🟢'}
            meta={ops.meta}
            error={ops.error}
            isStale={ops.isStale}
        >
            {/* Phase F3.2: Last Mutation Panel */}
            {lastMutation && (
                <div style={{
                    padding: '8px 12px',
                    background: 'rgba(59, 130, 246, 0.1)',
                    borderBottom: '1px solid var(--border-color)',
                    fontSize: '10px',
                    fontFamily: 'monospace',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    color: '#3b82f6',
                }}>
                    <span style={{ fontWeight: 'bold' }}>LAST:</span>
                    <span>{lastMutation.action}</span>
                    <span style={{ color: '#666' }}>|</span>
                    <span style={{ fontWeight: 'bold' }}>BY:</span>
                    <span>{lastMutation.actor}</span>
                    <Identicon seed={lastMutation.actor} size={16} />
                    <span style={{ color: '#666' }}>|</span>
                    <span style={{ fontWeight: 'bold' }}>INTENT:</span>
                    <span>{lastMutation.intent_id}</span>
                    <span style={{ color: '#666' }}>|</span>
                    <span style={{ fontWeight: 'bold' }}>TS:</span>
                    <span>{new Date(lastMutation.ts).toLocaleTimeString('en-US', { hour12: false })}</span>
                    <span style={{ opacity: 0.6, marginLeft: '8px' }}>[DERIVED]</span>
                </div>
            )}

            {/* Inner component: existing governance logic */}
            <SystemStateWidget
                opsData={ops.data}
                opsError={ops.error}
                opsLoading={!ops.data && !ops.error}
                opsRefresh={ops.refresh}
            />
        </WidgetShell>
    );
};
