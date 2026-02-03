
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

// --- RESPONSIVENESS TESTS ---

test('Slider: Drag commits once on mouseup, not per tick', async ({ page }) => {
    // Track API calls
    const apiCalls: string[] = [];
    await page.route('**/*', (route, request) => {
        const url = request.url();
        if (url.includes('/api/') || url.includes('/ops/')) {
            if (request.method() !== 'GET') {
                apiCalls.push(`${request.method()} ${url}`);
            }
        }
        route.continue();
    });

    // Inject auth and navigate
    await page.goto(`${BASE_URL}/login`);
    await page.evaluate(() => {
        localStorage.setItem('lunia-auth-state', JSON.stringify({
            role: 'ADMIN',
            bearerToken: 'sim-valid-token-123',
            opsToken: 'sim-ops-token-123',
            user: {
                id: 1,
                email: 'test@lunia.test',
                role: 'ADMIN',
                tier: 'INST_PRO',
                is_active: true,
                onboarding_completed: true,
                kyc_status: 'VERIFIED'
            },
            expiresAt: new Date(Date.now() + 86400000).toISOString()
        }));
    });

    await page.goto(`${BASE_URL}/trader`);
    await page.waitForTimeout(2000); // Wait for widgets to load

    // Find a slider
    const slider = page.locator('input[type="range"].slider-institutional').first();
    await slider.waitFor({ state: 'visible', timeout: 5000 });

    // Clear API call history
    apiCalls.length = 0;

    // Get slider bounding box
    const box = await slider.boundingBox();
    if (!box) throw new Error('Slider not found');

    // Simulate dragging: multiple mousemoves over 1 second
    await page.mouse.move(box.x + 10, box.y + box.height / 2);
    await page.mouse.down();

    for (let i = 0; i < 10; i++) {
        await page.mouse.move(box.x + 10 + (i * 10), box.y + box.height / 2);
        await page.waitForTimeout(100);
    }

    // Count API calls during drag (should be 0)
    const callsDuringDrag = apiCalls.length;
    console.log(`API calls during drag: ${callsDuringDrag}`);

    // Release mouse
    await page.mouse.up();
    await page.waitForTimeout(500); // Wait for commit

    const callsAfterRelease = apiCalls.length;
    console.log(`Total API calls after release: ${callsAfterRelease}`);
    console.log('API calls:', apiCalls);

    // PASS: Should have at most 1-2 commits, not 10+
    expect(callsDuringDrag).toBeLessThanOrEqual(2);
    expect(callsAfterRelease).toBeLessThanOrEqual(3);

    await page.screenshot({ path: `${ARTIFACT_DIR}/slider_drag_test.png` });
});

test('Toggle: UI updates instantly before API completes', async ({ page }) => {
    // Inject auth
    await page.goto(`${BASE_URL}/login`);
    await page.evaluate(() => {
        localStorage.setItem('lunia-auth-state', JSON.stringify({
            role: 'ADMIN',
            bearerToken: 'sim-valid-token-123',
            opsToken: 'sim-ops-token-123',
            user: {
                id: 1,
                email: 'test@lunia.test',
                role: 'ADMIN',
                tier: 'INST_PRO',
                is_active: true,
                onboarding_completed: true,
                kyc_status: 'VERIFIED'
            },
            expiresAt: new Date(Date.now() + 86400000).toISOString()
        }));
    });

    await page.goto(`${BASE_URL}/trader`);
    await page.waitForTimeout(2000);

    // Find a toggle switch
    const toggleInput = page.locator('.switch input[type="checkbox"]').first();
    await toggleInput.waitFor({ state: 'attached', timeout: 5000 });

    // Get initial state
    const initialChecked = await toggleInput.isChecked();
    console.log(`Initial toggle state: ${initialChecked}`);

    // Click the toggle
    const startTime = Date.now();
    await toggleInput.click({ force: true });

    // Check state immediately (within 50ms target)
    const newChecked = await toggleInput.isChecked();
    const clickDuration = Date.now() - startTime;

    console.log(`New toggle state: ${newChecked}, time to update: ${clickDuration}ms`);

    // PASS: State should have flipped instantly
    expect(newChecked).not.toBe(initialChecked);
    expect(clickDuration).toBeLessThan(200); // Should be <50ms but allowing 200ms for test overhead

    await page.screenshot({ path: `${ARTIFACT_DIR}/toggle_instant_test.png` });
});
