import React from 'react';
import { usePoller } from '../../hooks/usePoller';
import { getRiskRules } from '../../api/adapter';
import { useWhy } from '../../contexts/WhyContext';

export const RiskRulesTable: React.FC = () => {
    const { data: rulesData, error: rulesError, refresh: rulesRefresh } = usePoller({
        key: 'risk_rules',
        endpoint: '/api/risk/rules',
        fetcher: () => getRiskRules(),
        interval_ms: 5000,
        critical: false
    });
    const rules = { data: rulesData, error: rulesError, loading: false, refresh: rulesRefresh };
    const { openWhy } = useWhy();


    return (
        <div className="card">
            <div className="card-header">
                <h3>Policy Rules</h3>
                <p className="small muted">Active Trading Constraints</p>
            </div>
            {rules.error ? (
                <div className="p-4 alert danger">{String(rules.error)}</div>
            ) : (
                <table className="table w-full text-sm">
                    <thead>
                        <tr className="text-left text-muted border-b border-subtle">
                            <th className="pb-2 pl-4">Rule Name</th>
                            <th className="pb-2">Status</th>
                            <th className="pb-2">Severity</th>
                            <th className="pb-2">Description</th>
                            <th className="pb-2 text-right pr-4">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rules.data?.map((rule: any) => (
                            <tr key={rule.id} className="border-b border-subtle/10 hover:bg-deep/50">
                                <td className="py-3 pl-4 font-bold">{rule.name}</td>
                                <td className="py-3">
                                    <span className={`badge tiny ${rule.status === 'ACTIVE' ? 'success' : 'warning'}`}>
                                        {rule.status}
                                    </span>
                                </td>
                                <td className="py-3">
                                    <span className={`tiny font-mono ${rule.severity === 'CRITICAL' ? 'text-danger' : 'text-warning'}`}>
                                        {rule.severity}
                                    </span>
                                </td>
                                <td className="py-3 text-muted">{rule.description}</td>
                                <td className="py-3 pr-4 text-right">
                                    <button className="button small text" onClick={() => openWhy({
                                        ruleId: rule.id,
                                        context: `Rule ${rule.id} ("${rule.name}") is currently active. ${rule.description}`
                                    })}>WHY?</button>
                                </td>

                            </tr>
                        ))}
                    </tbody>
                </table>
            )}
        </div>
    );
};
