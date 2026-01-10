import React, { useState } from 'react';
import { usePreview } from '../../hooks/usePreview';

export const ForensicsReplayWidget: React.FC = () => {
    const { isPreview, previewStore } = usePreview();
    const [selectedIncidentId, setSelectedIncidentId] = useState<string>('');
    const [replayTime, setReplayTime] = useState<number>(0);

    // In a real system, this would fetch snapshots around the incident time.
    // In Preview/Sim, we will mock a state progression.

    const incidents = isPreview
        ? previewStore.getState().incidents
        : []; // In production this would come from a backend snapshot service

    const handleIncidentSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
        setSelectedIncidentId(e.target.value);
        setReplayTime(0);
    };

    const selectedIncident = incidents.find(i => i.id === selectedIncidentId);

    return (
        <div className="card forensics-widget" style={{ borderLeft: '4px solid var(--accent-primary)' }}>
            <div className="card-header">
                <h3>Forensics Replay Engine</h3>
                {isPreview && <span className="badge warning">SIMULATION</span>}
            </div>

            <p className="small muted mb-4">
                Select a critical incident to replay state transitions frame-by-frame.
            </p>

            <div className="form-group mb-4">
                <label className="small simple-header">Target Incident</label>
                <select
                    className="input full-width"
                    value={selectedIncidentId}
                    onChange={handleIncidentSelect}
                    disabled={!isPreview}
                >
                    <option value="">-- Select Incident --</option>
                    {incidents.map(i => (
                        <option key={i.id} value={i.id}>
                            [{new Date(i.ts).toLocaleTimeString()}] {i.severity} - {i.summary}
                        </option>
                    ))}
                </select>
                {!isPreview && (
                    <div className="tiny text-warn mt-1">Forensics Replay not available via API in this version. Use local logs.</div>
                )}
            </div>

            {selectedIncident && (
                <div className="replay-controls animate-fade-in">
                    <div className="flex-between mb-2">
                        <span className="tiny font-mono muted">T-Minus 5s</span>
                        <span className="tiny font-mono font-bold text-primary">IMPACT: 0s</span>
                        <span className="tiny font-mono muted">T-Plus 5s</span>
                    </div>

                    <input
                        type="range"
                        min="-50"
                        max="50"
                        value={replayTime}
                        onChange={(e) => setReplayTime(parseInt(e.target.value))}
                        className="full-width mb-4"
                    />

                    <div className="grid cols-2 gap-4 p-4 rounded" style={{ background: 'var(--bg-panel-soft)' }}>
                        <div>
                            <div className="tiny uppercase muted mb-1">System State</div>
                            <div className="font-mono small">
                                {replayTime < 0 ? 'NOMINAL' : 'DEGRADED'}
                            </div>
                        </div>
                        <div>
                            <div className="tiny uppercase muted mb-1">Latency</div>
                            <div className="font-mono small">
                                {replayTime < 0 ? '24ms' : `${24 + (replayTime * 10)}ms`}
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};
