
import { test, expect } from '@playwright/test';
import * as fs from 'fs';

const BASE_URL = process.env.BASE_URL || 'http://localhost:5180';
const ARTIFACT_DIR = 'artifacts/smoke-test';

test.beforeAll(async () => {
    if (!fs.existsSync(ARTIFACT_DIR)) fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
});

test('Trader Panel Smoke Test (No Crash)', async ({ page }) => {
    console.log(`Running smoke test against ${BASE_URL}`);

    // 1. Inject Auth
    await page.goto(`${BASE_URL}/login`);
    await page.evaluate(() => {
        localStorage.setItem('lunia-auth-state', JSON.stringify({
            role: 'ADMIN',
            bearerToken: 'sim-valid-token-123',
            opsToken: 'sim-ops-token-123',
            user: {
                id: 1,
                email: 'smoke@lunia.test',
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

    // 3. Wait for critical widgets to verify successful render
    // We expect "Active Symbols" and "AI Signals" to be visible
    await expect(page.locator('h3', { hasText: 'Active Symbols' })).toBeVisible({ timeout: 10000 });

    // 4. Check for Error Boundary Text
    const crashText = page.locator('text=Something went wrong');
    await expect(crashText).not.toBeVisible();

    const crashText2 = page.locator('text=Cannot read properties of undefined');
    await expect(crashText2).not.toBeVisible();

    console.log('Trader Panel rendered successfully without crash.');
    await page.screenshot({ path: `${ARTIFACT_DIR}/trader_smoke_pass.png` });
});
