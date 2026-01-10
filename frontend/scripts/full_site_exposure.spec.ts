
import { test, expect } from '@playwright/test';
import * as fs from 'fs';

test.describe.configure({ mode: 'serial' });

const BASE_URL = 'http://localhost:5180';
const ARTIFACT_DIR = 'artifacts/visual-exposure';

test.beforeAll(async () => {
    if (!fs.existsSync(ARTIFACT_DIR)) fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
});

test('VISUAL EXPOSURE: Full Project Walkthrough', async ({ page }) => {
    // 1. TRADER PANEL (The Core)
    console.log(` Visiting ${BASE_URL}/trader`);
    await page.goto(`${BASE_URL}/trader`);
    await page.waitForTimeout(5000); // Wait for all polling widgets
    await page.screenshot({ path: `${ARTIFACT_DIR}/01_Trader_Panel_Full.png`, fullPage: true });

    // 2. PORTFOLIO ENGINE
    console.log(` Visiting ${BASE_URL}/portfolio`);
    await page.goto(`${BASE_URL}/portfolio`);
    await page.waitForTimeout(3000);
    await page.screenshot({ path: `${ARTIFACT_DIR}/02_Portfolio_Engine.png`, fullPage: true });

    // 3. STRATEGIES HUB
    console.log(` Visiting ${BASE_URL}/strategies`);
    await page.goto(`${BASE_URL}/strategies`);
    await page.waitForTimeout(3000);
    await page.screenshot({ path: `${ARTIFACT_DIR}/03_Strategy_Hub.png`, fullPage: true });

    // 4. RISK DASHBOARD
    console.log(` Visiting ${BASE_URL}/risk`);
    await page.goto(`${BASE_URL}/risk`);
    await page.waitForTimeout(3000);
    await page.screenshot({ path: `${ARTIFACT_DIR}/04_Risk_Dashboard.png`, fullPage: true });

    // 5. ACCOUNT GOVERNANCE
    console.log(` Visiting ${BASE_URL}/account`);
    await page.goto(`${BASE_URL}/account`);
    await page.waitForTimeout(2000);
    await page.screenshot({ path: `${ARTIFACT_DIR}/05_Account_Governance.png`, fullPage: true });

    // 6. ADMIN CONSOLE
    console.log(` Visiting ${BASE_URL}/admin`);
    await page.goto(`${BASE_URL}/admin`);
    await page.waitForTimeout(2000);
    await page.screenshot({ path: `${ARTIFACT_DIR}/06_Admin_Console.png`, fullPage: true });

    // 7. NEW SURFACES
    console.log(' Verifying New Surfaces...');

    // Strategy Allocation Slider
    await page.goto(`${BASE_URL}/trader`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);
    await page.screenshot({ path: `${ARTIFACT_DIR}/09_Trader_New_Widgets.png`, fullPage: true });

    // Portfolio Wizard
    console.log(` Visiting ${BASE_URL}/portfolio`);
    await page.goto(`${BASE_URL}/portfolio`);
    await page.waitForLoadState('networkidle');

    console.log(' Clicking New Portfolio Button...');
    console.log(' Clicking New Portfolio Button...');
    // Try multiple selectors incase of text mismatch
    await page.getByRole('button', { name: /new portfolio/i }).click({ timeout: 5000 });

    await page.waitForTimeout(2000); // Wait for modal
    await page.screenshot({ path: `${ARTIFACT_DIR}/10_Portfolio_Wizard.png`, fullPage: true });

    console.log('Visual Exposure Complete.');
});
