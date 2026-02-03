import React, { useEffect } from 'react';
import { useWidgetRegistration, WidgetStatus } from '../../context/WidgetRegistryContext';
import { WidgetBlocker } from './WidgetBlocker';

interface WidgetWrapperProps {
    id: string; // The Widget Name (e.g. "RiskWidget")
    title?: string;
    loading?: boolean;
    error?: Error | null;
    children: React.ReactNode;
    minHeight?: string;
    rightElem?: React.ReactNode; // Optional header element
}

export const WidgetWrapper: React.FC<WidgetWrapperProps> = ({
    id,
    title,
    loading,
    error,
    children,
    minHeight = '300px',
    rightElem
}) => {
    const { reportStatus } = useWidgetRegistration(id);

    useEffect(() => {
        if (loading) reportStatus('LOADING');
        else if (error) reportStatus('BLOCKED', error.message);
        else reportStatus('OK');
    }, [loading, error, reportStatus]);

    if (error) {
        return (
            <div className="card" style={{ height: '100%', minHeight, display: 'flex', flexDirection: 'column' }}>
                <div className="card-header flex-between">
                    <h3>{title || id}</h3>
                    {rightElem}
                </div>
                <WidgetBlocker
                    reason="Data Unavailable"
                    detail={error.message}
                    action="Check System Status"
                />
            </div>
        );
    }

    return (
        <div className="widget-container" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            {children}
        </div>
    );
};
