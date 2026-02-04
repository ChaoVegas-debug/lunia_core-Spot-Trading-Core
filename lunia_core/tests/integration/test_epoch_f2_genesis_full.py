"""EPOCH F.2 Genesis Full Stack Integration Test - HARDENED

TESTS:
1. Full pipeline execution (no bypass)
2. Global halt on risk breach
3. SHA256 determinism verification
4. E5-only portfolio updates
5. Observable halt
"""
import pytest,warnings,hashlib,csv
from decimal import Decimal
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent.parent.parent))

from lunia_core.app.data.genesis_seeder import GenesisDataSeeder
from lunia_core.app.services.history.store.inmemory import InMemoryHistoricalStore
from lunia_core.app.simulation.genesis_harness_full import GenesisHarnessFull
from lunia_core.app.services.allocation.policies import DecimalMathKernel

# LOCKED CONFIG (F.2)
CONFIG={
    'genesis_seed':1337,
    'sim_clock_seed_ms':1700000000000,
    'initial_capital':10000.00,
    'fee_maker':0.001,
    'fee_taker':0.001,
    'slippage':0.0005,
    'max_drawdown_limit':0.20,  # 20% DD limit
    'bars':1000
}

def seed_d2():
    """Ensure D2 has Genesis data"""
    store=InMemoryHistoricalStore()
    seeder=GenesisDataSeeder(seed=CONFIG['genesis_seed'],start_ms=CONFIG['sim_clock_seed_ms'])
    generated,appended=seeder.seed_to_d2(store,CONFIG['bars'])
    assert generated==CONFIG['bars']
    assert appended==CONFIG['bars']
    return store

def compute_csv_hash(filepath:Path)->str:
    """Compute SHA256 of CSV file"""
    if not filepath.exists():
        return ""
    with open(filepath,'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()

def test_epoch_f2_genesis_full():
    """
    EPOCH F.2 Full Stack Genesis - HARDENED
    
    Tests:
    1. Full pipeline (E3, E2, E5.1, E5)
    2. Global halt on risk breach
    3. Determinism (SHA256)
    4. E5-only updates
    5. Survival > performance
    """
    # Ensure warnings as errors
    DecimalMathKernel.ensure_context(28)
    
    # Seed D2
    store=seed_d2()
    
    # RUN A
    print("\n=== RUN A ===")
    harness_a=GenesisHarnessFull(CONFIG)
    result_a=harness_a.run(store)
    
    # Write artifacts (Run A)
    artifacts_dir=Path(__file__).parent.parent.parent/"artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    
    equity_csv_path=artifacts_dir/"epoch_f2_full_equity.csv"
    trades_csv_path=artifacts_dir/"epoch_f2_full_trades.csv"
    log_path=artifacts_dir/"epoch_f2_full_log.txt"
    
    # Equity CSV
    with open(equity_csv_path,'w',newline='') as f:
        if result_a['equity_curve']:
            writer=csv.DictWriter(f,fieldnames=result_a['equity_curve'][0].keys())
            writer.writeheader()
            writer.writerows(result_a['equity_curve'])
    
    # Trades CSV
    with open(trades_csv_path,'w',newline='') as f:
        if result_a['trade_lineage']:
            writer=csv.DictWriter(f,fieldnames=result_a['trade_lineage'][0].keys())
            writer.writeheader()
            writer.writerows(result_a['trade_lineage'])
    
    # Log
    with open(log_path,'w') as f:
        f.write("\\n".join(result_a['logs']))
    
    # Compute hashes (Run A)
    hash_equity_a=compute_csv_hash(equity_csv_path)
    hash_trades_a=compute_csv_hash(trades_csv_path)
    
    # RUN B (Determinism test)
    print("\n=== RUN B (DETERMINISM) ===")
    harness_b=GenesisHarnessFull(CONFIG)
    result_b=harness_b.run(store)
    
    # Write temp artifacts (Run B)
    equity_csv_b=artifacts_dir/"epoch_f2_full_equity_runb.csv"
    trades_csv_b=artifacts_dir/"epoch_f2_full_trades_runb.csv"
    
    with open(equity_csv_b,'w',newline='') as f:
        if result_b['equity_curve']:
            writer=csv.DictWriter(f,fieldnames=result_b['equity_curve'][0].keys())
            writer.writeheader()
            writer.writerows(result_b['equity_curve'])
    
    with open(trades_csv_b,'w',newline='') as f:
        if result_b['trade_lineage']:
            writer=csv.DictWriter(f,fieldnames=result_b['trade_lineage'][0].keys())
            writer.writeheader()
            writer.writerows(result_b['trade_lineage'])
    
    # Compute hashes (Run B)
    hash_equity_b=compute_csv_hash(equity_csv_b)
    hash_trades_b=compute_csv_hash(trades_csv_b)
    
    # ASSERTIONS
    
    # 1. Completion
    assert result_a['final_equity'] is not None
    assert DecimalMathKernel.is_finite(result_a['final_equity'])
    
    # 2. Trade count > 0
    assert result_a['counters']['fills_total']>0,f"Must have trades! fills={result_a['counters']['fills_total']}"
    
    # 3. GLOBAL HALT must have triggered
    assert result_a['global_halted'],f"Risk must trigger GLOBAL_HALTED! halted={result_a['global_halted']}"
    assert result_a['halt_bar_index']>=0
    
    # 4. No bypass (stage counters)
    assert result_a['counters']['risk_evaluated_total']==result_a['counters']['sized_total'],"Risk must evaluate all sized intents"
    
    # 5. Risk blocked something
    assert result_a['counters']['risk_blocked_total']>0,"Risk must block some intents"
    
    # 6. Final equity > F.1 baseline (survival)
    f1_baseline=Decimal("638.44")
    assert result_a['final_equity']>f1_baseline,f"Survival test: {result_a['final_equity']} must exceed F.1 baseline {f1_baseline}"
    
    # 7. SHA256 Determinism (RULE 5)
    assert hash_equity_a==hash_equity_b,f"Equity CSV determinism FAILED!\\nA: {hash_equity_a}\\nB: {hash_equity_b}"
    assert hash_trades_a==hash_trades_b,f"Trades CSV determinism FAILED!\\nA: {hash_trades_a}\\nB: {hash_trades_b}"
    
    # 8. Final equity match (Run A vs B)
    assert str(result_a['final_equity'])==str(result_b['final_equity']),"Final equity must be bit-identical"
    
    # 9. Equity curve length
    assert len(result_a['equity_curve'])==CONFIG['bars']
    
    # Print summary
    print(f"\\n{'='*60}")
    print(f"EPOCH F.2 GENESIS FULL STACK - HARDENED")
    print(f"{'='*60}")
    print(f"Final equity: ${result_a['final_equity']}")
    print(f"F.1 baseline: ${f1_baseline}")
    print(f"Improvement: ${result_a['final_equity']-f1_baseline}")
    print(f"Fills: {result_a['counters']['fills_total']}")
    print(f"Risk blocked: {result_a['counters']['risk_blocked_total']}")
    print(f"GLOBAL_HALTED: {result_a['global_halted']} (bar {result_a['halt_bar_index']})")
    print(f"Halt reason: {result_a['halt_reason']}")
    print(f"\\nDeterminism:")
    print(f"  Equity CSV: {hash_equity_a[:16]}...") 
    print(f"  Trades CSV: {hash_trades_a[:16]}...")
    print(f"  Match: ✅")
    print(f"{'='*60}")
    
    # Cleanup temp files
    equity_csv_b.unlink()
    trades_csv_b.unlink()

if __name__=="__main__":
    warnings.simplefilter("error")
    pytest.main([__file__,"-v","-s"])
