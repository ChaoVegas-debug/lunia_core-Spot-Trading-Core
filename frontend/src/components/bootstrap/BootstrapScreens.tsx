/**
 * Integration Gate I.1 — Bootstrap Screens
 * 
 * Mandatory visible screens for every bootstrap state.
 * NO STATE MAY RENDER NULL OR BLANK.
 */

import React from 'react';
import type { BootstrapContext } from '../../lib/bootstrapTypes';

// ------------------------------------------------------------
// BOOTING SCREEN (HARDENED: Shows elapsed time, never infinite)
// ------------------------------------------------------------

export const BootScreen: React.FC<{ context: BootstrapContext }> = ({ context }) => {
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
            <h2 style={{ margin: 0, color: '#fff' }}>Initializing...</h2>
            <p style={{ color: '#888', margin: 0 }}>
                Probing <code>/api/health</code>... ({elapsed.toFixed(1)}s)
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
// BACKEND UNREACHABLE SCREEN
// ------------------------------------------------------------

export const BackendDownScreen: React.FC<{ context: BootstrapContext }> = ({ context }) => {
    return (
        <div className="flex-center flex-column" style={{ height: '100vh', gap: '1.5rem', padding: '2rem' }}>
            <div style={{ fontSize: '4rem', color: '#ff4444' }}>⚠️</div>
            <h1 style={{ margin: 0, color: '#fff' }}>Backend Unreachable</h1>
            <p style={{ color: '#aaa', maxWidth: '500px', textAlign: 'center', margin: 0 }}>
                Unable to connect to the LUNIA backend API. This may be due to network issues,
                server maintenance, or a temporary outage.
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
                <div><strong>API Base:</strong> {context.backendUrl}</div>
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
// BACKEND ERROR SCREEN (5xx - NEW in I.1.1 hotfix)
// ------------------------------------------------------------

export const BackendErrorScreen: React.FC<{ context: BootstrapContext }> = ({ context }) => {
    const statusCode = typeof context.lastProbeStatus === 'number' ? context.lastProbeStatus : 'Unknown';

    return (
        <div className="flex-center flex-column" style={{ height: '100vh', gap: '1.5rem', padding: '2rem' }}>
            <div style={{ fontSize: '4rem', color: '#ff6600' }}>🔥</div>
            <h1 style={{ margin: 0, color: '#fff' }}>Backend Server Error</h1>
            <p style={{ color: '#aaa', maxWidth: '500px', textAlign: 'center', margin: 0 }}>
                The LUNIA backend is experiencing an internal server error. This is not a network issue -
                the server responded but encountered an error while processing the request.
            </p>

            <div style={{
                background: 'rgba(255,100,0,0.1)',
                border: '1px solid rgba(255,100,0,0.3)',
                padding: '1.5rem',
                borderRadius: '8px',
                color: '#ff8844',
                maxWidth: '500px',
                width: '100%',
            }}>
                <div style={{ fontSize: '2rem', fontWeight: 'bold', marginBottom: '0.5rem' }}>
                    HTTP {statusCode}
                </div>
                <div style={{ fontSize: '0.9rem', marginBottom: '1rem' }}>
                    Server Error - Please try again or contact support if this persists.
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
                <div><strong>API Base:</strong> {context.backendUrl}</div>
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
// UNAUTHORIZED SCREEN (401)
// ------------------------------------------------------------

export const UnauthorizedScreen: React.FC<{ context: BootstrapContext }> = ({ context }) => {
    return (
        <div className="flex-center flex-column" style={{ height: '100vh', gap: '1.5rem', padding: '2rem' }}>
            <div style={{ fontSize: '4rem' }}>🔒</div>
            <h1 style={{ margin: 0, color: '#fff' }}>Authentication Required</h1>
            <p style={{ color: '#aaa', maxWidth: '500px', textAlign: 'center', margin: 0 }}>
                You must be logged in to access this resource.
            </p>

            <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
                <a href="/login" className="button primary" style={{ padding: '0.75rem 2rem' }}>
                    Log In
                </a>
                <button onClick={context.retry} className="button secondary" style={{ padding: '0.75rem 2rem' }}>
                    Retry
                </button>
            </div>
        </div>
    );
};

// ------------------------------------------------------------
// FORBIDDEN SCREEN (403)
// ------------------------------------------------------------

export const ForbiddenScreen: React.FC<{ context: BootstrapContext }> = ({ context }) => {
    return (
        <div className="flex-center flex-column" style={{ height: '100vh', gap: '1.5rem', padding: '2rem' }}>
            <div style={{ fontSize: '4rem' }}>🚫</div>
            <h1 style={{ margin: 0, color: '#fff' }}>Access Denied</h1>
            <p style={{ color: '#aaa', maxWidth: '500px', textAlign: 'center', margin: 0 }}>
                You do not have permission to access this resource.
            </p>

            {context.governanceReason && (
                <div style={{
                    background: 'rgba(255,100,100,0.1)',
                    border: '1px solid rgba(255,100,100,0.3)',
                    padding: '1rem',
                    borderRadius: '8px',
                    color: '#ff6666',
                    maxWidth: '500px',
                }}>
                    <strong>Reason:</strong> {context.governanceReason}
                </div>
            )}

            <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
                <a href="/" className="button secondary" style={{ padding: '0.75rem 2rem' }}>
                    Go Home
                </a>
                <button onClick={context.retry} className="button secondary" style={{ padding: '0.75rem 2rem' }}>
                    Retry
                </button>
            </div>
        </div>
    );
};

// ------------------------------------------------------------
// SYSTEM HALTED SCREEN (409 / GLOBAL STOP)
// ------------------------------------------------------------

export const SystemHaltedScreen: React.FC<{ context: BootstrapContext }> = ({ context }) => {
    return (
        <div className="flex-center flex-column" style={{
            height: '100vh',
            gap: '1.5rem',
            padding: '2rem',
            background: 'linear-gradient(180deg, rgba(255,0,0,0.1) 0%, rgba(0,0,0,1) 100%)',
        }}>
            <div style={{ fontSize: '5rem', animation: 'pulse 1.5s ease-in-out infinite' }}>🛑</div>
            <h1 style={{ margin: 0, color: '#ff4444', fontSize: '2.5rem', fontWeight: 'bold' }}>
                SYSTEM HALTED
            </h1>
            <p style={{ color: '#ffaaaa', maxWidth: '600px', textAlign: 'center', margin: 0, fontSize: '1.1rem' }}>
                Trading operations are currently suspended by system governance.
                All execution is paused. Contact your system administrator.
            </p>

            {context.governanceReason && (
                <div style={{
                    background: 'rgba(255,0,0,0.2)',
                    border: '2px solid rgba(255,0,0,0.5)',
                    padding: '1.5rem',
                    borderRadius: '8px',
                    color: '#ff6666',
                    maxWidth: '600px',
                    fontFamily: 'monospace',
                }}>
                    <strong>HALT REASON:</strong> {context.governanceReason}
                </div>
            )}

            <button
                onClick={context.retry}
                className="button secondary"
                style={{ marginTop: '1rem', padding: '0.75rem 2rem', fontSize: '1rem' }}
            >
                Check Status
            </button>
        </div>
    );
};

// ------------------------------------------------------------
// GOVERNANCE BLOCKED SCREEN (veto/drift/airlock)
// ------------------------------------------------------------

export const GovernanceBlockedScreen: React.FC<{ context: BootstrapContext }> = ({ context }) => {
    return (
        <div className="flex-center flex-column" style={{ height: '100vh', gap: '1.5rem', padding: '2rem' }}>
            <div style={{ fontSize: '4rem' }}>⚖️</div>
            <h1 style={{ margin: 0, color: '#ffa500' }}>Governance Block Active</h1>
            <p style={{ color: '#aaa', maxWidth: '600px', textAlign: 'center', margin: 0 }}>
                This action has been blocked by system governance rules. Review the details below.
            </p>

            {context.governanceReason && (
                <div style={{
                    background: 'rgba(255,165,0,0.1)',
                    border: '1px solid rgba(255,165,0,0.3)',
                    padding: '1.5rem',
                    borderRadius: '8px',
                    color: '#ffaa00',
                    maxWidth: '600px',
                }}>
                    <div style={{ marginBottom: '0.5rem' }}><strong>Block Type:</strong> Governance Veto / Drift / Airlock</div>
                    <div><strong>Reason:</strong> {context.governanceReason}</div>
                </div>
            )}

            <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
                <a href="/admin" className="button secondary" style={{ padding: '0.75rem 2rem' }}>
                    Review Governance
                </a>
                <button onClick={context.retry} className="button secondary" style={{ padding: '0.75rem 2rem' }}>
                    Retry
                </button>
            </div>
        </div>
    );
};

// ------------------------------------------------------------
// CRASH SCREEN (Enhanced Error Boundary Fallback)
// ------------------------------------------------------------

export const CrashScreen: React.FC<{
    error: Error;
    errorInfo?: React.ErrorInfo;
    reset?: () => void;
}> = ({ error, errorInfo, reset }) => {
    const diagnostics = JSON.stringify({
        error: {
            name: error.name,
            message: error.message,
            stack: error.stack,
        },
        componentStack: errorInfo?.componentStack,
        timestamp: new Date().toISOString(),
        userAgent: navigator.userAgent,
    }, null, 2);

    const copyDiagnostics = () => {
        navigator.clipboard.writeText(diagnostics);
        alert('Diagnostics copied to clipboard');
    };

    return (
        <div className="flex-center flex-column" style={{
            height: '100vh',
            gap: '1.5rem',
            padding: '2rem',
            background: '#1a1a1a',
        }}>
            <div style={{ fontSize: '4rem' }}>💥</div>
            <h1 style={{ margin: 0, color: '#ff4444' }}>Application Crashed</h1>
            <p style={{ color: '#aaa', maxWidth: '600px', textAlign: 'center', margin: 0 }}>
                An unexpected error occurred. The error details are shown below.
            </p>

            <div style={{
                background: 'rgba(255,50,50,0.1)',
                border: '1px solid rgba(255,50,50,0.3)',
                padding: '1rem',
                borderRadius: '8px',
                maxWidth: '700px',
                width: '100%',
                maxHeight: '300px',
                overflow: 'auto',
                fontFamily: 'monospace',
                fontSize: '0.85rem',
                color: '#ff6666',
            }}>
                <div><strong>Error:</strong> {error.message}</div>
                <div style={{ marginTop: '0.5rem', color: '#888', fontSize: '0.75rem', whiteSpace: 'pre-wrap' }}>
                    {error.stack}
                </div>
                {errorInfo?.componentStack && (
                    <div style={{ marginTop: '1rem', color: '#888', fontSize: '0.75rem', whiteSpace: 'pre-wrap' }}>
                        <strong>Component Stack:</strong>
                        {errorInfo.componentStack}
                    </div>
                )}
            </div>

            <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
                {reset && (
                    <button onClick={reset} className="button primary" style={{ padding: '0.75rem 2rem' }}>
                        Reload Application
                    </button>
                )}
                <button onClick={copyDiagnostics} className="button secondary" style={{ padding: '0.75rem 2rem' }}>
                    Copy Diagnostics
                </button>
                <button onClick={() => window.location.href = '/'} className="button secondary" style={{ padding: '0.75rem 2rem' }}>
                    Go Home
                </button>
            </div>
        </div>
    );
};
