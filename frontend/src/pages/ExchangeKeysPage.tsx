import React, { useEffect, useState } from 'react';
import { getBalances, getExchangeKeys, updateExchangeKeys, testExchangeConnection, deleteExchangeKey } from '../api/adapter';
import { useAuth } from '../hooks/useAuth';
import { useLocation } from 'react-router-dom';
import { useDashboard } from '../context/DashboardContext';
import { ExchangeKey } from '../api/types';
import { useWhy } from '../contexts/WhyContext';
import { previewStore } from '../preview/PreviewStore';

// Helper for masking
const maskSecret = (secret: string) => {
    if (!secret) return '';
    if (secret === '***') return '***';
    return `${secret.substring(0, 3)}...${secret.substring(secret.length - 3)}`;
};

export const ExchangeKeysPage: React.FC = () => {
    const auth = useAuth();
    // Construct client object for adapter authentication
    const client = {
        role: auth.role,
        adminToken: auth.adminToken,
        opsToken: auth.opsToken,
        bearerToken: auth.bearerToken
    };

    const location = useLocation() as { state: any };
    const { openWhy } = useWhy();
    const { addToast } = useDashboard();

    // Preview Store Source State (Hybrid Mode)
    const [useRealData, setUseRealDataState] = useState(previewStore.getState().use_real_data);
    const setUseRealData = (val: boolean) => {
        previewStore.setUseRealData(val);
        setUseRealDataState(val);
        // Trigger re-fetch with delay to allow prop
        setTimeout(() => fetchBalances(), 500);
    };

    const [keys, setKeys] = useState<ExchangeKey[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Modal State
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [editingKey, setEditingKey] = useState<ExchangeKey | null>(null);

    // Form State
    const [formData, setFormData] = useState({
        exchange_id: 'binance',
        api_key: '',
        api_secret: '',
        passphrase: '',
        is_testnet: false,
        permissions: { read: true, trade: true, withdraw: false }
    });
    const [submitting, setSubmitting] = useState(false);

    // Test Results State
    const [testResults, setTestResults] = useState<Record<string, { status: string; latency?: number; message?: string }>>({});

    // Balance State
    const [balances, setBalances] = useState<{ asset: string; free: number; locked: number }[]>([]);
    const [balancesLoading, setBalancesLoading] = useState(false);
    const [showZeroBalances, setShowZeroBalances] = useState(false);
    // Explicit Proof: Store last fetch status/source
    const [fetchStatus, setFetchStatus] = useState<{ code: number, source: 'REAL' | 'SIM', requestId?: string, error?: string } | null>(null);

    useEffect(() => {
        loadKeys();
    }, []);

    const fetchBalances = async () => {
        setBalancesLoading(true);
        // Clear previous balance errors if we are retrying
        // Note: We don't have a specific balanceError state, we use toast. 
        // But for "Inline" message requested, maybe we should add one?
        // Let's stick to Toast + maybe render detail if empty.
        try {
            // Check Explicit Source
            const isReal = previewStore.getState().use_real_data;
            const requestId = crypto.randomUUID();

            // @ts-ignore
            const res = await getBalances(new AbortController().signal, client, requestId);

            setBalances(res.balances || []);
            setFetchStatus({
                code: res.upstream_status || 200,
                source: (res.source as 'REAL' | 'SIM') || (isReal ? 'REAL' : 'SIM'),
                requestId: res.request_id || requestId
            });
            addToast({ type: 'SUCCESS', message: 'Live balances updated successfully' });
        } catch (err: any) {
            console.error(err);
            const isReal = previewStore.getState().use_real_data;

            // Fix: APIError has .status, not .response.status
            const status = err.status || err.response?.status || 500;

            // Extract detailed message from payload if available (Flask returns "error" in body)
            let detailedMsg = err.message || 'Unknown Error';
            if (err.payload && typeof err.payload === 'object') {
                const p = err.payload as any;
                if (p.error) detailedMsg = p.error;
                // Add upstream status if available for debugging
                if (p.upstream_status) detailedMsg += ` (Upstream: ${p.upstream_status})`;
            }

            setFetchStatus({ code: status, source: isReal ? 'REAL' : 'SIM', error: detailedMsg });
            addToast({ type: 'ERROR', message: `Fetch Failed: ${detailedMsg}` });
        } finally {
            setBalancesLoading(false);
        }
    };

    const loadKeys = async () => {
        setLoading(true);
        try {
            // @ts-ignore
            const data = await getExchangeKeys(new AbortController().signal, client);
            setKeys(data);
        } catch (err) {
            addToast({ type: 'ERROR', message: 'Failed to load keys' });
            setError('Failed to load keys');
        } finally {
            setLoading(false);
        }
    };

    const handleOpenModal = (key?: ExchangeKey) => {
        if (key) {
            setEditingKey(key);
            setFormData({
                exchange_id: key.exchange_id,
                api_key: key.api_key,
                api_secret: '', // Never fill secret on edit
                passphrase: '',
                is_testnet: key.is_testnet,
                permissions: key.permissions || { read: true, trade: true, withdraw: false }
            });
        } else {
            setEditingKey(null);
            setFormData({
                exchange_id: 'binance',
                api_key: '',
                api_secret: '',
                passphrase: '',
                is_testnet: false,
                permissions: { read: true, trade: true, withdraw: false }
            });
        }
        setIsModalOpen(true);
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSubmitting(true);
        setError(null);
        try {
            await updateExchangeKeys({
                ...formData,
                api_secret: formData.api_secret || (editingKey ? '***' : '')
            }, new AbortController().signal, client);

            addToast({ type: 'SUCCESS', message: 'Exchange key configuration saved' });
            setIsModalOpen(false);
            await loadKeys();
        } catch (err: any) {
            const msg = err.message || 'Failed to update key';
            addToast({ type: 'ERROR', message: msg });
            setError(msg);
        } finally {
            setSubmitting(false);
        }
    };

    const handleTest = async (key: ExchangeKey) => {
        setTestResults(prev => ({ ...prev, [key.exchange_id]: { status: 'loading' } }));
        try {
            const res = await testExchangeConnection(key.exchange_id, new AbortController().signal, client) as { latency_ms: number; status: string; message?: string };
            setTestResults(prev => ({
                ...prev,
                [key.exchange_id]: {
                    status: res.status,
                    latency: res.latency_ms,
                    message: res.message
                }
            }));
            // Reload keys to update status in list if changed
            loadKeys();
        } catch (e: any) {
            setTestResults(prev => ({
                ...prev,
                [key.exchange_id]: { status: 'error', message: e.message }
            }));
        }
    };

    const handleDelete = async (id: string) => {
        // In a real app we might want a nicer modal, but for now we replace the native confirm with a Toast-based flow?
        // Actually, native confirm is blocking. Non-blocking replacement usually requires a separate modal state.
        // Given the instructions to "replace native alerts", replacing confirm with a custom modal is best.
        // However, for speed, if we want to just remove it or acknowledge it's blocking...
        // "Implementing a global Toast notification system to replace native alerts."
        // Native confirm is also annoying.
        // I'll leave the confirm for DELETION as it is critical, OR I can use a Toast to say "Deleted" after.
        // But better to use `window.confirm` explicitly if we must, or even better, no confirm but an "Undo" toast?
        // No, key revocation is destructive.
        // Let's use a simple window.confirm but wrapped or just keep it for now but add Toast on success/error.
        // Use window.confirm for now but add Toasts.
        if (!window.confirm(`Are you sure you want to revoke keys for ${id}? This cannot be undone.`)) return;

        try {
            await deleteExchangeKey(id, new AbortController().signal, client);
            setKeys(prev => prev.filter(k => k.exchange_id !== id));
            addToast({ type: 'SUCCESS', message: `Revoked keys for ${id}` });
        } catch (e: any) {
            addToast({ type: 'ERROR', message: e.message });
        }
    };

    return (
        <div className="page-container">
            <header className="flex-between" style={{ marginBottom: '2rem' }}>
                <div>
                    {location.state?.tourActive && (
                        <div style={{ marginBottom: '8px' }}>
                            <span className="tiny font-bold uppercase" style={{
                                backgroundColor: 'var(--accent-primary)',
                                color: 'white',
                                padding: '2px 8px',
                                borderRadius: '4px'
                            }}>Step 1 of 7</span>
                        </div>
                    )}
                    <h1 style={{ margin: 0, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Exchange Keys</h1>
                    <div className="small muted">Manage API connections to external venues</div>
                </div>
                <button className="button primary" onClick={() => handleOpenModal()}>
                    + Add Connection
                </button>
            </header>

            {/* ERROR BANNER */}
            {error && (
                <div className="card" style={{ padding: '1rem', borderLeft: '4px solid var(--status-error)', marginBottom: '1rem' }}>
                    <div className="flex-row">
                        <span style={{ color: 'var(--status-error)', fontWeight: 'bold' }}>ERROR</span>
                        <span>{error}</span>
                    </div>
                </div>
            )}

            {/* KEY LIST Table */}
            <div className="card">
                <div className="card-header flex-between">
                    <h3>Configured Exchanges</h3>
                    <div className="small muted">{keys.length} active connections</div>
                </div>

                {loading && keys.length === 0 ? (
                    <div className="padding-2 muted">Loading configuration...</div>
                ) : (
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                            <tr style={{ borderBottom: '1px solid var(--border-color)', textAlign: 'left' }}>
                                <th className="small muted uppercase" style={{ padding: '1rem' }}>Exchange</th>
                                <th className="small muted uppercase" style={{ padding: '1rem' }}>Environment</th>
                                <th className="small muted uppercase" style={{ padding: '1rem' }}>Permissions</th>
                                <th className="small muted uppercase" style={{ padding: '1rem' }}>Recency</th>
                                <th className="small muted uppercase" style={{ padding: '1rem' }}>Status</th>
                                <th className="small muted uppercase" style={{ padding: '1rem', textAlign: 'right' }}>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {keys.map(k => {
                                const testRes = testResults[k.exchange_id];
                                return (
                                    <tr key={k.exchange_id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                                        <td style={{ padding: '1rem' }}>
                                            <div className="flex-row">
                                                <div style={{ width: 8, height: 8, borderRadius: '50%', background: k.status === 'CONNECTED' ? 'var(--status-ok)' : 'var(--status-error)' }} />
                                                <span style={{ fontWeight: 600 }}>{k.exchange_id.toUpperCase()}</span>
                                            </div>
                                            <div className="tiny muted" style={{ marginLeft: '1rem' }}>
                                                ID: {k.api_key.substring(0, 8)}...
                                            </div>
                                        </td>
                                        <td style={{ padding: '1rem' }}>
                                            {k.is_testnet ? (
                                                <span className="status-chip warn">TESTNET</span>
                                            ) : (
                                                <span className="status-chip success">LIVE</span>
                                            )}
                                        </td>
                                        <td style={{ padding: '1rem' }}>
                                            <div className="flex-col gap-1">
                                                <div className="flex-row">
                                                    <span className={`tiny ${k.permissions?.read ? 'success' : 'muted'}`}>READ</span>
                                                    <span className={`tiny ${k.permissions?.trade ? 'success' : 'muted'}`}>TRADE</span>
                                                </div>
                                                <div className="flex-row">
                                                    {k.permissions?.withdraw ? (
                                                        <span className="tiny danger">WITHDRAW</span>
                                                    ) : (
                                                        <span
                                                            className="tiny muted"
                                                            style={{ textDecoration: 'line-through', cursor: 'help' }}
                                                            onClick={() => openWhy({
                                                                ruleId: 'withdraw_disabled',
                                                                context: "Withdrawal permissions are strictly disabled by policy for hot wallets."
                                                            })}
                                                        >
                                                            WITHDRAW
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                        </td>
                                        <td style={{ padding: '1rem' }} className="small muted">
                                            {new Date(k.updated_at).toLocaleDateString()}
                                        </td>
                                        <td style={{ padding: '1rem' }}>
                                            {testRes?.status === 'loading' ? (
                                                <span className="tiny">Testing...</span>
                                            ) : (
                                                <div className="flex-col">
                                                    <span className={`status-chip ${k.status === 'CONNECTED' || k.status === 'CONFIGURED' ? 'success' : 'error'}`}>
                                                        {k.status}
                                                    </span>
                                                    {/* Show Live Test Result if available */}
                                                    {testRes && (
                                                        <span className={`tiny ${testRes.status === 'ok' ? 'success' : 'danger'}`}>
                                                            {testRes.message || (testRes.status === 'ok' ? 'Connected' : 'Failed')}
                                                        </span>
                                                    )}
                                                    {/* Fallback to stored latency */}
                                                    {!testRes && k.last_latency_ms && (
                                                        <span className="tiny muted">{k.last_latency_ms}ms</span>
                                                    )}
                                                </div>
                                            )}
                                        </td>
                                        <td style={{ padding: '1rem', textAlign: 'right' }}>
                                            <div className="flex-row" style={{ justifyContent: 'flex-end', gap: '0.5rem' }}>
                                                <button className="button tiny secondary" onClick={() => handleTest(k)}>
                                                    Test
                                                </button>
                                                <button className="button tiny secondary" onClick={() => handleOpenModal(k)}>
                                                    Edit
                                                </button>
                                                <button className="button tiny danger ghost" onClick={() => handleDelete(k.exchange_id)}>
                                                    Revoke
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                );
                            })}
                            {keys.length === 0 && (
                                <tr>
                                    <td colSpan={6} style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                                        No exchange keys configured. Add one to start trading.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                )}
            </div>

            {/* LIVE BALANCE SNAPSHOT */}
            <div className="card" style={{ marginTop: '2rem' }}>
                <div className="card-header flex-between">
                    <div className="flex-row gap-2">
                        <h3>Live Binance Account Snapshot</h3>
                        {/* Source Indicator */}
                        <div className="flex-row gap-2" style={{ alignItems: 'center' }}>
                            <div className="tiny uppercase font-bold text-muted">SOURCE:</div>
                            <div className="flex-row" style={{ background: '#111', borderRadius: '4px', padding: '2px' }}>
                                <button
                                    className={`button tiny ${!useRealData ? 'primary' : 'ghost'}`}
                                    style={{ padding: '2px 8px' }}
                                    onClick={() => setUseRealData(false)}
                                >
                                    SIM
                                </button>
                                <button
                                    className={`button tiny ${useRealData ? 'warn' : 'ghost'}`}
                                    style={{ padding: '2px 8px' }}
                                    onClick={() => {
                                        if (keys.length === 0) {
                                            addToast({ type: 'ERROR', message: "No Exchange Keys configured. Cannot switch to Real Data." });
                                            return;
                                        }
                                        setUseRealData(true);
                                    }}
                                >
                                    REAL
                                </button>
                            </div>
                        </div>
                        {/* Status Chip */}
                        {useRealData ? (
                            <span className="status-chip warn">READ-ONLY (REAL)</span>
                        ) : (
                            <span className="status-chip success">SIMULATED</span>
                        )}
                    </div>
                    <div className="flex-row gap-2">
                        <label className="flex-row gap-1 tiny muted pointer">
                            <input
                                type="checkbox"
                                checked={showZeroBalances}
                                onChange={e => setShowZeroBalances(e.target.checked)}
                            />
                            Show Zero Balances
                        </label>
                        <button className="button secondary small" onClick={fetchBalances} disabled={balancesLoading}>
                            {balancesLoading ? 'Fetching...' : 'Refresh Balances'}
                        </button>
                    </div>
                </div>

                {/* Security Banner */}
                <div className="padding-2" style={{ background: 'rgba(255, 165, 0, 0.1)', borderBottom: '1px solid var(--border-color)' }}>
                    <div className="flex-row gap-2" style={{ color: 'var(--status-warn)' }}>
                        <span style={{ fontSize: '1.2rem' }}>⚠️</span>
                        <div>
                            <strong>LIVE DATA READING ENABLED — TRADING STILL IN DRY-RUN MODE</strong>
                            <div className="tiny" style={{ opacity: 0.8 }}>
                                The balances below are real-time data from your Binance account.
                                By default, the system remains in <code>TRADING_DRY_RUN=true</code> mode, meaning no executing orders will be sent to the exchange.
                            </div>
                        </div>
                    </div>
                </div>

                {/* Explicit Fetch Proof */}
                {fetchStatus && (
                    <div className="padding-1 tiny flex-row gap-2" style={{ background: fetchStatus.code === 200 ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)', borderBottom: '1px solid var(--border-color)' }}>
                        <span style={{ fontWeight: 'bold', color: fetchStatus.code === 200 ? 'var(--status-ok)' : 'var(--status-error)' }}>
                            [{useRealData ? 'REAL API' : 'SIMULATION'}] Response: {fetchStatus.code}
                        </span>
                        {fetchStatus.error && <span className="text-danger">{fetchStatus.error}</span>}
                    </div>
                )}

                {/* Content */}
                {(() => {
                    const filtered = balances.filter(b => {
                        if (showZeroBalances) return true;
                        return parseFloat(b.free as any) > 0 || parseFloat(b.locked as any) > 0;
                    });

                    if (filtered.length === 0 && !balancesLoading) {
                        return (
                            <div className="padding-2 muted text-center">
                                {balances.length > 0 ? (
                                    <p>No non-zero balances found. <a onClick={() => setShowZeroBalances(true)} className="pointer text-primary">Show zero balances</a>?</p>
                                ) : (
                                    <p>No balances loaded. Click "Refresh Balances" to inspect active assets.</p>
                                )}
                            </div>
                        );
                    }

                    return (
                        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                            <thead>
                                <tr style={{ borderBottom: '1px solid var(--border-color)', textAlign: 'left' }}>
                                    <th className="small muted uppercase" style={{ padding: '1rem' }}>Asset</th>
                                    <th className="small muted uppercase" style={{ padding: '1rem', textAlign: 'right' }}>Free</th>
                                    <th className="small muted uppercase" style={{ padding: '1rem', textAlign: 'right' }}>Locked</th>
                                    <th className="small muted uppercase" style={{ padding: '1rem', textAlign: 'right' }}>Total</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filtered.map((b) => {
                                    const free = typeof b.free === 'string' ? parseFloat(b.free) : b.free;
                                    const locked = typeof b.locked === 'string' ? parseFloat(b.locked) : b.locked;
                                    const total = free + locked;
                                    return (
                                        <tr key={b.asset} style={{ borderBottom: '1px solid var(--border-color)' }}>
                                            <td style={{ padding: '1rem', fontWeight: 600 }}>{b.asset}</td>
                                            <td style={{ padding: '1rem', textAlign: 'right', fontFamily: 'monospace' }}>{free.toLocaleString(undefined, { maximumFractionDigits: 8 })}</td>
                                            <td style={{ padding: '1rem', textAlign: 'right', fontFamily: 'monospace', color: 'var(--text-muted)' }}>{locked > 0 ? locked.toLocaleString(undefined, { maximumFractionDigits: 8 }) : '-'}</td>
                                            <td style={{ padding: '1rem', textAlign: 'right', fontFamily: 'monospace' }}>{total.toLocaleString(undefined, { maximumFractionDigits: 8 })}</td>
                                        </tr>
                                    )
                                })}
                            </tbody>
                        </table>
                    );
                })()}
            </div>

            {/* ADD/EDIT MODAL */}
            {isModalOpen && (
                <div className="modal-overlay">
                    <div className="modal card" style={{ maxWidth: '500px', width: '100%' }}>
                        <div className="card-header flex-between">
                            <h3>{editingKey ? 'Edit Configuration' : 'Add New Connection'}</h3>
                            <button className="button text" onClick={() => setIsModalOpen(false)}>✕</button>
                        </div>
                        <div className="padding-2">
                            <form onSubmit={handleSubmit} className="grid gap-2">
                                <div>
                                    <label className="small muted">Exchange</label>
                                    <select
                                        value={formData.exchange_id}
                                        onChange={e => setFormData({ ...formData, exchange_id: e.target.value })}
                                        className="input"
                                        disabled={!!editingKey} // Cannot change ID on edit
                                    >
                                        <option value="binance">Binance</option>
                                        <option value="okx">OKX</option>
                                        <option value="bybit">Bybit</option>
                                        <option value="kraken">Kraken</option>
                                        <option value="coinbase">Coinbase</option>
                                    </select>
                                </div>

                                <div className="grid cols-2 gap-2">
                                    <div>
                                        <label className="small muted">API Key</label>
                                        <input
                                            type="text"
                                            value={formData.api_key}
                                            onChange={e => setFormData({ ...formData, api_key: e.target.value })}
                                            className="input"
                                            required
                                            placeholder="Ex. A1B2C3..."
                                        />
                                    </div>
                                    <div>
                                        <label className="small muted">Passphrase</label>
                                        <input
                                            type="password"
                                            value={formData.passphrase}
                                            onChange={e => setFormData({ ...formData, passphrase: e.target.value })}
                                            className="input"
                                            placeholder="Optional"
                                        />
                                    </div>
                                </div>

                                <div>
                                    <label className="small muted">API Secret</label>
                                    <input
                                        type="password"
                                        value={formData.api_secret}
                                        onChange={e => setFormData({ ...formData, api_secret: e.target.value })}
                                        className="input"
                                        required={!editingKey} // Only required for new keys
                                        placeholder={editingKey ? 'Unchanged (Enter to rotate)' : 'Ex. Secret...'}
                                    />
                                </div>

                                <div className="card padding-1" style={{ background: 'rgba(255,255,255,0.02)' }}>
                                    <label className="tiny uppercase font-bold" style={{ display: 'block', marginBottom: '0.5rem' }}>Permissions Scope</label>
                                    <div className="flex-row gap-2">
                                        <label className="flex-row gap-1 pointer">
                                            <input
                                                type="checkbox"
                                                checked={formData.permissions.read}
                                                onChange={e => setFormData({ ...formData, permissions: { ...formData.permissions, read: e.target.checked } })}
                                            />
                                            <span className="small">Reading Info</span>
                                        </label>
                                        <label className="flex-row gap-1 pointer">
                                            <input
                                                type="checkbox"
                                                checked={formData.permissions.trade}
                                                onChange={e => setFormData({ ...formData, permissions: { ...formData.permissions, trade: e.target.checked } })}
                                            />
                                            <span className="small">Spot Trading</span>
                                        </label>
                                        <label className="flex-row gap-1 pointer disabled">
                                            <input
                                                type="checkbox"
                                                checked={formData.permissions.withdraw}
                                                disabled
                                            />
                                            <span className="small muted">Withdraw (Disabled)</span>
                                        </label>
                                    </div>
                                </div>

                                <div className="flex-row gap-2" style={{ marginTop: '0.5rem' }}>
                                    <input
                                        type="checkbox"
                                        id="modal-testnet"
                                        checked={formData.is_testnet}
                                        onChange={e => setFormData({ ...formData, is_testnet: e.target.checked })}
                                    />
                                    <label htmlFor="modal-testnet" className="small">Use Testnet Environment</label>
                                </div>

                                <div className="flex-end gap-1" style={{ marginTop: '1rem' }}>
                                    <button type="button" className="button secondary" onClick={() => setIsModalOpen(false)}>Cancel</button>
                                    <button type="submit" className="button primary" disabled={submitting}>
                                        {submitting ? 'Saving...' : 'Save Configuration'}
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};
