/**
 * WIDGET SHELL - STANDARD WRAPPER
 * 
 * UI Constitution Enforcement:
 * - LAW A: F1 Standard Only (usePoller + fetchJSON + FailClosedPanel + ProvenanceFooter mandatory)
 * - LAW B: Fail-Closed is Visual (blur + RED overlay impossible to hide)
 * - LAW C: High Density Information Design (compact headers, tight spacing)
 * - LAW D: Mock Protocol (amber [MOCKED] badges, meta.source='sim')
 * 
 * Every widget MUST use this wrapper. Widgets become pure content renderers.
 * Standard structure:
 * - Header: title + badges + status dot + optional right slot
 * - Body: FailClosedPanel (automatic blur + RED diagnostics on error)
 * - Footer: ProvenanceFooter (always visible)
 * 
 * This prevents drift and ensures 100% F1 compliance.
 */

import React from 'react';
import { FailClosedPanel } from '../common/FailClosedPanel';
import { ProvenanceFooter } from '../common/ProvenanceFooter';
import type { ProvenanceMeta } from '../../lib/runtime/provenance';

export interface WidgetShellProps {
    /** Widget display title */
    title: string;

    /** Badge type (controls color and label) */
    badgeType?: 'LIVE' | 'MOCKED' | 'DATA_NOT_CONNECTED';

    /** Status indicator */
    statusDot?: '🟢' | '⚪' | '🔴';

    /** Optional slot for controls in header (e.g., filters, refresh button) */
    rightHeaderSlot?: React.ReactNode;

    /** Widget content (will be wrapped in FailClosedPanel) */
    children: React.ReactNode;

    /** Provenance metadata (required for footer) */
    meta: ProvenanceMeta;

    /** Error state (null if no error) */
    error: Error | null;

    /** Last good snapshot (for fail-closed display) */
    lastGood?: { data: any; meta: ProvenanceMeta } | null;

    /** Show endpoint in provenance footer (default: true) */
    showEndpoint?: boolean;

    /** Additional STALE badge if data is stale */
    isStale?: boolean;
}

export const WidgetShell: React.FC<WidgetShellProps> = ({
    title,
    badgeType,
    statusDot,
    rightHeaderSlot,
    children,
    meta,
    error,
    lastGood,
    showEndpoint = true,
    isStale = false,
}) => {
    // Badge styling
    const getBadgeStyle = () => {
        switch (badgeType) {
            case 'LIVE':
                return { background: '#10b981', color: '#fff' };
            case 'MOCKED':
                return { background: '#f59e0b', color: '#000' };
            case 'DATA_NOT_CONNECTED':
                return { background: '#dc2626', color: '#fff' };
            default:
                return null;
        }
    };

    const badgeStyle = getBadgeStyle();

    return (
        <div style={{
            background: 'var(--bg-panel)',
            border: '1px solid var(--border-color)',
            borderRadius: '4px',
            display: 'flex',
            flexDirection: 'column',
            height: '100%',
            overflow: 'hidden',
        }}>
            {/* HEADER */}
            <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '6px 8px',
                borderBottom: '1px solid var(--border-color)',
                background: 'var(--bg-panel)',
                flexShrink: 0,
            }}>
                {/* Left: Title + Badges + Status */}
                <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    fontSize: '11px',
                }}>
                    {statusDot && (
                        <span style={{ fontSize: '12px' }}>{statusDot}</span>
                    )}
                    <span style={{
                        fontWeight: 'bold',
                        fontSize: '11px',
                        textTransform: 'uppercase',
                        letterSpacing: '0.5px',
                    }}>
                        {title}
                    </span>
                    {badgeStyle && (
                        <span style={{
                            ...badgeStyle,
                            fontSize: '9px',
                            padding: '2px 4px',
                            borderRadius: '2px',
                            fontWeight: 'bold',
                        }}>
                            [{badgeType}]
                        </span>
                    )}
                    {isStale && (
                        <span style={{
                            background: '#f59e0b',
                            color: '#000',
                            fontSize: '9px',
                            padding: '2px 4px',
                            borderRadius: '2px',
                            fontWeight: 'bold',
                        }}>
                            STALE
                        </span>
                    )}
                </div>

                {/* Right: Optional slot */}
                {rightHeaderSlot && (
                    <div style={{ fontSize: '10px' }}>
                        {rightHeaderSlot}
                    </div>
                )}
            </div>

            {/* BODY (with FailClosedPanel) */}
            <div style={{
                flex: 1,
                overflow: 'auto',
                padding: '8px',
            }}>
                <FailClosedPanel
                    title={title}
                    error={error}
                    meta={meta}
                    lastGoodTs={lastGood?.meta.ts}
                >
                    {children}
                </FailClosedPanel>
            </div>

            {/* FOOTER (Provenance) */}
            <div style={{
                flexShrink: 0,
                padding: '4px 8px',
                borderTop: '1px solid var(--border-color)',
            }}>
                <ProvenanceFooter meta={meta} showEndpoint={showEndpoint} />
            </div>
        </div>
    );
};
