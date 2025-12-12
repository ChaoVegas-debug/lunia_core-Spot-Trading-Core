import React, { useState } from 'react';
import { DataStatus } from '../components/common/DataStatus';

interface Section {
  key: string;
  title: string;
  content: React.ReactNode;
  status?: { loading: boolean; error?: Error; lastUpdated?: number };
}

interface Props {
  title: string;
  sections: Section[];
  subtitle?: string;
}

export const PanelPage: React.FC<Props> = ({ title, sections, subtitle }) => {
  const [active, setActive] = useState<string>(sections[0]?.key ?? 'overview');
  const activeSection = sections.find((s) => s.key === active) ?? sections[0];

  return (
    <div className="panel-grid">
      <aside className="panel-nav">
        <h2>{title}</h2>
        {subtitle && <div className="small muted">{subtitle}</div>}
        <nav>
          {sections.map((section) => (
            <button
              key={section.key}
              className={`nav-link ${section.key === active ? 'active' : ''}`}
              onClick={() => setActive(section.key)}
            >
              <span>{section.title}</span>
              {section.status && (
                <DataStatus
                  loading={section.status.loading}
                  error={section.status.error}
                  lastUpdated={section.status.lastUpdated}
                  staleAfterMs={15000}
                />
              )}
            </button>
          ))}
        </nav>
      </aside>
      <main className="panel-content">
        {activeSection?.content}
      </main>
    </div>
  );
};
