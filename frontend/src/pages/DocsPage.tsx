import React from 'react';

export const DocsPage: React.FC = () => {
  return (
    <div>
      <h2>Docs & Contract</h2>
      <p className="small">
        API contract is versioned in <code>docs/API_CONTRACT.md</code>. Use this page to quickly jump to it when building widgets or
        troubleshooting payloads.
      </p>
      <ul>
        <li>
          <a href="/docs/API_CONTRACT.md" target="_blank" rel="noreferrer">
            Open API_CONTRACT.md (served by backend static handler if available)
          </a>
        </li>
        <li className="small">If static serving is disabled, open the contract directly from the repository path: docs/API_CONTRACT.md.</li>
      </ul>
    </div>
  );
};
