import React from 'react';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getActionFeed } from '../../api/adapter';
import { ActivityItem } from '../../api/types';

export const SystemActionsFeedWidget: React.FC = () => {
    const { data } = usePolledResource(getActionFeed, 1000);

    return (
        <div className="card log-console" style={{ height: '200px', display: 'flex', flexDirection: 'column' }}>
            <div style={{ borderBottom: '1px solid #333', paddingBottom: '4px', marginBottom: '4px', color: '#888', fontWeight: 'bold' }}>
                SYSTEM FEED
            </div>
            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {data?.map((item: ActivityItem, i: number) => (
                    <div key={i} className="entry" style={{ fontSize: '0.75rem', fontFamily: 'monospace' }}>
                        <span className="ts" style={{ color: '#444', marginRight: '8px' }}>
                            {new Date(item.ts).toLocaleTimeString()}
                        </span>
                        <span style={{ color: 'var(--accent-primary)', fontWeight: 'bold', marginRight: '8px' }}>
                            [{item.actor}]
                        </span>
                        <span style={{ color: '#ccc' }}>
                            {item.details}
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
};
