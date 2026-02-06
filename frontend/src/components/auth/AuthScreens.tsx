/**
 * Integration Gate I.2 — Auth Screens
 * 
 * Visible auth error/state screens.
 * NO SILENT AUTH FAILURES.
 */

import React from 'react';
import type { AuthControllerContext } from '../../lib/authTypes';

// ------------------------------------------------------------
// AUTH UNAVAILABLE SCREEN (Transport failure)
// ------------------------------------------------------------

export const AuthUnavailableScreen: React.FC<{ context: AuthControllerContext }> = ({ context }) => {
    return (
        <div className="flex-center flex-column" style={{ height: '100vh', gap: '1.5rem', padding: '2rem' }}>
            <div style={{ fontSize: '4rem', color: '#ff8800' }}>⚠️</div>
            <h1 style={{ margin: 0, color: '#fff' }}>Auth Service Unavailable</h1>
            <p style={{ color: '#aaa', maxWidth: '500px', textAlign: 'center', margin: 0 }}>
                Unable to reach the authentication service. This may be due to network issues or server maintenance.
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
                <div><strong>Endpoint:</strong> /api/v1/auth/me</div>
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
// AUTH SERVER ERROR SCREEN (5xx)
// ------------------------------------------------------------

export const AuthServerErrorScreen: React.FC<{ context: AuthControllerContext }> = ({ context }) => {
    const statusCode = typeof context.lastProbeStatus === 'number' ? context.lastProbeStatus : 'Unknown';

    return (
        <div className="flex-center flex-column" style={{ height: '100vh', gap: '1.5rem', padding: '2rem' }}>
            <div style={{ fontSize: '4rem', color: '#ff3300' }}>🔥</div>
            <h1 style={{ margin: 0, color: '#fff' }}>Auth Server Error</h1>
            <p style={{ color: '#aaa', maxWidth: '500px', textAlign: 'center', margin: 0 }}>
                The authentication server encountered an internal error. Please try again or contact support if this continues.
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
                    Server Error - Authentication service is experiencing issues.
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
                <div><strong>Endpoint:</strong> /api/v1/auth/me</div>
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
// AUTH BOOTING SCREEN (Optional - can reuse BootScreen)
// ------------------------------------------------------------

export const AuthBootingScreen: React.FC<{ context: AuthControllerContext }> = ({ context }) => {
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
            <h2 style={{ margin: 0, color: '#fff' }}>Authenticating...</h2>
            <p style={{ color: '#888', margin: 0 }}>
                Verifying session... ({elapsed.toFixed(1)}s)
            </p>
            {elapsed > 2.5 && (
                <p style={{ color: '#ff8800', fontSize: '0.85rem', margin: 0 }}>
                    Taking longer than expected...
                </p>
            )}
        </div>
    );
};
