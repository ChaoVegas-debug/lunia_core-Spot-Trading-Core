
/**
 * Safe Array Guard
 * Guarantees a return of T[] or [], never undefined or null.
 * Use this in UI components before .length, .map, or .filter to prevents crashes.
 */
export const safeArray = <T>(v: T[] | null | undefined): T[] => {
    if (v === null || v === undefined) return [];
    return Array.isArray(v) ? v : [];
};
