# Phase P4: Operator UX Completion Specification

**Goal**: Transform the UI from "technically complete" into an institutional operator console with high information density, explainability, and intervention tools.

## 1. Core Components & Architecture

### A. Unified Execution Command Strip
*   **Path**: `src/components/widgets/ExecutionCommandStrip.tsx`
*   **Mount**: `TraderPanel.tsx` (Top Header)
*   **Data Sources**: `getOpsState`, `getHealth`
*   **Features**:
    *   Mode Toggle (MANUAL / SEMI / AUTO) -> triggers `AirlockModal` for AUTO.
    *   Driver Indicator (HUMAN / AI).
    *   Status Capsule (LIVE / DRIFT / VETO).
    *   Danger Actions: FLATTEN, KILL SWITCH.
    *   "Why?" Action -> opens `WhyPanel`.

### B. The "Why" Layer (Explainability)
*   **Path**: `src/components/modals/WhyPanel.tsx`
*   **Data**: `src/governance/rulebook.ts` (Static Rule Definitions)
*   **Usage**: Global Modal/Drawer triggered by ANY governance block (drift, veto, stop).
*   **Content**:
    *   Rule ID & Description.
    *   Trigger Metric vs Limit.
    *   Recovery Checklist.

### C. Human Intervention Decision Panel
*   **Path**: `src/components/overlays/HumanInterventionDecisionPanel.tsx`
*   **Mount**: `TraderPanel.tsx` (Overlay Layer)
*   **Trigger**: `ops.drift_status === 'DRIFT'` OR `ops.veto_reason`.
*   **Actions**:
    *   Accept Reality (Update Baseline).
    *   Revert via Bot.
    *   Flatten Exposure.
*   **Governance**: Blocks AUTO mode until resolved.

### D. Portfolio Action Surface
*   **Path**: `src/components/widgets/OperatorActionPanel.tsx` (New)
*   **Integration**: Inside `PortfolioStructureWidget` rows.
*   **Actions**: Pause, Risk Adjust, Freeze, Convert.
*   **States**: AI HOLDING, BLOCKED, EXECUTING.

## 2. Page Specific Enhancements

### Strategies Page (`/strategies`)
*   **Controls**: Simulate, Duplicate, Archive.
*   **Status Indicators**: Paper/Live, Active/Paused.

### Account Page (`/account`)
*   **Trust Progress**: Timeline view of trust events + "Unlocks Next".

### Landing Page (`/`)
*   **Narrative**: Institutional "Not for Retail" messaging.
*   **Content**: Governance Constitution, Non-Custodial, Screen Gallery.

## 3. Governance Rulebook Scheme
```typescript
interface GovernanceRule {
    id: string;
    title: string;
    description: string;
    severity: 'WARNING' | 'CRITICAL' | 'FATAL';
    recoverySteps: string[];
}
```

## 4. Acceptance Criteria
1.  **Command Strip**: Always visible, updates in real-time.
2.  **Why Panel**: Explains at least one Veto/Drift event clearly.
3.  **Intervention**: Forces a decision when drift is detected (mocked if needed).
4.  **Honesty**: All missing backend actions are labeled "Integration Pending" or logged to UI journal only.

## 5. Preview Mode (P4.5)
**Goal**: Allow Owner/Stakeholder demo of the UI even when backend is offline or gated.
*   **Env Feature**: `VITE_PREVIEW_MODE=1`
*   **Soft Blocks**: "System Halted" and "Require Onboarding" overlays become dismissible.
*   **Simulation**: Fallback to `simulatedBackend.ts` for "Happy Path" demo (Ops: AUTO, Health: OK) when real backend is unreachable.
*   **Badge**: Distinct "PREVIEW MODE" badge to prevent confusion with real production data.
