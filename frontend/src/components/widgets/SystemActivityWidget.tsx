import React from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getActivity } from '../../api/endpoints';
import { DataStatus } from '../common/DataStatus';

export const SystemActivityWidget: React.FC = () => {
  const auth = useAuth();
  const client = {
    role: auth.role,
    adminToken: auth.adminToken,
    opsToken: auth.opsToken,
    bearerToken: auth.bearerToken,
    tenantId: auth.tenantId
  };

  const activity = usePolledResource((signal) => getActivity(signal, client), 5000, [auth.role, auth.tenantId]);

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3>System Activity</h3>
          <p className="small">Scheduler, arbitrage, spot, and futures agents with last actions.</p>
        </div>
        <DataStatus loading={activity.loading} error={activity.error} lastUpdated={activity.lastUpdated} staleAfterMs={10000} />
      </div>
      <div className="grid cols-2">
        {activity.data &&
          Object.entries(activity.data.components).map(([name, comp]) => (
            <div key={name} className="card subtle">
              <div className="flex-row" style={{ justifyContent: 'space-between' }}>
                <strong className="text-cap">{name}</strong>
                <span className={`status-chip ${comp.status === 'on' ? 'ok' : 'error'}`}>{comp.status}</span>
              </div>
              <div className="small">Last tick: {comp.last_tick ? new Date(comp.last_tick * 1000).toLocaleTimeString() : 'n/a'}</div>
              {comp.notes && <div className="small muted">{comp.notes}</div>}
            </div>
          ))}
      </div>
      <div className="card" style={{ marginTop: 12 }}>
        <h4>Recent actions</h4>
        {!activity.data && <div className="small">No actions yet.</div>}
        {activity.data && activity.data.last_actions.length === 0 && <div className="small">No recorded actions.</div>}
        {activity.data && activity.data.last_actions.length > 0 && (
          <ul className="list">
            {activity.data.last_actions.slice(0, 10).map((item) => (
              <li key={`${item.ts}-${item.action}`} className="list-row">
                <div>
                  <div className="small">{new Date(item.ts).toLocaleTimeString()} • {item.actor}</div>
                  <div>{item.action}</div>
                  {item.details && <div className="small muted">{item.details}</div>}
                </div>
                <span className={`status-chip ${item.ok ? 'ok' : 'error'}`}>{item.ok ? 'OK' : 'FAIL'}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};
