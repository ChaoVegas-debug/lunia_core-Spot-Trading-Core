/**
 * FAIL-CLOSED PANEL
 * 
 * Implements UI Constitution LAW 3 (Fail-Closed + DEFCON Awareness).
 * 
 * Displays widget content with institutional-grade error handling:
 * - Blurs content on error
 * - Shows RED banner with forensic diagnostics
 * - Displays lastGoodTs if available
 * - Reveals NonJsonResponseError details (status, content_type, snippet)
 * 
 * Usage:
 *   <FailClosedPanel
 *     title="Live Balances"
 *     error={error}
 *     meta={meta}
 *     lastGoodTs={lastGood?.meta.ts}
 *   >
 *     <BalancesTable data={data} />
 *   </FailClosedPanel>
 */

import React from 'react';
import type { ProvenanceMeta } from '../../lib/runtime/provenance';
import { isNonJsonResponseError, isJsonParseError, isHttpError } from '../../lib/api/normalizeResponse';

export interface FailClosedPanelProps {
    title: string;
    error: Error | null;
    meta: ProvenanceMeta;
    lastGoodTs?: number;
    children: React.ReactNode;
}

export const FailClosedPanel: React.FC<FailClosedPanelProps> = ({
    title,
    error,
    meta,
    lastGoodTs,
    children,
}) => {
    if (!error) {
        return <>{children}</>;
    }

    // Format last good timestamp
    const lastGoodTime = lastGoodTs
        ? new Date(lastGoodTs).toLocaleTimeString()
        : undefined;
    const lastGoodAge = lastGoodTs
        ? Math.floor((Date.now() - lastGoodTs) / 1000)
        : undefined;

    // Extract error details
    let errorType = error.name || 'ERROR';
    let errorMessage = error.message;
    let diagnostics: React.ReactNode = null;

    if (isNonJsonResponseError(error)) {
        diagnostics = (
            <div style={{ fontSize: '10px', marginTop: '0.5rem', fontFamily: 'monospace' }}>
                <div><strong>HTTP Status</strong>: {error.http_status}</div>
                <div><strong>Content-Type</strong>: {error.content_type}</div>
                <div><strong>Endpoint</strong>: {error.endpoint}</div>
                <div><strong>Hint</strong>: {error.hint}</div>
                <div style={{ marginTop: '0.5rem' }}>
                    <strong>Response Snippet</strong> (first 200 chars):
                    <pre style={{
                        background: '#1a1a1a',
                        padding: '0.5rem',
                        borderRadius: '3px',
                        overflow: 'auto',
                        maxHeight: '100px',
                        marginTop: '0.25rem'
                    }}>
                        {error.snippet}
                    </pre>
                </div>
            </div>
        );
    } else if (isJsonParseError(error)) {
        diagnostics = (
            <div style={{ fontSize: '10px', marginTop: '0.5rem', fontFamily: 'monospace' }}>
                <div><strong>HTTP Status</strong>: {error.http_status}</div>
                <div><strong>Endpoint</strong>: {error.endpoint}</div>
                <div style={{ marginTop: '0.5rem' }}>
                    <strong>Response Snippet</strong>:
                    <pre style={{
                        background: '#1a1a1a',
                        padding: '0.5rem',
                        borderRadius: '3px',
                        overflow: 'auto',
                        maxHeight: '100px',
                        marginTop: '0.25rem'
                    }}>
                        {error.snippet}
                    </pre>
                </div>
            </div>
        );
    } else if (isHttpError(error)) {
        diagnostics = (
            <div style={{ fontSize: '10px', marginTop: '0.5rem', fontFamily: 'monospace' }}>
                <div><strong>HTTP Status</strong>: {error.http_status}</div>
                <div><strong>Endpoint</strong>: {error.endpoint}</div>
                {error.response_text && (
                    <div style={{ marginTop: '0.5rem' }}>
                        <strong>Response</strong>:
                        <pre style={{
                            background: '#1a1a1a',
                            padding: '0.5rem',
                            borderRadius: '3px',
                            overflow: 'auto',
                            maxHeight: '100px',
                            marginTop: '0.25rem'
                        }}>
                            {error.response_text}
                        </pre>
                    </div>
                )}
            </div>
        );
    }

    return (
        <div style={{ position: 'relative' }}>
            {/* Blurred children */}
            <div style={{ filter: 'blur(4px)', opacity: 0.3, pointerEvents: 'none' }}>
                {children}
            </div>

            {/* Error overlay */}
            <div style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: 'rgba(220, 38, 38, 0.1)',
                backdropFilter: 'blur(4px)',
                zIndex: 10,
            }}>
                <div style={{
                    background: '#dc2626',
                    color: '#fff',
                    padding: '1rem',
                    borderRadius: '4px',
                    maxWidth: '600px',
                    fontFamily: 'monospace',
                    fontSize: '11px',
                }}>
                    <div style={{ fontWeight: 'bold', fontSize: '13px', marginBottom: '0.5rem' }}>
                        ❌ DATA NOT CONNECTED - {title}
                    </div>

                    <div style={{ marginBottom: '0.5rem' }}>
                        <strong>{errorType}</strong>: {errorMessage}
                    </div>

                    {diagnostics}

                    {lastGoodTime && (
                        <div style={{
                            marginTop: '0.75rem',
                            paddingTop: '0.75rem',
                            borderTop: '1px solid rgba(255,255,255,0.3)',
                            fontSize: '10px'
                        }}>
                            <strong>Last Success</strong>: {lastGoodTime} ({lastGoodAge}s ago)
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};
