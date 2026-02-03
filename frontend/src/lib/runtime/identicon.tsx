/**
 * IDENTICON GENERATOR
 * 
 * Phase F3.2: Deterministic SVG identicon from string hash
 * 
 * Generates a simple geometric identicon for actor/user identification.
 * Seeded from string hash for consistency (same string = same identicon).
 * 
 * Features:
 * - Deterministic (same input → same output)
 * - Lightweight (inline SVG, no heavy dependencies)
 * - 5x5 grid with symmetry
 * - Color derived from hash
 * 
 * Usage:
 * ```tsx
 * const svg = generateIdenticon('actor@example.com', 24);
 * <div dangerouslySetInnerHTML={{ __html: svg }} />
 * ```
 */

/**
 * Simple string hash function (Java-style hashCode)
 */
function hashCode(str: string): number {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        const char = str.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash; // Convert to 32-bit integer
    }
    return Math.abs(hash);
}

/**
 * Generate deterministic identicon SVG
 * 
 * @param seed - String to generate identicon from (e.g., actor email/role)
 * @param size - Size in pixels (default: 24)
 * @returns SVG string (inject via dangerouslySetInnerHTML)
 */
export function generateIdenticon(seed: string, size: number = 24): string {
    const hash = hashCode(seed || 'unknown');

    // Generate color from hash (pastel for visibility)
    const hue = hash % 360;
    const saturation = 50 + (hash % 30);
    const lightness = 40 + (hash % 20);
    const color = `hsl(${hue}, ${saturation}%, ${lightness}%)`;

    // Generate 5x5 grid pattern (symmetric)
    const gridSize = 5;
    const cells: boolean[] = [];

    // Generate half + center column (3 columns)
    for (let row = 0; row < gridSize; row++) {
        for (let col = 0; col < Math.ceil(gridSize / 2); col++) {
            const bitIndex = row * Math.ceil(gridSize / 2) + col;
            const bit = (hash >> bitIndex) & 1;
            cells.push(bit === 1);
        }
    }

    // Mirror to create symmetric pattern
    const fullCells: boolean[] = [];
    for (let row = 0; row < gridSize; row++) {
        const rowStart = row * Math.ceil(gridSize / 2);
        const leftHalf = cells.slice(rowStart, rowStart + 2);
        const center = cells[rowStart + 2];
        const rightHalf = [...leftHalf].reverse();

        fullCells.push(...leftHalf, center, ...rightHalf);
    }

    // Generate SVG
    const cellSize = size / gridSize;
    const rects = fullCells
        .map((filled, idx) => {
            if (!filled) return '';
            const row = Math.floor(idx / gridSize);
            const col = idx % gridSize;
            const x = col * cellSize;
            const y = row * cellSize;
            return `<rect x="${x}" y="${y}" width="${cellSize}" height="${cellSize}" fill="${color}" />`;
        })
        .filter(Boolean)
        .join('');

    return `<svg width="${size}" height="${size}" xmlns="http://www.w3.org/2000/svg" style="display:inline-block;vertical-align:middle">${rects}</svg>`;
}

/**
 * React component wrapper for identicon
 */
export function Identicon({ seed, size = 24 }: { seed: string; size?: number }) {
    const svg = generateIdenticon(seed, size);
    return <span dangerouslySetInnerHTML={{ __html: svg }} />;
}
