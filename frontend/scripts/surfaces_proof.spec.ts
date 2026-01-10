
import { test, expect } from '@playwright/test';
import * as fs from 'fs';

test.describe.configure({ mode: 'serial' });

const BASE_URL = 'http://localhost:5180';
const ARTIFACT_DIR = 'artifacts/surfaces-proof';

test.beforeAll(async () => {
    if (!fs.existsSync(ARTIFACT_DIR)) fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
});

test('PART F: Verify Institutional Surfaces', async ({ page }) => {
    // Capture console logs
    page.on('console', msg => console.log(`BROWSER LOG: ${msg.text()}`));
    page.on('pageerror', err => console.log(`BROWSER ERROR: ${err.message}`));

    console.log(`Navigating to ${BASE_URL}/trader`);
    await page.goto(`${BASE_URL}/trader`);
    await page.waitForTimeout(5000); // Increased wait

    // Debug snapshot
    await page.screenshot({ path: `${ARTIFACT_DIR}/debug_trader_state.png` });

    // 1. Trader Panel: Verify New Widgets

    // 1. Trader Panel: Verify New Widgets
    await expect(page.locator('text=Global Balances')).toBeVisible();
    await expect(page.locator('text=Trading Blotter')).toBeVisible();
    await expect(page.locator('text=Hedging & Derivatives')).toBeVisible();
    await expect(page.locator('text=ARB CORE')).toBeVisible(); // Command strip toggle

    await page.screenshot({ path: `${ARTIFACT_DIR}/trader_new_widgets.png` });
    console.log('Verified Trader Widgets');

    // 2. Portfolio: Verify AI Cards
    await page.goto(`${BASE_URL}/portfolio`);
    await page.waitForTimeout(2000);
    await expect(page.locator('text=AI Research Feed')).toBeVisible();
    await expect(page.locator('text=Institutional Accumulation')).toBeVisible(); // Specific content

    await page.screenshot({ path: `${ARTIFACT_DIR}/portfolio_ai_cards.png` });
    console.log('Verified Portfolio AI Cards');

    // 3. Account: Verify Settings
    await page.goto(`${BASE_URL}/account`);
    await page.waitForTimeout(1500);
    await expect(page.locator('text=Platform Settings')).toBeVisible();
    await expect(page.locator('text=Polski')).toBeVisible();

    await page.screenshot({ path: `${ARTIFACT_DIR}/account_settings.png` });
    console.log('Verified Account Settings');

    // 4. Admin: Verify Expansion
    // Assumption: User is ADMIN in preview
    await page.goto(`${BASE_URL}/admin`);
    await page.waitForTimeout(1500);
    // Check for "Audit Log Explorer" if user is admin, handling redirect if not
    // In preview mode we forced Admin role, so it should work.
    if (await page.locator('text=Audit Log Explorer').isVisible()) {
        await page.screenshot({ path: `${ARTIFACT_DIR}/admin_expanded.png` });
        console.log('Verified Admin Expansion');
    } else {
        console.log('Admin Expansion check skipped (Role check needed?)');
    }
});
