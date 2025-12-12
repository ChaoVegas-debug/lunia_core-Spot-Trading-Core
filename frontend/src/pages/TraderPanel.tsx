import React from 'react';
import { PanelPage } from './PanelPage';
import { SystemStateWidget } from '../components/widgets/SystemStateWidget';
import { PortfolioWidget } from '../components/widgets/PortfolioWidget';
import { SignalsWidget } from '../components/widgets/SignalsWidget';
import { RiskWidget } from '../components/widgets/RiskWidget';
import { ControlsWidget } from '../components/widgets/ControlsWidget';
import { LogsWidget } from '../components/widgets/LogsWidget';
import { SystemActivityWidget } from '../components/widgets/SystemActivityWidget';

export const TraderPanel: React.FC = () => {
  return (
    <PanelPage
      title="Trader Panel"
      subtitle="Trader/Operator view with control toggles and trading visibility."
      sections={[
        { key: 'overview', title: 'Dashboard', content: <SystemStateWidget /> },
        { key: 'portfolio', title: 'Portfolio', content: <PortfolioWidget /> },
        { key: 'signals', title: 'Signals', content: <SignalsWidget /> },
        { key: 'activity', title: 'System Activity', content: <SystemActivityWidget /> },
        { key: 'risk', title: 'Risk', content: <RiskWidget /> },
        { key: 'controls', title: 'Controls', content: <ControlsWidget /> },
        { key: 'logs', title: 'Logs', content: <LogsWidget /> }
      ]}
    />
  );
};
