
import { test, expect } from '@playwright/test';
import * as fs from 'fs';

// Force Serial
test.describe.configure({ mode: 'serial' });

const BASE_URL = 'http://localhost:5179'; // Using the confirmed active port
const ARTIFACT_DIR = 'artifacts/ui-proof';

test.beforeAll(async () => {
    if (!fs.existsSync(ARTIFACT_DIR)) fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
});

test('PART D: Proof of Manual Login to /trader', async ({ page }) => {
    // 0. Go to Login
    console.log(`Open Login: ${BASE_URL}/login`);
    await page.goto(`${BASE_URL}/login`);
    await page.screenshot({ path: `${ARTIFACT_DIR}/login_00_initial.png` });

    // 1. Fill Form
    await page.fill('input[type="email"]', 'admin@lunia.fi');
    await page.fill('input[type="password"]', 'password');
    await page.screenshot({ path: `${ARTIFACT_DIR}/login_01_filled.png` });

    // 2. Click Login
    console.log('Clicking Login...');
    await page.click('button[type="submit"]');

    // 3. Wait for Navigation (Redirect to /trader)
    try {
        await expect(page).toHaveURL(/.*\/trader/, { timeout: 10000 });
        console.log('Redirect SUCCESS: /trader reached');
    } catch (e) {
        console.log(`Redirect FAILED. Current URL: ${page.url()}`);
        await page.screenshot({ path: `${ARTIFACT_DIR}/login_02_fail_state.png` });
        throw e;
    }

    await page.waitForTimeout(2000); // Allow widgets to mount

    // 4. Verify Identity
    await page.screenshot({ path: `${ARTIFACT_DIR}/login_03_trader_landed.png` });

    // 5. Assert Widgets
    // Check for "Preview Mode" text or badge
    const badgeVisible = await page.getByText(/Preview Mode|SIM/i).count() > 0;
    console.log(`Badge Visible: ${badgeVisible}`);

    // Check for Key Widgets (SystemStateWidget, etc via partial text)
    const stopButton = await page.getByText('Global Stop').count() > 0;
    console.log(`Global Stop Button Visible: ${stopButton}`);

    expect(badgeVisible).toBeTruthy();
});
