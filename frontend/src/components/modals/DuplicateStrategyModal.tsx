import React, { useState, useEffect } from 'react';
import { usePreview } from '../../hooks/usePreview';
import { journalStore } from '../../store/JournalStore';
import { StrategyConfig } from '../../api/types';

interface DuplicateStrategyModalProps {
    strategy: StrategyConfig;
    isOpen: boolean;
    onClose: () => void;
    onSave: (newStrategy: Partial<StrategyConfig>) => Promise<void>;
}

export const DuplicateStrategyModal: React.FC<DuplicateStrategyModalProps> = ({ strategy, isOpen, onClose, onSave }) => {
    const { isPreview } = usePreview();
    const [name, setName] = useState('');
    const [weight, setWeight] = useState(0);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (isOpen && strategy) {
            setName(`${strategy.name} (Copy)`);
            setWeight(0); // Default to 0 weight for safety
        }
    }, [isOpen, strategy]);

    if (!isOpen) return null;

    const handleSubmit = async () => {
        setLoading(true);
        try {
            await onSave({
                ...strategy,
                name,
                weight,
                enabled: false, // Always disabled by default
                id: undefined // New ID will be generated
            });
            journalStore.addLog('INFO', `Strategy Duplicated: ${name}`, isPreview ? 'SYSTEM' : 'HUMAN');
            onClose();
        } catch (e) {
            alert("Failed to duplicate strategy: " + e);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 2000,
            background: 'rgba(0,0,0,0.7)',
            backdropFilter: 'blur(4px)'
        }}>
            <div className="card" style={{ width: '500px', maxWidth: '90vw' }}>
                <div className="card-header">
                    <h3>Duplicate Strategy Configuration</h3>
                </div>

                <div className="card-body">
                    <div className="alert info mb-4" style={{ marginBottom: '1.5rem' }}>
                        You are about to clone <strong>{strategy.core}</strong> logic. The new strategy will be created in PAUSED state.
                    </div>

                    <div style={{ marginBottom: '1rem' }}>
                        <label className="small muted uppercase">New Strategy Name</label>
                        <input
                            type="text"
                            className="input full-width"
                            value={name}
                            onChange={e => setName(e.target.value)}
                            style={{ width: '100%', padding: '0.5rem', marginTop: '0.25rem' }}
                        />
                    </div>

                    <div style={{ marginBottom: '1rem' }}>
                        <label className="small muted uppercase">Initial Allocation Weight (0 - 1.0)</label>
                        <input
                            type="number"
                            className="input full-width"
                            value={weight}
                            onChange={e => setWeight(Math.max(0, parseFloat(e.target.value) || 0))}
                            step="0.01"
                            max="1.0"
                            style={{ width: '100%', padding: '0.5rem', marginTop: '0.25rem' }}
                        />
                    </div>

                    {isPreview && (
                        <div className="alert warning small">
                            <strong>PREVIEW MODE:</strong> This will purely update the simulation state. No API call will be made.
                        </div>
                    )}
                </div>

                <div className="flex-row gap-2" style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '2rem' }}>
                    <button className="button ghost" onClick={onClose} disabled={loading}>Cancel</button>
                    <button className="button primary" onClick={handleSubmit} disabled={loading}>
                        {loading ? 'Cloning...' : 'Create Copy'}
                    </button>
                </div>
            </div>
        </div>
    );
};
