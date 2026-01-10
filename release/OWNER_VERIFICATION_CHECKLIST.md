# Owner Verification Checklist (Click-by-Click)

## 1. Startup & Login
1.  [ ] **Open**: `http://localhost:5173/trader`
2.  [ ] **Login**: `trader@example.com` / `trader123`
3.  [ ] **Verify**: Land on Trader Cockpit. No "Connection Refused" error.

## 2. Control Plane (Left)
4.  [ ] **System Mode**: Click `MANUAL`. Confirm "Mode: MANUAL" status chip updates.
5.  [ ] **Capital**: Move "Global Cap" slider to 60%. Click `Review` -> `Confirm`.
6.  [ ] **Verify**: Pie chart updates. Toast "Capital Updated".
7.  [ ] **Exchanges**: Toggle "Binance" OFF. Click `Review` -> `Confirm`.
8.  [ ] **Verify**: Binance status shows "DISC" (Gray/Red).

## 3. Decision Plane (Center)
9.  [ ] **Active Portfolios**: Check for `long_term_main` and `tactical_alpha`.
10. [ ] **Expand**: Click `▼ SHOW ASSETS` on `tactical_alpha`.
11. [ ] **Verify**: 3 Asset Cards Visible (ARB, OP, LDO).
12. [ ] **Action**: Click `REBALANCE` (⚖️). Confirm Dialog "Yes".
13. [ ] **Verify**: Toast "Action Initiated". Log entry appears in Right Column.

## 4. Risk & Intel Plane (Right)
14. [ ] **Strategy**: Move "Micro Trend" slider. Click `Review`.
15. [ ] **Risk**: Click `Edit Limits`. Click `🛡️` (Shield Preset).
16. [ ] **Verify**: Max Positions drops to 3.
17. [ ] **Save**: Click `Save`. Confirm.
18. [ ] **Logs**: Verify "LIMIT_UPDATE" and "PORTFOLIO_ACTION" events are top of list.

## 5. Safety Checks
19. [ ] **Global Halt**: Click `EMERGENCY HALT` (Red Button).
20. [ ] **Verify**: Banner "SYSTEM HALTED" appears. All inputs disabled (if implemented) or subsequent actions fail.
21. [ ] **Restore**: (If supported in UI) or restart backend.
