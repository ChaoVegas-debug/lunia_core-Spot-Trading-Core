# Widget Visibility Map

| Widget Name | Visibility Strategy (Live Mode) | Gating Condition (Fail-Closed) | Visual Outcome on Failure |
|---|---|---|---|
| **BalancesWidget** | **BLOCK** | `auth_proven=VERIFIED` | Shows "Data Unavailable" Overlay with 502/403 Error |
| **RiskWidget** | **BLOCK** | `auth_proven=VERIFIED` | Shows "Risk Engine Offline" Overlay |
| **TradingBlotter** | **BLOCK** | `auth_proven=VERIFIED` | Shows "Order Data Unavailable" Overlay |
| **ExecutionTimeline** | **BLOCK** | `auth_proven=VERIFIED` | Shows "Logs Unavailable" Overlay |
| **ManualTradeWidget** | Visible (Safe) | N/A (Client-side Form) | Submit action fails if Auth fails (Error Toast) |
| **PortfolioReality** | Visible (Safe) | N/A (Calculated) | Shows 0 or partial data if dependencies fail |
| **StructureWidget** | Visible (Safe) | N/A (Client-side) | Shows empty structure |

## Gating Logic Explained
- **BLOCK**: The entire widget is replaced by a `<WidgetBlocker>` component when the data dependency fails with a critical error (Auth/Network).
- **Visible (Safe)**: The widget relies on client-side state or non-critical data and remains fully interactive/visible, though actions may fail.

**DIAGNOSTICS**:
Admins can inspect the exact visibility state via the new **Diagnostics Panel** in `/admin`.
