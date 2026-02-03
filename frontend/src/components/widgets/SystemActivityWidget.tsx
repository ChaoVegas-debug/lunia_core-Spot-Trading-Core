import React from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePoller } from '../../hooks/usePoller';
import { getActivity, getSystemEvents } from '../../api/adapter';
import { safeArray } from '../../utils/safe';
import type { SystemEvent, ActivityComponent } from '../../api/types';
import { DataStatus } from '../common/DataStatus';

export const SystemActivityWidget: React.FC = () => {
  const auth = useAuth();
  const client = { role: auth.role, adminToken: auth.adminToken, opsToken: auth.opsToken, bearerToken: auth.bearerToken };

  const { data: activityData, error: activityError, refresh: activityRefresh } = usePoller({
        key: 'activity_SystemActivityWidget',
        endpoint: '/api/activity',
        fetcher: () => getActivity(new AbortController().signal, client),
        interval_ms: 5000,
        critical: false
    });
    const activity = { data: activityData, error: activityError, loading: false, refresh: activityRefresh };
  const { data: eventsData, error: eventsError, refresh: eventsRefresh } = usePoller({
        key: 'events_SystemActivityWidget',
        endpoint: '/api/events/system',
        fetcher: () => getSystemEvents(new AbortController().signal, client),
        interval_ms: 2000,
        critical: false
    });
    const events = { data: eventsData, error: eventsError, loading: false, refresh: eventsRefresh };

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3>System Audit</h3>
          <p className="small">Live Event Feed & Safety Log</p>
        </div>
        <DataStatus loading={events.loading} error={events.error} lastUpdated={events.lastUpdated} staleAfterMs={5000} />
      </div>

      <div className="grid cols-2" style={{ marginBottom: '12px' }}>
        {activity.data && Object.entries(activity.data.components).map(([name, compData]) => {
          const comp = compData as ActivityComponent;
          return (
            <div key={name} className="card subtle">
              <div className="flex-row" style={{ justifyContent: 'space-between' }}>
                <strong className="text-cap">{name}</strong>
                <span className={`status-chip ${comp.status === 'on' ? 'ok' : 'error'}`}>{comp.status}</span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="card" style={{ maxHeight: '400px', overflowY: 'auto' }}>
        <h4>Event Feed</h4>
        {safeArray(events.data?.items).length === 0 && <div className="small">No events recorded.</div>}

        {safeArray(events.data?.items).length > 0 && (
          <ul className="list">
            {safeArray(events.data?.items).slice().reverse().map((evt: SystemEvent) => (
              <li key={evt.id} className="list-row">
                <div>
                  <div className="tiny muted">{new Date(evt.timestamp).toLocaleTimeString()}</div>
                  <div className="small font-bold">{evt.type}</div>
                  <div className="tiny code">{JSON.stringify(evt.payload)}</div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};
