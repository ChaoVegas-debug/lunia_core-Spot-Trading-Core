
import React, { useState, useEffect } from 'react';
import { useDashboard } from '../../context/DashboardContext';

const LANGUAGES = [
    { code: 'EN', label: 'English' },
    { code: 'PL', label: 'Polski' },
    { code: 'RU', label: 'Русский' }
];

export const SettingsWidget: React.FC = () => {
    const { addToast } = useDashboard();
    const [lang, setLang] = useState(localStorage.getItem('LUNIA_LANG') || 'EN');

    const handleLang = (code: string) => {
        setLang(code);
        localStorage.setItem('LUNIA_LANG', code);
        // In a real app, this would trigger global context update.
        // For visual proof, we show state change.
        if (code !== 'EN') addToast({ type: 'INFO', message: `UI Language Switched to ${code} (Preview Placeholder)` });
    };

    return (
        <div className="card">
            <h3>Platform Settings</h3>
            <div className="grid cols-2" style={{ marginTop: '1rem' }}>
                <div>
                    <h4>Interface Language / Język / Язык</h4>
                    <div className="button-group" style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                        {LANGUAGES.map(l => (
                            <button
                                key={l.code}
                                className={`button ${lang === l.code ? 'primary' : 'secondary'}`}
                                onClick={() => handleLang(l.code)}
                            >
                                {l.label}
                            </button>
                        ))}
                    </div>
                </div>
                <div>
                    <h4>Theme & Density</h4>
                    <div className="button-group" style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                        <button className="button active" disabled>Dark Pro</button>
                        <button className="button secondary" disabled>Light (Coming Soon)</button>
                    </div>
                </div>
            </div>
        </div>
    );
};
