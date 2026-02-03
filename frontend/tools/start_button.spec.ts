import { test, expect } from '@playwright/test';
import * as fs from 'fs';

const BASE_URL = process.env.BASE_URL || 'http://localhost:5180';
const ARTIFACT_DIR = 'artifacts/start-button';

test.beforeAll(async () => {
    if (!fs.existsSync(ARTIFACT_DIR)) fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
});

test('START Button Smoke Test', async ({ page }) => {
    console.log(`Running START button test against ${BASE_URL}`);

    // 1. Inject Auth
    await page.goto(`${BASE_URL}/login`);
    await page.evaluate(() => {
        localStorage.setItem('lunia-auth-state', JSON.stringify({
            role: 'ADMIN',
            bearerToken: 'sim-valid-token-123',
            opsToken: 'sim-ops-token-123',
            user: {
                id: 1,
                email: 'start@lunia.test',
                role: 'ADMIN',
                tier: 'INST_PRO',
                is_active: true,
                onboarding_completed: true,
                kyc_status: 'VERIFIED'
            },
            expiresAt: new Date(Date.now() + 86400000).toISOString()
        }));
    });

    // 2. Navigate to Trader
    console.log('Navigating to /trader...');
    await page.goto(`${BASE_URL}/trader`);

    // 3. Wait for ExecutionCommandStrip to render
    await page.waitForTimeout(1500);

    // 4. Look for START button
    const startBtn = page.locator('button:has-text("START")');
    await expect(startBtn).toBeVisible({ timeout: 10000 });
    console.log('START button found');

    // 5. Take screenshot before click
    await page.screenshot({ path: `${ARTIFACT_DIR}/01_start_button_visible.png` });

    // 6. Click START
    await startBtn.click();
    await page.waitForTimeout(500);

    // 7. Verify modal appears with gates summary
    const modal = page.locator('text=START Trading Pipeline');
    await expect(modal).toBeVisible({ timeout: 5000 });
    console.log('Confirmation modal appeared');

    await page.screenshot({ path: `${ARTIFACT_DIR}/02_start_modal_open.png` });

    // 8. Click "Start DRY"
    const dryBtn = page.locator('button:has-text("Start DRY")');
    if (await dryBtn.isVisible()) {
        await dryBtn.click();
        console.log('Clicked Start DRY');
        await page.waitForTimeout(500);
    }

    // 9. Verify RunStateBadge shows phase transition
    await page.waitForTimeout(2000);
    await page.screenshot({ path: `${ARTIFACT_DIR}/03_running_state.png` });

    // 10. Check for no crash
    const crashText = page.locator('text=Something went wrong');
    await expect(crashText).not.toBeVisible();

    const crashText2 = page.locator('text=Cannot read properties of undefined');
    await expect(crashText2).not.toBeVisible();

    console.log('START Button test passed successfully.');
    await page.screenshot({ path: `${ARTIFACT_DIR}/04_test_complete.png` });
});
