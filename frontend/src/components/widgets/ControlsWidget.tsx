import React, { useState } from 'react';
import { hasControlAccess, useAuth } from '../../hooks/useAuth';
import { postAutoOff, postAutoOn, postStartAll, postStopAll } from '../../api/endpoints';
import { APIError } from '../../api/errors';
import { addAuditEntry } from '../../utils/auditLog';

interface Props {
  disabledReason?: string;
}

export const ControlsWidget: React.FC<Props> = ({ disabledReason }) => {
  const auth = useAuth();
  const [message, setMessage] = useState<string>('');
  const [error, setError] = useState<string>('');

  const client = {
    role: auth.role,
    adminToken: auth.adminToken,
    opsToken: auth.opsToken,
    bearerToken: auth.bearerToken
  };

  if (!hasControlAccess(auth.role)) {
    return <div className="card small">Controls are read-only for this role.</div>;
  }

  const run = async (action: (signal: AbortSignal) => Promise<unknown>, label: string) => {
    if (disabledReason) {
      setError(disabledReason);
      return;
    }
    if (!window.confirm(`Confirm action: ${label}?`)) {
      return;
    }
    const controller = new AbortController();
    setMessage(`Running ${label}...`);
    setError('');
    try {
      await action(controller.signal);
      const ts = new Date().toISOString();
      addAuditEntry({ ts, action: label, ok: true });
      setMessage(`${label} executed`);
    } catch (err) {
      const apiErr = err as APIError;
      const msg = apiErr.message || 'Unknown error';
      setError(msg);
      addAuditEntry({ ts: new Date().toISOString(), action: label, ok: false, details: msg });
    }
  };

  const disabled = !client.adminToken || Boolean(disabledReason);

  return (
    <div className="card">
      <div className="section-header">
        <h3>Controls</h3>
        <span className="small">Admin/Trader only</span>
      </div>
      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
        <button className="button" disabled={disabled} onClick={() => run((signal) => postAutoOn(signal, client), 'Auto On')}>
          Auto On
        </button>
        <button
          className="button secondary"
          disabled={disabled}
          onClick={() => run((signal) => postAutoOff(signal, client), 'Auto Off')}
        >
          Auto Off
        </button>
        <button className="button" disabled={disabled} onClick={() => run((signal) => postStartAll(signal, client), 'Start All')}>
          Start All
        </button>
        <button
          className="button secondary"
          disabled={disabled}
          onClick={() => run((signal) => postStopAll(signal, client), 'Stop All')}
        >
          Stop All
        </button>
      </div>
      {message && <div className="small">{message}</div>}
      {error && <div className="alert">{error}</div>}
      {!client.adminToken && (
        <div className="alert">
          Admin token required for mutations. Provide X-Admin-Token / X-OPS-TOKEN in Login to actually invoke controls.
        </div>
      )}
      {disabledReason && <div className="alert warn">{disabledReason}</div>}
    </div>
  );
};
