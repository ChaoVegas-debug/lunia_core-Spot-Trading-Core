import React from 'react';
import { useAuth } from '../hooks/useAuth';
import { usePolledResource } from '../hooks/usePolledResource';
import { getFundOverview, getFundPortfolio, getFundStrategies, getFundAccounts } from '../api/adapter';
import { FundOverview, FundPortfolio, FundStrategy, FundAccount } from '../api/types';
import { DataStatus } from '../components/common/DataStatus';

export const FundPanel: React.FC = () => {
  const auth = useAuth();
  const client = { role: auth.role, adminToken: auth.adminToken, opsToken: auth.opsToken, bearerToken: auth.bearerToken };

  // Poll resources
  const { data: overview, loading: loadingOverview, error: errorOverview, lastUpdated } = usePolledResource<FundOverview>((s) => getFundOverview(s, client), 5000, [auth]);
  const { data: portfolio } = usePolledResource<FundPortfolio>((s) => getFundPortfolio(s, client), 10000, [auth]);
  const { data: strategies } = usePolledResource<FundStrategy[]>((s) => getFundStrategies(s, client), 10000, [auth]);

  return (
    <div className="page-container p-6 max-w-[1600px] mx-auto space-y-8">
      {/* Header */}
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-blue-500">
            Institutional Fund Overview
          </h1>
          <div className="flex items-center gap-2 mt-2">
            <span className="px-2 py-0.5 rounded text-xs font-bold bg-blue-900/50 text-blue-200 border border-blue-700">PREVIEW MODE</span>
            <p className="text-sm text-gray-400">Global Aggregation Layer</p>
          </div>
        </div>
        <DataStatus loading={loadingOverview} error={errorOverview} lastUpdated={lastUpdated} />
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-5">
          <div className="text-sm text-gray-400 mb-1">Total AUM</div>
          <div className="text-3xl font-mono text-cyan-400">
            {overview?.total_aum ? `$${(overview.total_aum / 1000000).toFixed(2)}M` : '--'}
          </div>
          <div className="text-xs text-green-400 mt-2 flex items-center gap-1">
            <span>▲ 1.4%</span>
            <span className="text-gray-500">vs yesterday</span>
          </div>
        </div>
        <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-5">
          <div className="text-sm text-gray-400 mb-1">Active Accounts</div>
          <div className="text-3xl font-mono text-white">
            {overview?.active_accounts || '--'}
          </div>
          <div className="text-xs text-gray-500 mt-2">Across 12 Tenants</div>
        </div>
        <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-5">
          <div className="text-sm text-gray-400 mb-1">Capital Utilization</div>
          <div className="text-3xl font-mono text-white">
            {overview?.capital_in_use_pct ? `${(overview.capital_in_use_pct * 100).toFixed(1)}%` : '--'}
          </div>
          <div className="w-full bg-gray-700 h-1.5 mt-3 rounded-full overflow-hidden">
            <div className="bg-blue-500 h-full" style={{ width: `${(overview?.capital_in_use_pct || 0) * 100}%` }}></div>
          </div>
        </div>
        <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-5">
          <div className="text-sm text-gray-400 mb-1">Risk Health</div>
          <div className={`text-3xl font-bold ${overview?.risk_level === 'LOW' ? 'text-green-400' : 'text-red-400'}`}>
            {overview?.risk_level || '--'}
          </div>
          <div className="text-xs text-gray-500 mt-2">Score: {overview?.health_score}/100</div>
        </div>
      </div>

      {/* Allocations & Strategies */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Asset Allocation */}
        <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4 text-gray-200">Asset Allocation</h3>
          <div className="space-y-3">
            {portfolio?.asset_allocation.map((item, i) => (
              <div key={i} className="flex justify-between items-center group">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded bg-gray-700 flex items-center justify-center text-xs font-bold">{item.asset}</div>
                  <span className="text-gray-300 group-hover:text-white transition-colors">{item.asset}</span>
                </div>
                <div className="text-right">
                  <div className="font-mono text-cyan-300">{(item.pct * 100).toFixed(1)}%</div>
                  <div className="w-24 bg-gray-700 h-1 mt-1 rounded-full ml-auto">
                    <div className="bg-cyan-500 h-full rounded-full" style={{ width: `${item.pct * 100}%` }}></div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Venue Allocation */}
        <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4 text-gray-200">Venue Exposure</h3>
          <div className="space-y-4">
            {portfolio?.venue_allocation.map((item, i) => (
              <div key={i}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-400">{item.venue}</span>
                  <span className="font-mono text-gray-200">{(item.pct * 100).toFixed(1)}%</span>
                </div>
                <div className="w-full bg-gray-700 h-2 rounded-full overflow-hidden">
                  <div className="bg-purple-500 h-full rounded-full" style={{ width: `${item.pct * 100}%` }}></div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Top Strategies */}
        <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4 text-gray-200">Top Strategies</h3>
          <div className="overflow-y-auto max-h-[300px] pr-2">
            <table className="w-full text-sm text-left">
              <thead className="text-xs text-gray-500 uppercase border-b border-gray-700">
                <tr>
                  <th className="pb-2">Strategy</th>
                  <th className="pb-2 text-right">AUM</th>
                  <th className="pb-2 text-right">24h</th>
                </tr>
              </thead>
              <tbody>
                {strategies?.map(s => (
                  <tr key={s.id} className="border-b border-gray-800 last:border-0 hover:bg-gray-700/30 transition-colors">
                    <td className="py-3 font-medium text-blue-300">{s.name}</td>
                    <td className="py-3 text-right font-mono text-gray-400">${(s.aum_deployed / 1000000).toFixed(1)}M</td>
                    <td className={`py-3 text-right font-mono ${s.performance_24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {s.performance_24h > 0 ? '+' : ''}{s.performance_24h}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Actions Bar */}
      <div className="flex justify-end gap-3 p-4 bg-gray-800/30 border border-gray-800 rounded-lg">
        <button disabled className="btn btn-secondary opacity-50 cursor-not-allowed">
          Generate NAV Report (Locked)
        </button>
        <button disabled className="btn btn-secondary opacity-50 cursor-not-allowed">
          Request Rebalance (Locked)
        </button>
      </div>
    </div>
  );
};
