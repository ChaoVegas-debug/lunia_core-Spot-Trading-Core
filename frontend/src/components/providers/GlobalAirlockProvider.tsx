import React, { useState, useEffect } from 'react';
import { AirlockModalV3 } from '../modals/AirlockModalV3';
import { AirlockContext, subscribeToAirlock, closeAirlock } from '../../lib/airlock/airlockHelper';

/**
 * GLOBAL AIRLOCK PROVIDER
 * 
 * Single instance that listens for openAirlock() calls
 * and renders the AirlockModalV3 accordingly.
 * 
 * Mount this at app root level.
 */
export const GlobalAirlockProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [context, setContext] = useState<AirlockContext | null>(null);

    useEffect(() => {
        const unsubscribe = subscribeToAirlock((newContext) => {
            setContext(newContext);
        });
        return unsubscribe;
    }, []);

    const handleClose = () => {
        closeAirlock();
    };

    return (
        <>
            {children}
            <AirlockModalV3
                isOpen={!!context}
                context={context || undefined}
                onClose={handleClose}
            />
        </>
    );
};
