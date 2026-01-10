import React, { createContext, useContext, useState, ReactNode } from 'react';
import { WhyPanel } from '../components/modals/WhyPanel';

interface WhyParams {
    ruleId?: string;
    context?: string;
}

interface WhyContextType {
    openWhy: (params: WhyParams) => void;
    closeWhy: () => void;
}

const WhyContext = createContext<WhyContextType | undefined>(undefined);

export const WhyProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [isOpen, setIsOpen] = useState(false);
    const [params, setParams] = useState<WhyParams>({});

    const openWhy = (p: WhyParams) => {
        setParams(p);
        setIsOpen(true);
    };

    const closeWhy = () => {
        setIsOpen(false);
    };

    return (
        <WhyContext.Provider value={{ openWhy, closeWhy }}>
            {children}
            <WhyPanel
                isOpen={isOpen}
                onClose={closeWhy}
                ruleId={params.ruleId}
                context={params.context}
            />
        </WhyContext.Provider>
    );
};

export const useWhy = () => {
    const context = useContext(WhyContext);
    if (!context) {
        throw new Error('useWhy must be used within a WhyProvider');
    }
    return context;
};
