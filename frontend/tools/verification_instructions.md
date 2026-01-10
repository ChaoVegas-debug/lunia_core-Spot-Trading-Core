
# Final Verification Checklist

The Critical `.length` Crash Fix and Audit is COMPLETE.

## 1. Safety Checks Applied
- **Core**: `src/utils/safe.ts` created.
- **Adapter**: `adapter.ts` returns `[]` by default for all lists.
- **Widgets**: The following components are now guarded against `undefined` crashes:
  - `SignalsWidget`
  - `PortfolioStructureWidget`
  - `PortfolioWidget`
  - `StrategyHealthWidget`
  - `TradingBlotterWidget`
  - `SystemActivityWidget`
  - `RiskWidget`
  - `BalancesWidget`
  - `ExchangeControlsWidget`
  - `CreatePortfolioWizard`
  - `IntelligenceWidget`
  - `GovernanceBanners`
  - `PreviewStatusBadge`

## 2. Launch Instructions

To launch the Full Institutional Cockpit in Preview Mode:

```bash
# 1. Install Dependencies (if needed)
npm install

# 2. Launch Server
# This enables Preview, Simulation, and Proof modes.
# It unlocks the Trader Panel and populates it with rich simulated data.
VITE_PREVIEW_MODE=1 VITE_PREVIEW_SIMULATION=1 VITE_PROOF_MODE=1 npm run dev -- --port 5180
```

## 3. Manual Verification
Open `http://localhost:5180/trader`

- **Visual Check**:
  - Verify "AI Signals" list RENDERED (no crash).
  - Verify "Risk Engine" constraints RENDERED.
  - Verify "Portfolio Structure" assets RENDERED.
  - Verify "Trading Blotter" RENDERED.

- **Interaction Check**:
  - Click "Review" on an AI Proposal (Intelligence Widget).
  - Click "Limit Overview" in Risk Widget.
  - Launch "Portfolio Wizard" via Create Modal (if button accessible).

## 4. Playwright Smoke Test
Run the automated smoke test to confirm stability:
```bash
npx playwright test tools/trader_smoke_test.spec.ts
```
