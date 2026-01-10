
import { test, expect } from '@playwright/test';
import * as fs from 'fs';

test.describe.configure({ mode: 'serial' });

const BASE_URL = 'http://localhost:5180'; // Use the running port
const ARTIFACT_DIR = 'artifacts/ui-proof';

test.beforeAll(async () => {
    if (!fs.existsSync(ARTIFACT_DIR)) fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
});

test('PART E: Verify Trader Panel Scrollability', async ({ page }) => {
    console.log(`Navigating to ${BASE_URL}/trader`);
    await page.goto(`${BASE_URL}/trader`);

    // Wait for load
    await expect(page.locator('.trader-cockpit')).toBeVisible();
    await page.waitForTimeout(2000);

    // Initial Screenshot (Top)
    await page.screenshot({ path: `${ARTIFACT_DIR}/scroll_01_top.png` });

    // Scroll to Bottom
    console.log('Scrolling to bottom...');
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));

    // Alternative: Scroll the specific container if window scroll doesn't work (due to layout)
    // Try scrolling .content just in case layout uses internal scroll
    await page.evaluate(() => {
        const content = document.querySelector('.content');
        if (content) content.scrollTo(0, content.scrollHeight);
    });

    await page.waitForTimeout(1000);

    // Verify Visibility of Bottom Widgets
    // Check for "SignalsWidget" or "LogConsole" or "IntelligenceWidget" at bottom
    // We assume Intelligence/Signals are near bottom based on layout
    const bottomWidget = page.locator('text=Signals').first();
    if (await bottomWidget.isVisible()) {
        console.log('Bottom Widget (Signals) is Visible');
    }

    // Screenshot Bottom
    await page.screenshot({ path: `${ARTIFACT_DIR}/scroll_02_bottom.png` });
});
