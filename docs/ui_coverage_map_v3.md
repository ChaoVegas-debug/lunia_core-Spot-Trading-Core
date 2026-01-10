# LUNIA / ALADDIN — UI Coverage Map v3.1 (MASTER)

**Objective:** End-to-end operable web terminal verification.
**Principle:** Honest UI. No dead ends.

## Status Legend
- **[LIVE]**: Works against real backend endpoints.
- **[PREVIEW]**: Works in Preview Mode via simulated data/actions.
- **[GAP]**: Missing backend endpoint; UI exists but shows "Not Implemented".

---

## 1. TRADER COCKPIT (`/trader`)
| Component | Status | Fallback Strategy |
|-----------|--------|---------------------|
| **Command Strip** | [PREVIEW] | `simulatedBackend` (Mode/Stop/Drift) |
| **Control Authority** | [LIVE] | N/A |
| **Portfolio Reality** | [PREVIEW] | `PreviewStore` Aggregates |
| **Execution Timeline** | [PREVIEW] | `PreviewStore` Audit Log |
| **Decision Plane** | [PREVIEW] | Safe Empty Arrays |

## 2. STRATEGY ENGINE (`/strategies`)
| Component | Status | Fallback Strategy |
|-----------|--------|---------------------|
| **Registry List** | [PREVIEW] | `PreviewStore` Strategy List |
| **Simulation** | [PREVIEW] | `simulateStrategyRun` (Mock) |
| **Duplication** | [PREVIEW] | `duplicateStrategy` (Mock) |
| **Active Orders** | [PREVIEW] | `StrategyOrdersDrawer` (Mock Items) |

## 3. ACCOUNT & TRUST (`/account`)
| Component | Status | Fallback Strategy |
|-----------|--------|---------------------|
| **Trust Widget** | [PREVIEW] | `PreviewStore` User Mock |
| **Timeline** | [PREVIEW] | `PreviewStore.audit_log` |
| **Capability Matrix** | [PREVIEW] | Derived from Tier (Static) |

## 4. ADMIN PLANE (`/admin`)
| Component | Status | Fallback Strategy |
|-----------|--------|---------------------|
| **Dashboard** | [PREVIEW] | `simulatedBackend` Mock Stats |
| **User Manager** | [PREVIEW] | `AdminPage` Table + Mock Actions |
| **Incidents** | [GAP] | Not yet implemented |
| **Audit Log** | [PREVIEW] | `PreviewStore.audit_log` |

## 5. SYSTEM PLANE (`/system`)
| Component | Status | Fallback Strategy |
|-----------|--------|---------------------|
| **Event Stream** | [PREVIEW] | `simulatedBackend.getSystemEvents` |
| **Capital Gov** | [PREVIEW] | `SystemPage` + `setGlobalCapitalCap` |
| **State Inspector** | [PREVIEW] | `SystemPage` JSON Dump of `OpsState` |

## 6. FUND PLANE (`/fund`)
| Component | Status | Fallback Strategy |
|-----------|--------|---------------------|
| **Overview KPIs** | [PREVIEW] | `simulatedBackend.getFundOverview` |
| **Allocations** | [PREVIEW] | `simulatedBackend.getFundPortfolio` |
| **Strategy List** | [PREVIEW] | `simulatedBackend.getFundStrategies` |
