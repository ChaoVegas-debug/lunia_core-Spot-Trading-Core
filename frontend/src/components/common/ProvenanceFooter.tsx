/**
 * PROVENANCE FOOTER
 * 
 * Implements UI Constitution LAW 4 (Golden Thread).
 * 
 * Always visible widget footer displaying:
 * - REQ: Request ID (8-char hash)
 * - LAT: Latency (ms)
 * - AGE: Data age (seconds)
 * - TS: Timestamp (HH:MM:SS)
 * - SRC: Source (network|cache|sim|unknown)
 * - EP: Endpoint (short form)
 * 
 * Usage:
 *   <ProvenanceFooter meta={meta} />
 */

import React from 'react';
import type { ProvenanceMeta } from '../../lib/runtime/provenance';
import { formatProvenance, normalizeEndpoint } from '../../lib/runtime/provenance';

export interface ProvenanceFooterProps {
    meta: ProvenanceMeta;
    showEndpoint?: boolean;
}

export const ProvenanceFooter: React.FC<ProvenanceFooterProps> = ({
    meta,
    showEndpoint = true,
}) => {
    const formatted = formatProvenance(meta);
    const endpoint = showEndpoint ? normalizeEndpoint(meta.endpoint || '') : null;

    // Color coding based on age
    const ageColor = meta.age_s < 10
        ? '#888'  // Normal
        : meta.age_s < 60
            ? '#f59e0b'  // Amber (stale)
            : '#dc2626';  // Red (decayed)

    return (
        <div style={{
            marginTop: '0.5rem',
            paddingTop: '0.5rem',
            borderTop: '1px solid var(--border-color)',
            fontSize: '9px',
            fontFamily: 'monospace',
            color: '#666',
            display: 'flex',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '0.5rem'
        }}>
            <div>{formatted}</div>
            {endpoint && (
                <div style={{ color: '#555' }}>EP: {endpoint}</div>
            )}
            {meta.age_s > 10 && (
                <div style={{
                    color: ageColor,
                    fontWeight: 'bold',
                    textTransform: 'uppercase'
                }}>
                    {meta.age_s > 60 ? 'DECAYED' : 'STALE'}
                </div>
            )}
        </div>
    );
};
