import React from 'react';
import { usePoller } from '../../hooks/usePoller';
import { getRiskMandates } from '../../api/adapter';

export const RiskMandatesTable: React.FC = () => {
    const { data: mandatesData, error: mandatesError, refresh: mandatesRefresh } = usePoller({
        key: 'risk_mandates',
        endpoint: '/api/risk/mandates',
        fetcher: () => getRiskMandates(),
        interval_ms: 5000,
        critical: false
    });
    const mandates = { data: mandatesData, error: mandatesError, loading: false, refresh: mandatesRefresh };

    return (
        <div className="card">
            <div className="card-header bg-dark-2">
                <h3 className="text-warn">Global Mandates</h3>
                <p className="small muted">Hard/Immutable Limits</p>
            </div>
            <div className="p-0">
                {mandates.data?.map((m: any, idx: number) => (
                    <div key={idx} className="flex-between p-3 border-b border-subtle last:border-0 hover:bg-deep/50">
                        <div>
                            <div className="font-bold text-sm">{m.label}</div>
                            <div className="tiny muted">Limit: {m.limit}</div>
                        </div>
                        <div className="text-right">
                            <div className={`font-mono font-bold ${m.status === 'OK' ? 'text-success' : 'text-danger'}`}>
                                {m.current}
                            </div>
                            <div className="tiny badge subtle">{m.status}</div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};
