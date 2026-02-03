import React from 'react';
import { usePoller } from '../../hooks/usePoller';
import { getActionFeed } from '../../api/adapter';
import { ActivityItem } from '../../api/types';
import { WidgetWrapper } from '../common/WidgetWrapper';

export const SystemActionsFeedWidget: React.FC = () => {
    const { data, error } = usePoller({
        key: 'action_feed',
        endpoint: '/api/actions/feed',
        fetcher: () => getActionFeed(),
        interval_ms: 1000,
        critical: false
    });
    const loading = false;

    return (
        <WidgetWrapper id="SystemActionsFeedWidget" title="System Feed" loading={loading} error={error}>
            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '4px', maxHeight: '180px' }}>
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
        </WidgetWrapper>
    );
};
