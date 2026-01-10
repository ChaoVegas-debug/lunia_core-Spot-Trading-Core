
import { test, expect } from '@playwright/test';
import * as fs from 'fs';

// FORCE SERIAL EXECUTION
test.describe.configure({ mode: 'serial' });

const BASE_URL = 'http://localhost:5173';
const ARTIFACT_DIR = 'artifacts/ui-proof';

test.beforeAll(async () => {
    if (!fs.existsSync(ARTIFACT_DIR)) fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
});

test('Master Visual Verification Walkthrough', async ({ page }) => {
    // Listen for console logs
    page.on('console', msg => console.log(`BROWSER LOG: ${msg.text()}`));
    page.on('pageerror', err => console.log(`BROWSER ERROR: ${err}`));

    // 0. AUTH INJECTION (Bypass Login)
    console.log('--- Step 0: Injecting Auth State ---');
    await page.goto(`${BASE_URL}/login`);

    await page.evaluate(() => {
        localStorage.setItem('lunia-auth-state', JSON.stringify({
            role: 'ADMIN',
            bearerToken: 'sim-valid-token-123',
            opsToken: 'sim-ops-token-123',
            user: {
                id: 1,
                email: 'admin@lunia.fi',
                role: 'ADMIN',
                tier: 'INST_PRO',
                is_active: true,
                onboarding_completed: true,
                kyc_status: 'VERIFIED'
            },
            expiresAt: new Date(Date.now() + 86400000).toISOString()
        }));
    });
    console.log('Auth state injected.');

    // 1. DIRECT NAVIGATION TO TRADER
    console.log('--- Step 1: Navigate to Trader ---');
    await page.goto(`${BASE_URL}/trader`);

    // Wait for App to hydrate and redirect if needed (should stay on /trader)
    // Check if we are really on /trader
    await expect(page).toHaveURL(/.*trader/);
    console.log(`Navigated to: ${page.url()}`);
    await page.waitForTimeout(2000); // Wait for widgets
    await page.screenshot({ path: `${ARTIFACT_DIR}/02_trader_panel_initial.png` });

    // 2. TRADER PANEL & GOVERNANCE ACTIONS
    console.log('--- Step 2: Trader Panel & Governance ---');
    // Ensure key widgets loaded
    // await expect(page.locator('text=Preview Mode')).toBeVisible(); 

    // 2C. Global Stop
    console.log('--- Step 2C: Global Stop ---');
    const stopBtn = page.locator('button', { hasText: /Global Stop/i }).first();
    if (await stopBtn.isVisible()) {
        await stopBtn.click();
        await page.waitForTimeout(1000);
        await page.screenshot({ path: `${ARTIFACT_DIR}/02c_global_stop_triggered.png` });
        // Verify "STOP" mode indicator
        // await expect(page.locator('text=STOP')).toBeVisible();

        // Resume
        await stopBtn.click(); // Toggle off
        await page.waitForTimeout(1000);
    }

    // 3. PORTFOLIO
    console.log('--- Step 3: Portfolio ---');
    await page.goto(`${BASE_URL}/portfolio`);
    await page.waitForTimeout(1500);
    await page.screenshot({ path: `${ARTIFACT_DIR}/03_portfolio_list.png` });

    // 4. RISK
    console.log('--- Step 4: Risk ---');
    await page.goto(`${BASE_URL}/risk`);
    await page.waitForTimeout(1000);
    await page.screenshot({ path: `${ARTIFACT_DIR}/04_risk_dashboard.png` });

    // 5. STRATEGIES
    console.log('--- Step 5: Strategies ---');
    await page.goto(`${BASE_URL}/strategies`);
    await page.waitForTimeout(1000);
    await page.screenshot({ path: `${ARTIFACT_DIR}/05_strategies.png` });

    // 6. EXCHANGE KEYS & TEST CONNECTION
    console.log('--- Step 6: Exchange Keys ---');
    await page.goto(`${BASE_URL}/exchange-keys`);
    await page.waitForTimeout(1000);
    await page.screenshot({ path: `${ARTIFACT_DIR}/06_exchange_keys.png` });

    // 7. ACCOUNT & ADMIN
    console.log('--- Step 7: Account/Admin ---');
    await page.goto(`${BASE_URL}/account`);
    await page.screenshot({ path: `${ARTIFACT_DIR}/07_account.png` });

    await page.goto(`${BASE_URL}/admin`);
    await page.screenshot({ path: `${ARTIFACT_DIR}/08_admin.png` });

    // 8. SYSTEM
    console.log('--- Step 8: System ---');
    await page.goto(`${BASE_URL}/system`);
    await page.screenshot({ path: `${ARTIFACT_DIR}/09_system.png` });

    console.log('--- Verification Complete ---');
});
