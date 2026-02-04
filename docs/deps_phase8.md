# Phase 8.1A — Dependency Strategy

**Pinned Dependencies for Production Stability**

**Date**: February 4, 2026  
**Phase**: 8.1A (OpenAI Provider)

---

## Overview

Phase 8.1A introduces real LLM provider integration with strict dependency requirements. This document defines the pinned versions, installation strategy, and compatibility guarantees.

---

## Required Dependencies

### Core (Phase 8.0 + 8.1A)

| Package | Version | Purpose | Critical? |
|---------|---------|---------|-----------|
| **jsonschema** | `>=4.17.0` | Schema validation (AIAnalysis contract) | ✅ YES |
| **openai** | `>=1.0.0,<2.0.0` | OpenAI SDK (provider) | ✅ YES (for real provider) |
| **tiktoken** | `>=0.5.0` | Accurate token estimation | ✅ YES (fail-closed if missing) |
| **pytest** | `>=7.0.0` | Testing framework | ✅ YES (dev) |
| **pytest-asyncio** | `>=0.21.0` | Async test support | ✅ YES (dev) |

### Optional

| Package | Version | Purpose | Critical? |
|---------|---------|---------|-----------|
| **httpx** | `>=0.24.0` | HTTP client (if not using OpenAI SDK) | ❌ NO (SDK preferred) |

---

## Installation Commands

### Production Environment

```bash
# Core dependencies (required)
pip3 install jsonschema>=4.17.0
pip3 install openai>=1.0.0,<2.0.0
pip3 install tiktoken>=0.5.0
```

### Development Environment

```bash
# All dependencies (core + dev)
pip3 install jsonschema>=4.17.0 \
             openai>=1.0.0,<2.0.0 \
             tiktoken>=0.5.0 \
             pytest>=7.0.0 \
             pytest-asyncio>=0.21.0
```

### Verification

```bash
# Verify all imports work
cd lunia_core
python3 -m pytest tests/test_phase8_env_deps.py -v
```

**Expected**: ALL PASS (imports successful)

---

## Dependency Rationale

### `jsonschema` (>=4.17.0)

**Why**: AIAnalysis schema validation (Phase 7)

**Introduced**: Phase 7 (Synthetic Advisor)

**Impact if missing**:

- Schema validation fails
- AI responses not validated against contract
- Potential runtime errors on malformed AI output

**Fail mode**: Fail-closed (AI disabled if schema invalid)

### `openai` (>=1.0.0,<2.0.0)

**Why**: Official OpenAI SDK for inference

**Introduced**: Phase 8.1A (OpenAI Provider)

**Version constraint**:

- `>= 1.0.0`: Requires v1+ API (stable)
- `< 2.0.0`: Pin to v1.x to avoid breaking changes

**Impact if missing**:

- `OpenAIProvider` unavailable
- `get_provider("openai")` returns `None`
- Gateway falls back to `MockProvider`
- Emits `AI_PROVIDER_FORCED_FALLBACK` event

**Fail mode**: Graceful degradation (fallback to MockProvider)

### `tiktoken` (>=0.5.0)

**Why**: Accurate token estimation for cost prediction

**Introduced**: Phase 8.1A (Token Estimation)

**Impact if missing**:

- Token estimation falls back to heuristic (~4 chars/token)
- Cost estimates **LESS ACCURATE**
- May trigger per-signal budget cap unexpectedly
- Emits `AI_DEPENDENCY_MISSING` event (if auditing enabled)

**Fail mode**: Heuristic fallback (documented, audited)

**Audit requirement**: MUST use tiktoken for production (fail-closed bias)

### `pytest` + `pytest-asyncio` (dev only)

**Why**: Testing framework for Phase 8.0/8.1A tests

**Introduced**: Phase 8.0

**Impact if missing**:

- Cannot run tests
- CI/CD pipeline fails

**Fail mode**: Development blocker (not runtime)

---

## Compatibility Matrix

| Python Version | jsonschema | openai | tiktoken | pytest | Status |
|----------------|------------|--------|----------|--------|--------|
| **3.10** | 4.17+ | 1.0–1.x | 0.5+ | 7.0+ | ✅ Tested |
| **3.11** | 4.17+ | 1.0–1.x | 0.5+ | 7.0+ | ✅ Tested |
| **3.12** | 4.17+ | 1.0–1.x | 0.5+ | 7.0+ | ✅ Expected |
| 3.9 | 4.17+ | 1.0–1.x | 0.5+ | 7.0+ | ⚠️ Not tested |

**Recommendation**: Python 3.10+ for production

---

## Reaching 7/7 GREEN Tests

### Phase 8.0 Tests (6/7 → 7/7)

**Issue**: `jsonschema` not installed

**Fix**:

```bash
pip3 install jsonschema>=4.17.0
```

**Verify**:

```bash
cd lunia_core
python3 -m pytest tests/test_phase8_control_plane.py -v
```

**Expected**: 16/16 PASS

### Phase 8.1A Tests (23/23)

**Prerequisites**:

```bash
pip3 install jsonschema>=4.17.0 \
             openai>=1.0.0,<2.0.0 \
             tiktoken>=0.5.0 \
             pytest>=7.0.0 \
             pytest-asyncio>=0.21.0
```

**Run**:

```bash
cd lunia_core
python3 -m pytest tests/test_phase8_1a_openai_provider.py -v
```

**Expected**: 23/23 PASS (all mocked, no live spend)

### Dependency Verification Test

**New test**: `test_phase8_env_deps.py`

**Run**:

```bash
python3 -m pytest tests/test_phase8_env_deps.py -v
```

**Expected**: Verifies all imports successful

---

## Pinning Strategy (requirements.txt)

If repo uses `requirements.txt`:

```txt
# Phase 8.0 + 8.1A Dependencies
jsonschema>=4.17.0,<5.0.0
openai>=1.0.0,<2.0.0
tiktoken>=0.5.0,<1.0.0

# Optional: development
pytest>=7.0.0,<8.0.0
pytest-asyncio>=0.21.0,<1.0.0
```

**Install**:

```bash
pip3 install -r requirements.txt
```

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'jsonschema'"

**Fix**:

```bash
pip3 install jsonschema
```

### "ModuleNotFoundError: No module named 'openai'"

**Fix**:

```bash
pip3 install openai
```

**Note**: If intentionally omitting (shadow mode disabled), this is expected. Provider will fallback to MockProvider.

### "ModuleNotFoundError: No module named 'tiktoken'"

**Fix** (production, recommended):

```bash
pip3 install tiktoken
```

**Alternative** (dev/test only): Accept heuristic fallback (documented degradation)

### Tests fail with "no module named pytest_asyncio"

**Fix**:

```bash
pip3 install pytest-asyncio
```

---

## Phase 8.3 Dependencies (Future)

Future phases may add:

- `prometheus-client` (metrics export)
- `anthropic` (Phase 8.1B, Anthropic provider)
- `httpx` (if custom HTTP client needed)

**Strategy**: Add incrementally, document in this file

---

**Phase 8.1A Dependency Strategy** — Defined & Documented
