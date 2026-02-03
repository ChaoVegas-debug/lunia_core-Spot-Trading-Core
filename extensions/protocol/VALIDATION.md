# Protocol Validation Contract

**Phase 9.1 — Protocol Boundary Hardening**

This document defines the immutable validation rules for the protocol boundary between the sealed execution core and the unsealed strategy sandbox.

---

## Core Invariants

### 1. Intent Type Constraints

#### ENTRY Intents
- **MUST** include `exit_plan: TradeExitPlan`
- **MUST** specify `symbol: str`
- **MUST** specify `direction: TradeDirection`
- **MUST** specify either `size_base` or `size_quote`
- Exit plan **MUST** define at least one exit condition:
  - `stop_loss_price` OR `stop_loss_pct`
  - `take_profit_price` OR `take_profit_pct`
  - `time_limit_ms`
  - `trail_start_pct`

#### EXIT Intents
- **MUST** specify `symbol: str`
- **MAY** include `size_base` or `size_quote` for partial exits
- `exit_plan` is ignored (exit is immediate)

#### ADJUST Intents
- **MUST** specify `symbol: str`
- **MUST** include updated `exit_plan`
- Does NOT change position size

#### NOOP Intents
- **MUST** include `rationale: str` (non-empty)
- All position fields **MUST** be `None`
- Documents the decision to take no action

#### REJECT Intents
- For **documentation only** (governance rejection record)
- Strategies **MUST NOT** emit REJECT intents
- Only governance layer may create REJECT intents

---

### 2. Protocol Version Enforcement

```python
PROTOCOL_VERSION = "1.0.1"
```

- **Every** `StrategyIntent` **MUST** set `protocol_version = PROTOCOL_VERSION`
- **Every** `StrategyManifest` **MUST** set `protocol_version = PROTOCOL_VERSION`
- Version mismatch → **REJECT** (fail-closed)
- Manifest validation: `manifest.is_valid == (manifest.protocol_version == PROTOCOL_VERSION)`

---

### 3. One Intent Per Tick (MVP Invariant)

- Strategy **MUST** return exactly **one** `StrategyIntent` per invocation
- No batching, no arrays, no parallel intents
- This constraint **MAY** be relaxed in future protocol versions

---

### 4. Deterministic Identifiers

#### `intent_id`
- **MUST** be deterministic from `(correlation_id, ts_ms, strategy_id)`
- Suggested: `SHA256(f"{correlation_id}:{ts_ms}:{strategy_id}")[:16]`
- Replay guarantee: same inputs → same ID

#### `correlation_id`
- Provided by `GovernanceContext`
- Strategy **MUST** pass through unchanged
- Enables end-to-end traceability (governance → intent → execution)

#### `run_id`
- Provided by `GovernanceContext`
- Identifies governance invocation cycle
- Strategy **MUST NOT** modify

---

### 5. Timestamp Semantics

```python
ts_ms: int  # UTC epoch milliseconds
```

- **All** timestamps **MUST** use UTC epoch milliseconds
- No timezones, no ISO strings, no ambiguity
- `StrategyIntent.ts_ms` **MUST** match `GovernanceContext.ts_ms`

---

## Serialization Rules

### Canonical JSON

All protocol types **MUST** serialize to **deterministic canonical JSON**:

1. **Sorted keys** for all dictionaries/mappings
2. **Enums** serialize via `.value` (string representation)
3. **Float precision**: 8 decimal places (configurable, but must be documented)
4. **No whitespace variations** (compact JSON recommended for hashing)

### Example

```python
from dataclasses import asdict
import json

intent = StrategyIntent(...)
canonical = json.dumps(
    asdict(intent),
    sort_keys=True,
    separators=(',', ':'),
    default=lambda e: e.value if isinstance(e, Enum) else str(e)
)
```

### Replay Guarantee

```
Context (governance + portfolio + markets) → Intent → Canonical JSON
```

Given identical context, strategy **MUST** produce identical canonical JSON.

---

## Boundary Enforcement

### Sealed Core Paths (IMMUTABLE)

```
lunia_core/forensic/
lunia_core/risk/
lunia_core/auth/
```

- **NO** imports from these modules
- **NO** mirroring or reimplementation
- **NO** side-channel access

### Extension Zone (UNSEALED)

```
extensions/protocol/
extensions/strategies/
sandbox/
```

- **ALL** strategy code **MUST** reside here
- Strategies **MAY** import from `extensions/protocol/` only
- Zero cross-contamination

---

## Read-Only Access Contract

Strategies receive **immutable snapshots**:

- `GovernanceContext` (frozen dataclass)
- `ShadowPortfolio` (frozen dataclass)
- `List[MarketSnapshot]` (frozen dataclasses)

**Guarantees:**
- No mutations possible (Python `frozen=True`)
- No side effects (pure functions)
- No I/O (no network, no filesystem, no logging)

---

## Validation Checklist

Before submitting `StrategyIntent`, verify:

- [ ] `protocol_version == PROTOCOL_VERSION`
- [ ] `intent_id` is deterministic
- [ ] `correlation_id` matches `GovernanceContext.correlation_id`
- [ ] `ts_ms` matches `GovernanceContext.ts_ms`
- [ ] `intent_type` is valid Enum value
- [ ] ENTRY intents include `exit_plan` with at least one condition
- [ ] NOOP intents include non-empty `rationale`
- [ ] No imports from sealed core
- [ ] No execution logic (pure data construction)
- [ ] Serializes to canonical JSON deterministically

---

## Acceptance Criteria (Phase 9.1)

Phase 9.1 is **GREEN** only if:

1. ✅ Zero sealed-core modifications
2. ✅ `protocol.py` is pure interface only (no logic, no I/O)
3. ✅ Exit planning enforced for ENTRY intents
4. ✅ Reference strategy (`reference_noop.py`) compiles and respects governance
5. ✅ Deterministic IDs and timestamps
6. ✅ Full traceability via `correlation_id`
7. ✅ Manifest validation passes (`manifest.is_valid == True`)

---

## Future Extensions (Out of Scope for 9.1)

- Multi-intent batching
- Async intent streams
- Strategy-to-strategy messaging
- Machine learning integration
- AutoML

**These are explicitly NOT part of Phase 9.1.**

---

## Audit Trail Example

```
┌─────────────────────────────────────────────────────────┐
│ GovernanceContext                                       │
│  run_id: "run_abc123"                                   │
│  correlation_id: "corr_xyz789"                          │
│  ts_ms: 1737543014000                                   │
│  risk_state: RiskState.GREEN                            │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│ StrategyIntent                                          │
│  intent_id: "e4b3c2a1d5f6"  (deterministic)             │
│  correlation_id: "corr_xyz789"  (pass-through)          │
│  ts_ms: 1737543014000  (pass-through)                   │
│  intent_type: IntentType.NOOP                           │
│  rationale: "Reference NOOP | risk_state=green"         │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│ Canonical JSON (deterministic, replay-safe)             │
│  {                                                      │
│    "correlation_id": "corr_xyz789",                     │
│    "intent_id": "e4b3c2a1d5f6",                         │
│    "intent_type": "noop",                               │
│    "protocol_version": "1.0.1",                         │
│    "rationale": "Reference NOOP | risk_state=green",    │
│    "ts_ms": 1737543014000,                              │
│    ...                                                  │
│  }                                                      │
└─────────────────────────────────────────────────────────┘
```

---

## Green Light Guarantee

When all validation rules pass, the protocol boundary guarantees:

1. **Sealed core is protected** from sandbox corruption
2. **Strategies can read** market/portfolio/governance state safely
3. **UI can display** full trade plans with exit strategies
4. **Auditors can trace** context → intent → execution deterministically
5. **Replay is possible** from canonical JSON

---

**Phase 9.1 Status**: Validation contract complete.  
**Next Phase**: 9.2 — Runner / Validator Implementation  
**Blocked Until**: Green light on protocol boundary artifacts.
