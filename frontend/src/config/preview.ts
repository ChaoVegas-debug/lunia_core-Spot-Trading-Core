// Read from Vite env vars - fall back to false if not set
export const PREVIEW_MODE = import.meta.env.VITE_PREVIEW_MODE === '1' || import.meta.env.VITE_PREVIEW_MODE === 'true';
export const PREVIEW_SIMULATION = import.meta.env.VITE_PREVIEW_SIMULATION === '1' || import.meta.env.VITE_PREVIEW_SIMULATION === 'true';
export const PROOF_MODE = import.meta.env.VITE_PROOF_MODE === '1' || import.meta.env.VITE_PROOF_MODE === 'true';

export const PREVIEW_BADGE_TEXT = PREVIEW_MODE ? 'PREVIEW MODE' : 'LIVE MODE';

// PHASE 6: Localhost detection helper
export function isLocalhostDevelopment(): boolean {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || '';
    return baseUrl.includes('localhost') || baseUrl.includes('127.0.0.1');
}

export function isPreviewEnabled(): boolean {
    // PHASE 6: Disable preview mode for localhost dev (force real backend)
    if (isLocalhostDevelopment()) {
        return false;
    }
    return PREVIEW_MODE;
}

export function isSimulationEnabled(): boolean {
    return PREVIEW_SIMULATION;
}

export function isProofModeEnabled(): boolean {
    return PROOF_MODE;
}

export function previewLabel(text: string): string {
    return isSimulationEnabled() ? `[SIM] ${text}` : text;
}

export function requirePreviewOrThrow(featureName: string): void {
    if (!isPreviewEnabled()) {
        throw new Error(`Feature ${featureName} requires VITE_PREVIEW_MODE=1`);
    }
}

export function previewBannerText(mode: 'LIVE' | 'SIM' | 'PREVIEW_ONLY'): string {
    switch (mode) {
        case 'LIVE': return 'LIVE DATA - Backend Connected';
        case 'SIM': return 'SIMULATION - Backend Unreachable/Disabled';
        case 'PREVIEW_ONLY': return 'PREVIEW MODE - Governance Softened';
    }
}
