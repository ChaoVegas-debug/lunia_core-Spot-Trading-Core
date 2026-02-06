/**
 * Integration Gate I.3 — Entitlement Screens
 * 
 * Visible tier/subscription error screens.
 * NO SILENT TIER DENIALS.
 */

import React from 'react';
import type { EntitlementControllerContext } from '../../lib/entitlementTypes';

// ------------------------------------------------------------
// ENTITLEMENT BOOTING SCREEN
// ------------------------------------------------------------

export const EntitlementBootingScreen: React.FC<{ context: EntitlementControllerContext }> = ({ context }) => {
    const elapsed = context.elapsedSeconds || 0;

    return (
        <div className="flex-center flex-column" style={{ height: '100vh', gap: '2rem' }}>
            <div className="spinner" style={{
                width: '64px',
                height: '64px',
                border: '4px solid rgba(255, 255, 255, 0.1)',
                borderTop: '4px solid #00d4ff',
                borderRadius: '50%',
                animation: 'spin 0.8s linear infinite',
            }} />
            <h2 style={{ margin: 0, color: '#fff' }}>Verifying Subscription...</h2>
            <p style={{ color: '#888', margin: 0 }}>
                Checking tier entitlements... ({elapsed.toFixed(1)}s)
            </p>
            {elapsed > 2.5 && (
                <p style={{ color: '#ff8800', fontSize: '0.85rem', margin: 0 }}>
                    Taking longer than expected...
                </p>
            )}
        </div>
    );
};

// ------------------------------------------------------------
// ENTITLEMENT UNAVAILABLE SCREEN (Transport failure)
// ------------------------------------------------------------

export const EntitlementUnavailableScreen: React.FC<{ context: EntitlementControllerContext }> = ({ context }) => {
    return (
        <div className="flex-center flex-column" style={{ height: '100vh', gap: '1.5rem', padding: '2rem' }}>
            <div style={{ fontSize: '4rem', color: '#ff8800' }}>⚠️</div>
            <h1 style={{ margin: 0, color: '#fff' }}>Subscription Service Unavailable</h1>
            <p style={{ color: '#aaa', maxWidth: '500px', textAlign: 'center', margin: 0 }}>
                Unable to verify your subscription tier. This may be due to network issues or server maintenance.
            </p>

            <div style={{
                background: 'rgba(255,255,255,0.05)',
                padding: '1rem',
                borderRadius: '8px',
                fontFamily: 'monospace',
                fontSize: '0.85rem',
                color: '#888',
                maxWidth: '500px',
                width: '100%',
            }}>
                <div><strong>Endpoint:</strong> /api/v1/auth/me (tier validation)</div>
                <div><strong>Last Probe:</strong> {context.lastProbeTime || 'N/A'}</div>
                <div><strong>Status:</strong> {context.lastProbeStatus || 'N/A'}</div>
                {context.errorMessage && <div><strong>Error:</strong> {context.errorMessage}</div>}
            </div>

            <button
                onClick={context.retry}
                className="button primary"
                style={{ marginTop: '1rem', padding: '0.75rem 2rem', fontSize: '1rem' }}
            >
                Retry Connection
            </button>
        </div>
    );
};

// ------------------------------------------------------------
// ENTITLEMENT SERVER ERROR SCREEN (5xx)
// ------------------------------------------------------------

export const EntitlementServerErrorScreen: React.FC<{ context: EntitlementControllerContext }> = ({ context }) => {
    const statusCode = typeof context.lastProbeStatus === 'number' ? context.lastProbeStatus : 'Unknown';

    return (
        <div className="flex-center flex-column" style={{ height: '100vh', gap: '1.5rem', padding: '2rem' }}>
            <div style={{ fontSize: '4rem', color: '#ff3300' }}>🔥</div>
            <h1 style={{ margin: 0, color: '#fff' }}>Subscription Service Error</h1>
            <p style={{ color: '#aaa', maxWidth: '500px', textAlign: 'center', margin: 0 }}>
                The subscription verification service encountered an internal error. Please try again or contact support.
            </p>

            <div style={{
                background: 'rgba(255,50,0,0.1)',
                border: '1px solid rgba(255,50,0,0.3)',
                padding: '1.5rem',
                borderRadius: '8px',
                color: '#ff6644',
                maxWidth: '500px',
                width: '100%',
            }}>
                <div style={{ fontSize: '2rem', fontWeight: 'bold', marginBottom: '0.5rem' }}>
                    HTTP {statusCode}
                </div>
                <div style={{ fontSize: '0.9rem' }}>
                    Server Error - Subscription service is experiencing issues.
                </div>
            </div>

            <div style={{
                background: 'rgba(255,255,255,0.05)',
                padding: '1rem',
                borderRadius: '8px',
                fontFamily: 'monospace',
                fontSize: '0.85rem',
                color: '#888',
                maxWidth: '500px',
                width: '100%',
            }}>
                <div><strong>Endpoint:</strong> /api/v1/auth/me (tier validation)</div>
                <div><strong>Last Probe:</strong> {context.lastProbeTime || 'N/A'}</div>
                <div><strong>Status:</strong> {context.lastProbeStatus || 'N/A'}</div>
                {context.errorMessage && <div><strong>Error:</strong> {context.errorMessage}</div>}
            </div>

            <button
                onClick={context.retry}
                className="button primary"
                style={{ marginTop: '1rem', padding: '0.75rem 2rem', fontSize: '1rem' }}
            >
                Retry
            </button>
        </div>
    );
};

// ------------------------------------------------------------
// ENTITLEMENT MALFORMED SCREEN (Tier invalid/missing)
// ------------------------------------------------------------

export const EntitlementMalformedScreen: React.FC<{ context: EntitlementControllerContext }> = ({ context }) => {
    return (
        <div className="flex-center flex-column" style={{ height: '100vh', gap: '1.5rem', padding: '2rem' }}>
            <div style={{ fontSize: '4rem', color: '#ffaa00' }}>❌</div>
            <h1 style={{ margin: 0, color: '#fff' }}>Subscription Data Invalid</h1>
            <p style={{ color: '#aaa', maxWidth: '500px', textAlign: 'center', margin: 0 }}>
                Your subscription tier data is missing or invalid. Please contact support for assistance.
            </p>

            <div style={{
                background: 'rgba(255,170,0,0.1)',
                border: '1px solid rgba(255,170,0,0.3)',
                padding: '1.5rem',
                borderRadius: '8px',
                color: '#ffaa00',
                maxWidth: '500px',
                width: '100%',
                textAlign: 'center',
            }}>
                <div style={{ fontSize: '0.9rem', marginBottom: '0.5rem' }}>
                    <strong>Technical Details:</strong>
                </div>
                <div style={{ fontSize: '0.85rem', fontFamily: 'monospace' }}>
                    {context.errorMessage || 'Tier field missing or not recognized'}
                </div>
            </div>

            <div className="flex-col gap-2 mt-4" style={{ width: '100%', maxWidth: '500px' }}>
                <button
                    onClick={context.retry}
                    className="button primary full-width"
                >
                    Retry Verification
                </button>
                <a
                    href="mailto:support@lunia.fi?subject=Subscription%20Tier%20Issue"
                    className="button ghost full-width"
                    style={{ textDecoration: 'none' }}
                >
                    Contact Support
                </a>
            </div>
        </div>
    );
};
