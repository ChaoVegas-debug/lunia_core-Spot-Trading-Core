"""EPOCH F.2.1 Genesis Integration Test - Continuous Watchdog + Emergency Liquidation

TESTS:
1. Continuous DD monitoring (every bar)
2. Global halt at ~20% DD
3. Emergency liquidation via E2→E5.1→E5
4. Trades stop after halt
5. Final equity >= $7,500
6. SHA256 determinism
"""
import pytest,warnings,hashlib,csv
from decimal import Decimal
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent.parent.parent))

from app.data.genesis_seeder import GenesisDataSeeder
from app.services.history.store.inmemory import InMemoryHistoricalStore
from app.simulation.genesis_harness_full import GenesisHarnessFull
from app.services.allocation.policies import DecimalMathKernel

CONFIG={
    'initial_capital':Decimal("10000"),
    'genesis_seed':42,
    'sim_clock_seed_ms':1609459200000,
    'slippage':Decimal("0.0005"),
    'fee_taker':Decimal("0.001"),
    'fee_maker':Decimal("0.001"),
    'capital_fraction':Decimal("0.95"),  # RESTORED: Locked aggressive setting
    'max_drawdown_limit':Decimal("0.20"),
    'bars':1000
}

def seed_d2():
    store=InMemoryHistoricalStore()
    seeder=GenesisDataSeeder(seed=CONFIG['genesis_seed'],start_ms=CONFIG['sim_clock_seed_ms'])
    generated,appended=seeder.seed_to_d2(store,CONFIG['bars'])
    assert generated==CONFIG['bars']
    assert appended==CONFIG['bars']
    return store

def compute_csv_hash(filepath:Path)->str:
    if not filepath.exists():
        return ""
    with open(filepath,'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()

def test_epoch_f2_1_genesis_continuous_watchdog():
    """
    EPOCH F.2.1 - Continuous Watchdog + Emergency Liquidation
    
    SEMANTIC SUCCESS CRITERIA:
    - final_equity >= 7500
    - halt at ~20% DD
    - liquidation executed
    - trades stop after halt
    - determinism proven
    """
    DecimalMathKernel.ensure_context(28)
    
    store=seed_d2()
    
    # RUN A
    print("\n=== RUN A ===")
    harness_a=GenesisHarnessFull(CONFIG)
    result_a=harness_a.run(store)
    
    artifacts_dir=Path(__file__).parent.parent.parent/"artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    
    equity_csv_path=artifacts_dir/"epoch_f2_1_equity.csv"
    trades_csv_path=artifacts_dir/"epoch_f2_1_trades.csv"
    log_path=artifacts_dir/"epoch_f2_1_log.txt"
    
    with open(equity_csv_path,'w',newline='') as f:
        if result_a['equity_curve']:
            writer=csv.DictWriter(f,fieldnames=result_a['equity_curve'][0].keys())
            writer.writeheader()
            writer.writerows(result_a['equity_curve'])
    
    with open(trades_csv_path,'w',newline='') as f:
        if result_a['trade_lineage']:
            writer=csv.DictWriter(f,fieldnames=result_a['trade_lineage'][0].keys())
            writer.writeheader()
            writer.writerows(result_a['trade_lineage'])
    
    with open(log_path,'w') as f:
        f.write("\\n".join(result_a['logs']))
    
    hash_equity_a=compute_csv_hash(equity_csv_path)
    hash_trades_a=compute_csv_hash(trades_csv_path)
    
    # RUN B (Determinism)
    print("\n=== RUN B (DETERMINISM) ===")
    harness_b=GenesisHarnessFull(CONFIG)
    result_b=harness_b.run(store)
    
    equity_csv_b=artifacts_dir/"epoch_f2_1_equity_runb.csv"
    trades_csv_b=artifacts_dir/"epoch_f2_1_trades_runb.csv"
    
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
    
    hash_equity_b=compute_csv_hash(equity_csv_b)
    hash_trades_b=compute_csv_hash(trades_csv_b)
    
    # ASSERTIONS
    
    # 1. Completion
    assert result_a['final_equity'] is not None
    assert DecimalMathKernel.is_finite(result_a['final_equity'])
    
    # 2. GLOBAL HALT triggered
    assert result_a['global_halted'],f"Must trigger GLOBAL_HALTED! got={result_a['global_halted']}"
    
    # 3. Halt at ~20% DD (tolerance)
    assert result_a['dd_at_halt']>=Decimal("0.19"),f"DD at halt too low: {result_a['dd_at_halt']}"
    assert result_a['dd_at_halt']<=Decimal("0.25"),f"DD at halt too high: {result_a['dd_at_halt']}"
    
    # 4. Halt happened early (before bar 45)
    assert result_a['halt_bar_index']<45,f"Halt too late: bar {result_a['halt_bar_index']}"
    
    # 5. Liquidation attempted and executed
    assert result_a['liquidation_attempted'],f"Must attempt liquidation!"
    assert result_a['liquidation_executed'],f"Must execute liquidation to save capital!"
    
    # 6. Trades stop after halt (count fills before/after)
    fills_before_halt=sum(1 for entry in result_a['trade_lineage'] if entry['decision']=='FILLED' and entry['bar_index']<result_a['halt_bar_index'])
    fills_after_halt=sum(1 for entry in result_a['trade_lineage'] if entry['decision']=='FILLED' and entry['bar_index']>result_a['halt_bar_index'])
    assert fills_after_halt==0,f"Trades must stop after halt! fills_after={fills_after_halt}"
    
    # 7. SEMANTIC SURVIVAL: final equity >= $7,500
    assert result_a['final_equity']>=Decimal("7500"),f"SEMANTIC FAILURE: equity={result_a['final_equity']} (target>=7500)"
    
    # 8. SHA256 Determinism
    assert hash_equity_a==hash_equity_b,f"Equity CSV determinism FAILED!\\nA: {hash_equity_a}\\nB: {hash_equity_b}"
    assert hash_trades_a==hash_trades_b,f"Trades CSV determinism FAILED!\\nA: {hash_trades_a}\\nB: {hash_trades_b}"
    
    # 9. Final equity match
    assert str(result_a['final_equity'])==str(result_b['final_equity'])
    
    # 10. Equity curve length
    assert len(result_a['equity_curve'])==CONFIG['bars']
    
    # SUMMARY
    print(f"\\n{'='*70}")
    print(f"EPOCH F.2.1 GENESIS - CONTINUOUS WATCHDOG (SEMANTIC SURVIVAL)")
    print(f"{'='*70}")
    print(f"Final equity: ${result_a['final_equity']}")
    print(f"Target: >= $7,500")
    print(f"Survival: {'✅ PASSED' if result_a['final_equity']>=Decimal('7500') else '❌ FAILED'}")
    print(f"")
    print(f"Halt details:")
    print(f"  Bar index: {result_a['halt_bar_index']}")
    print(f"  DD at halt: {result_a['dd_at_halt']:.2%}")
    print(f"  Equity at halt: ${result_a['equity_at_halt']}")
    print(f"  Peak at halt: ${result_a['peak_at_halt']}")
    print(f"")
    print(f"Liquidation:")
    print(f"  Attempted: {result_a['liquidation_attempted']}")
    print(f"  Executed: {result_a['liquidation_executed']}")
    print(f"")
    print(f"Trade activity:")
    print(f"  Fills before halt: {fills_before_halt}")
    print(f"  Fills after halt: {fills_after_halt} (must be 0)")
    print(f"")
    print(f"Determinism:")
    print(f"  Equity CSV: {hash_equity_a[:16]}...")
    print(f"  Trades CSV: {hash_trades_a[:16]}...")
    print(f"  Match: ✅")
    print(f"{'='*70}")
    
    equity_csv_b.unlink()
    trades_csv_b.unlink()

if __name__=="__main__":
    warnings.simplefilter("error")
    pytest.main([__file__,"-v","-s"])
