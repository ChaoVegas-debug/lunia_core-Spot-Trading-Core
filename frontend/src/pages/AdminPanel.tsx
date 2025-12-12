import React from 'react';
import { PanelPage } from './PanelPage';
import { SystemStateWidget } from '../components/widgets/SystemStateWidget';
import { PortfolioWidget } from '../components/widgets/PortfolioWidget';
import { SignalsWidget } from '../components/widgets/SignalsWidget';
import { RiskWidget } from '../components/widgets/RiskWidget';
import { ControlsWidget } from '../components/widgets/ControlsWidget';
import { LogsWidget } from '../components/widgets/LogsWidget';
import { CapitalWidget } from '../components/widgets/CapitalWidget';
import { SystemActivityWidget } from '../components/widgets/SystemActivityWidget';
import { AdminUsersWidget } from '../components/widgets/AdminUsersWidget';
import { FeatureFlagsWidget } from '../components/widgets/FeatureFlagsWidget';
import { LimitsWidget } from '../components/widgets/LimitsWidget';
import { AuditWidget } from '../components/widgets/AuditWidget';

export const AdminPanel: React.FC = () => {
  return (
    <PanelPage
      title="Admin Panel"
      subtitle="Full control surface; admin tokens required for mutations."
      sections={[
        { key: 'overview', title: 'Dashboard', content: <SystemStateWidget /> },
        { key: 'activity', title: 'System Activity', content: <SystemActivityWidget /> },
        { key: 'capital', title: 'Capital', content: <CapitalWidget /> },
        { key: 'portfolio', title: 'Portfolio', content: <PortfolioWidget /> },
        { key: 'signals', title: 'Signals', content: <SignalsWidget /> },
        { key: 'risk', title: 'Risk', content: <RiskWidget /> },
        { key: 'controls', title: 'Controls', content: <ControlsWidget /> },
        { key: 'logs', title: 'Logs', content: <LogsWidget /> },
        { key: 'users', title: 'Users', content: <AdminUsersWidget /> },
        { key: 'flags', title: 'Feature Flags', content: <FeatureFlagsWidget /> },
        { key: 'limits', title: 'Limits', content: <LimitsWidget /> },
        { key: 'audit', title: 'Audit', content: <AuditWidget /> }
      ]}
    />
  );
};
