import React from 'react';

interface Props {
  loading: boolean;
  error?: Error;
  lastUpdated?: number;
  staleAfterMs?: number;
  label?: string;
}

export const DataStatus: React.FC<Props> = ({ loading, error, lastUpdated, staleAfterMs = 15000, label }) => {
  const now = Date.now();
  const stale = lastUpdated ? now - lastUpdated > staleAfterMs : false;

  let text = loading ? 'Loading…' : 'Live';
  let className = 'status-chip ok';
  if (error) {
    text = 'Error';
    className = 'status-chip error';
  } else if (stale) {
    text = 'Stale';
    className = 'status-chip warn';
  }

  return (
    <div className="data-status">
      <span className={className}>{text}</span>
      {label && <span className="small" style={{ marginLeft: 8 }}>{label}</span>}
      {lastUpdated && (
        <span className="small" style={{ marginLeft: 8 }}>
          Updated {new Date(lastUpdated).toLocaleTimeString()}
        </span>
      )}
      {error && <span className="small" style={{ marginLeft: 8, color: '#fbbf24' }}>{error.message}</span>}
    </div>
  );
};
