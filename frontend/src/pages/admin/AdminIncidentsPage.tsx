import React, { useState, useEffect } from 'react';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getSystemEvents } from '../../api/adapter';
import { useAuth } from '../../hooks/useAuth';
import { usePreview } from '../../hooks/usePreview'; // New hook import
import { useDashboard } from '../../context/DashboardContext';
import type { SystemEvent } from '../../api/types';

export const AdminIncidentsPage: React.FC = () => {
    const auth = useAuth();
    const { addToast } = useDashboard();
    const client = { role: auth.role, adminToken: auth.adminToken };
    const { isPreview, previewStore } = usePreview();
    const { data: events, loading, refresh } = usePolledResource<{ items: SystemEvent[] }>((s) => getSystemEvents(s, client), 5000, [auth.role]);

    // Use PreviewStore incidents if Sim
    const displayIncidents = isPreview
        ? previewStore.getState().incidents
        : (events?.items.filter(e =>
            e.type.includes('DRIFT') ||
            e.type.includes('VETO') ||
            e.type.includes('STOP') ||
            e.type.includes('ERROR')
        ) || []);

    const handleResolve = (id: string) => {
        if (isPreview) {
            previewStore.resolveIncident(id);
        } else {
            addToast({ type: 'WARNING', message: 'Incident Resolution not yet wired to Backend API.' });
        }
    };

    if (loading && !events && !isPreview) return <div className="card">Loading Incidents...</div>;

    return (
        <div className="admin-page">
            <h3 style={{ marginBottom: '1rem' }}>System Incidents Timeline</h3>

            <div className="card">
                <table className="table">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Status</th>
                            <th>Severity / Type</th>
                            <th>Summary / Payload</th>
                            {isPreview && <th>Action</th>}
                        </tr>
                    </thead>
                    <tbody>
                        {displayIncidents.map(inc => {
                            // Normalize SIM vs LIVE differences
                            const isSim = 'summary' in inc;
                            const ts = isSim ? inc.ts : (inc as SystemEvent).timestamp;
                            const type = isSim ? (inc as any).severity : (inc as SystemEvent).type;
                            const payload = isSim ? (inc as any).summary : JSON.stringify((inc as SystemEvent).payload).slice(0, 100);
                            const status = isSim ? (inc as any).status : 'OPEN';
                            const id = isSim ? (inc as any).id : (inc as SystemEvent).id;

                            return (
                                <tr key={id} style={{ opacity: status === 'RESOLVED' ? 0.5 : 1 }}>
                                    <td className="font-mono small">{new Date(ts).toLocaleString()}</td>
                                    <td>
                                        <span className={`badge tiny ${status === 'RESOLVED' ? 'success' : 'secondary'}`}>{status}</span>
                                    </td>
                                    <td>
                                        <span className={`badge tiny ${type === 'CRITICAL' || type === 'HIGH' ? 'danger' : 'warning'}`}>{type}</span>
                                    </td>
                                    <td>
                                        <code className="small muted">
                                            {payload}
                                        </code>
                                    </td>
                                    {isPreview && (
                                        <td>
                                            {status !== 'RESOLVED' && (
                                                <button className="button tiny outline" onClick={() => handleResolve(id)}>Match / Resolve</button>
                                            )}
                                        </td>
                                    )}
                                </tr>
                            );
                        })}
                        {displayIncidents.length === 0 && (
                            <tr>
                                <td colSpan={3} className="muted text-center" style={{ padding: '24px' }}>
                                    No critical incidents recorded in the last 24h.
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
};
