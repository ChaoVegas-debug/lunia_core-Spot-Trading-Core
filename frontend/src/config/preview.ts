export const PREVIEW_MODE = import.meta.env.VITE_PREVIEW_MODE === '1';
export const PREVIEW_SIMULATION = import.meta.env.VITE_PREVIEW_SIMULATION !== '0'; // default true if preview mode is on, unless explicitly 0

export const PREVIEW_BADGE_TEXT = 'PREVIEW MODE';

export function isPreviewEnabled(): boolean {
    return PREVIEW_MODE;
}

export function isSimulationEnabled(): boolean {
    return PREVIEW_MODE && PREVIEW_SIMULATION;
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
