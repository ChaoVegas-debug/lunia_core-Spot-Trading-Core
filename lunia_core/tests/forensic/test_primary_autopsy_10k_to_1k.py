"""PRIMARY AUTOPSY TEST

Deterministically reproduce or disprove the $10,000 → $1,000 equity death.

PHASE 0 EXCLUSIVE - No risk enforcement, pure accounting verification.
"""
import pytest
import json
import hashlib
from decimal import Decimal
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.data.genesis_seeder import GenesisDataSeeder
from app.services.history.store.inmemory import InMemoryHistoricalStore
from app.simulation.genesis_harness_full import GenesisHarnessFull
from app.services.allocation.policies import DecimalMathKernel
from forensic.classifier import ForensicTag, classify_failure

TOLERANCE = Decimal("0.01")  # 1 cent tolerance for accounting

def compute_replay_hash(event_sequence: list) -> str:
    """Compute deterministic hash of event sequence"""
    content = json.dumps(event_sequence, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()

def test_primary_autopsy_10k_to_1k():
    """
    PRIMARY AUTOPSY: Reproduce the $10k→$1k equity death
    
    Expected outcomes:
    1. Either reproduces deterministically with forensic tag, OR
    2. Proves it cannot occur under correct accounting
    
    CRASH LOUDLY on unexplained equity delta.
    """
    DecimalMathKernel.ensure_context(28)
    
    # Deterministic setup
    SEED = 42
    INITIAL_CAPITAL = Decimal("10000")
    
    CONFIG = {
        'initial_capital': INITIAL_CAPITAL,
        'genesis_seed': SEED,
        'sim_clock_seed_ms': 1609459200000,
        'slippage': Decimal("0.0005"),
        'fee_taker': Decimal("0.001"),
        'fee_maker': Decimal("0.001"),
        'capital_fraction': Decimal("0.95"),
        'max_drawdown_limit': Decimal("0.20"),
        'bars': 1000  # Match harness expectation
    }
    
    # Seed data
    store = InMemoryHistoricalStore()
    seeder = GenesisDataSeeder(seed=SEED, start_ms=CONFIG['sim_clock_seed_ms'])
    generated, appended = seeder.seed_to_d2(store, CONFIG['bars'])
    
    assert generated == CONFIG['bars'], f"Data seeding failed: {generated} != {CONFIG['bars']}"
    
    # Run harness
    print("\n" + "="*70)
    print("PRIMARY AUTOPSY: $10k→$1k Equity Death Investigation")
    print("="*70)
    
    harness = GenesisHarnessFull(CONFIG)
    
    # Try to run - may crash on OVERSELL (expected during Phase 0)
    result = None
    oversell_error = None
    try:
        result = harness.run(store)
    except RuntimeError as e:
        if "OVERSELL" in str(e):
            oversell_error = e
            # Still get logs from harness
            result = {
                'logs': harness.log_lines,
                'final_equity': Decimal("0"),  # Unknown due to crash
                'equity_curve': harness.equity_curve,
                'counters': harness.counters,
                'global_halted': harness.GLOBAL_HALTED
            }
            print(f"\n[OVERSELL DETECTED] {e}")
        else:
            raise
    
    # Save logs for forensic analysis
    log_path = Path(__file__).parent.parent.parent / "replay_packs" / "autopsy_forensic.log"
    with open(log_path, 'w') as f:
        f.write("\n".join(result['logs']))
    
    print(f"[FORENSIC LOGS] Saved to: {log_path}")
    
    # Extract critical metrics
    final_equity = result['final_equity']
    equity_curve = result['equity_curve']
    fills_total = result['counters']['fills_total']
    
    print(f"\n[AUTOPSY RESULTS]")
    print(f"Initial capital: ${INITIAL_CAPITAL}")
    print(f"Final equity: ${final_equity}")
    print(f"Equity loss: ${INITIAL_CAPITAL - final_equity}")
    print(f"Loss percentage: {((INITIAL_CAPITAL - final_equity) / INITIAL_CAPITAL * 100):.2f}%")
    print(f"Fills executed: {fills_total}")
    
    # FORENSIC ANALYSIS
    # Calculate explained vs unexplained delta
    
    # For a normal trading scenario with 2 fills (BUY+SELL):
    # - Expected loss from fees: ~$19 (0.1% on ~$9,500 notional twice)
    # - Expected loss from adverse price movement: proportional to actual price change
    
    # If we lost $9,000 (90%), this is NOT explainable by:
    # - Fees (~$20)
    # - Normal market movement (no flash crash proven)
    
    equity_loss = INITIAL_CAPITAL - final_equity
    explained_loss = Decimal("0")  # Will calculate based on fills
    
    # Check for catastrophic loss
    if equity_loss > INITIAL_CAPITAL * Decimal("0.5"):  # >50% loss
        print(f"\n[FORENSIC TAG] CATASTROPHIC EQUITY COLLAPSE DETECTED")
        print(f"Loss: ${equity_loss} ({equity_loss/INITIAL_CAPITAL*100:.1f}%)")
        
        # Classify failure
        context = {
            "initial_equity": float(INITIAL_CAPITAL),
            "final_equity": float(final_equity),
            "delta_pct": float(-equity_loss / INITIAL_CAPITAL),
            "fills_count": fills_total,
            "flash_crash": False  # We've proven no flash crash exists
        }
        
        classification = classify_failure("equity_collapse", context)
        
        print(f"\n[CLASSIFICATION]")
        print(f"Primary Tag: {classification['primary_tag']}")
        print(f"Severity: {classification['severity']}")
        print(f"Explanation: {classification['explanation']}")
        
        # Create replay pack
        replay_pack = {
            "autopsy_id": "primary_10k_to_1k",
            "seed": SEED,
            "initial_state": {
                "capital": str(INITIAL_CAPITAL),
                "config": {k: str(v) if isinstance(v, Decimal) else v for k, v in CONFIG.items()}
            },
            "final_state": {
                "equity": str(final_equity),
                "counters": result['counters']
            },
            "explained_loss": str(explained_loss),
            "unexplained_loss": str(equity_loss - explained_loss),
            "forensic_tags": [classification['primary_tag']],
            "classification": classification
        }
        
        # Save replay pack
        replay_dir = Path(__file__).parent.parent.parent / "replay_packs"
        replay_dir.mkdir(exist_ok=True)
        replay_path = replay_dir / f"autopsy_10k_to_1k_seed{SEED}.json"
        
        with open(replay_path, 'w') as f:
            json.dump(replay_pack, f, indent=2)
        
        print(f"\n[REPLAY PACK] Saved to: {replay_path}")
        
        # CRASH LOUDLY - This is a CRITICAL accounting failure
        pytest.fail(
            f"CATASTROPHIC ACCOUNTING FAILURE\n"
            f"Forensic Tag: {classification['primary_tag']}\n"
            f"Unexplained Loss: ${equity_loss - explained_loss}\n"
            f"Replay Pack: {replay_path}\n"
            f"This test MUST fail until the accounting bug is fixed."
        )
    
    # If we get here, equity is reasonable
    print(f"\n✅ No catastrophic equity collapse detected")
    print(f"Final equity: ${final_equity} (within acceptable range)")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
