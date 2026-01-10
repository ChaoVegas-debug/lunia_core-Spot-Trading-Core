# LUNIA / ALADDIN Governance Logic & Integrity Specification (v1.0)

**Phase: P0.4**
**Status: FINAL DRAFT**
**Scope: Conflict Resolution, Emergency States, and System Integrity**

---

## 1. Human vs Bot Conflict Model

The fundamental axiom of LUNIA is: **The Blockchain Truth is Absolute.**
If the Exchange State diverges from the Internal Strategy Model, the System must **PAUSE**, **ASSESS**, and **request INTERVENTION**. It must NEVER blindly overwrite user actions.

### 1.1 Conflict Scenarios

#### Scene A: User Manually SELLS a Portfolio Asset
*Context: Bot expects 1.0 BTC. User sells 0.5 BTC via Exchange UI.*
- **Detection**: WebSocket Execution Report (immediate) OR Polling `GET /balances` (lag < 5s).
- **Classification**: **HARD DRIFT** (Negative Deviation).
- **Reaction**:
  1.  **Immediate**: **PAUSE** Strategies involving BTC. Downgrade Mode `AUTO` → `SEMI`.
  2.  **Notification**: "Drift Detected: BTC Position decreased manually."
- **Recovery**:
  - Option A: "Rebalance" (Bot buys back 0.5 BTC).
  - Option B: "Accept New State" (Update Portfolio Target to 0.5 BTC).

#### Scene B: User Manually BUYS an Asset (Shadow Position)
*Context: User buys 1000 DOGE. DOGE is not in any active strategy.*
- **Detection**: Balance Appearance in `GET /balances`.
- **Classification**: **UNMANAGED ASSET** (Not Drift, as model expectation is 0).
- **Reaction**:
  1.  **Status**: **IGNORE** by Trading Engine (unless Capital Cap is breached).
  2.  **Capital Check**: If `Free Capital` is used, ensure `Global Capital Cap` is not violated. If violated → **Alert Capital Breach**.
- **Recovery**: User must manually manage or add "New Strategy" for DOGE.

#### Scene C: User WITHDRAWS Funds
*Context: User withdraws USDT. Remaining USDT < Reserve Requirements.*
- **Detection**: Balance update.
- **Classification**: **CAPITAL VIOLATION** (Critical).
- **Reaction**:
  1.  **Immediate**: **TRANSITION to SAFE MODE**.
  2.  **Action**: Cancel all open BUY orders to free liquidity. Halt all new entries.
- **Recovery**: Deposit funds OR Reduce Strategy Allocations to fit new capital.

#### Scene D: Leverage/Margin Mode Change
*Context: User changes account from 1x to 10x.*
- **Detection**: `GET /account/info` properties mismatch.
- **Classification**: **RISK BREACH**.
- **Reaction**:
  1.  **Immediate**: **EMERGENCY STOP**.
  2.  **Reason**: Risk Model invalid. Liquidation risk unquantified.
- **Recovery**: User must revert leverage settings manually.

#### Scene E: Forced Liquidation / Partial Fill
*Context: Exchange liquidates position due to volatility.*
- **Detection**: Execution Report `type: LIQUIDATION`.
- **Classification**: **CATASTROPHIC FAILURE**.
- **Reaction**:
  1.  **Immediate**: **EMERGENCY STOP**.
  2.  **Action**: **LOCK ACCOUNT**. Prevent Bot from "buying the dip" (death spiral prevention).
- **Recovery**: Manual Admin Reset required.

---

## 2. Emergency States & Modes (State Machine)

The system operates in one of 5 distinct states. Transitions are strictly governed.

### 2.1 State Definitions

| State | Trading | Auto Resume? | Visual Indicator | Description |
| :--- | :--- | :--- | :--- | :--- |
| **RUNNING** | ✅ Allowed | ✅ Yes | 🟢 Green Pulse | Normal Operation. |
| **SAFE MODE** | ⚠️ Reduce Only | ❌ NO | 🟡 Yellow Banner | Risk/Capital Limits hit. No new risks allowed. |
| **PAUSED** | ⏸ Frozen | ❌ NO | 🟠 Orange | User requested pause. Orders remain. |
| **STOP (KILL)**| 🛑 HALTED | ❌ NO | 🔴 Red Flash | Emergency. All Orders CANCELLED. |
| **DEGRADED** | ⚠️ Limited | ❓ If transient | 🔌 Gray Overlay | Data feed/API lag. Execution unreliable. |

### 2.2 Transitions

- **RUNNING → STOP**: Any Critical Fault, Liquidation, or User Kill Switch.
- **STOP → RUNNING**: **IMPOSSIBLE**. Must go STOP → PAUSED → (Manual Checks) → RUNNING.
- **RUNNING → SAFE**: Capital Cap breached.
- **SAFE → RUNNING**: Only after Capital/Risk metrics restored.

### 2.3 Liquidation Policy
- **System Initiated**: The Bot NEVER auto-liquidates positions unless explicitly configured for "Stop Loss".
- **Forbidden**: The Bot DOES NOT panic-sell during outages or "DEGRADED" states. It holds.

---

## 3. "Convert to Stablecoin" Logic (Nuclear Option)

*Warning: This is a high-impact, irreversible governance action.*

### 3.1 Constraints
- **Trigger**: Only available in `MANUAL` or `STOP` modes. Disabled in `AUTO`.
- **Role**: `ADMIN` or `TRADER` (with 2FA/Airlock).
- **Execution**:
  1.  **Cancel All Orders** (First).
  2.  **Get Quotes** for all assets.
  3.  **Execute Market Sells** (Batch 1: High Liquidity).
  4.  **Execute Market Sells** (Batch 2: Low Liquidity).
- **Fail-Safe**: If slippage > 5%, **ABORT** remaining batch.

### 3.2 UI Integration
- **Button**: "FLATTEN PORTFOLIO".
- **Color**: Danger Red.
- **Confirmation**: Type "FLATTEN" to confirm.

---

## 4. Auto Mode Recovery Rules

Once `AUTO` is lost, it is **Hard Lost**.

### 4.1 Disabling Auto
Auto is disabled if:
- Drift detected.
- API Error Rate > 5% / min.
- Heartbeat missed (30s).
- User Intervention (Manual Order).

### 4.2 Re-Arming Rules
To resume `AUTO`:
1.  **Drift Resolution**: User must explicitly "Accept" or "Fix" matches.
2.  **Airlock**: Must pass Airlock/Timer again if required by Risk Profile.
3.  **Cooldown**: 60s cooldown after any Emergency Stop.

**NO AUTO-RESUME**. The system never "guesses" it's safe to start again.

---

## 5. UI & UX Requirements

### 5.1 Indicators
- **Who is Driving?**: Top Bar must say "AUTO: AI DRIVER" or "MANUAL: HUMAN DRIVER".
- **Why Blocked?**: Hovering a disabled button MUST show the exact governance rule (e.g., "Disabled: Capital Cap Exceeded").

### 5.2 Mandatory Banners
- **Drift Warning**: "⚠️ Portfolio Drift Detected. Automation Paused."
- **Data Stale**: "🔌 Data > 10s Old. Displayed prices may be inaccurate."

---

## 6. Backend Contract Expectations

The Frontend assumes the Backend is the "System of Record", but verifies locally.

### 6.1 Required Signals
- `ops_state.global_stop`: Boolean.
- `portfolio.drift_detected`: Boolean.
- `api_health.latency_ms`: Number.

### 6.2 Missing Data Behavior
- If `GET /balances` fails:
  - **Hide** Portfolio Charts.
  - **Show** "Connection Lost" Skeleton.
  - **Disable** "Deploy Strategy" Buttons.
  - **DO NOT** show last known balance as "Current".

---

## 7. Integrity Statement

This specification guarantees that LUNIA operates as a **Fiduciary Agent**, not a Black Box.
By enforcing:
1.  **Conflict = Pause** (Never fight the human),
2.  **Drift = Downgrade** (Never guess the state),
3.  **Stop = Hard Stop** (Never ghost-trade),

We ensure that Institutional Clients retain **Ultimate Sovereignty** over their capital, while the Bot acts as a **compliant, fail-safe servant**.

**Approved for Implementation: P0.4**
