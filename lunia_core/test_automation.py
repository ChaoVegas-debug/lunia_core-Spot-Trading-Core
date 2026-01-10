import time
import logging
from app.services.scheduler.rebalancer import _check_and_trigger_rebalance
from app.core.state import get_state, set_state
from app.core.portfolio.types import PortfolioDefinition, PortfolioType, RiskProfile, PortfolioStatus, PortfolioRule
from app.services.api.flask_app import agent

# Setup Logging
logging.basicConfig(level=logging.INFO)

def test_automation():
    print("--- 1. Seeding Mock Portfolio ---")
    pid = "test_auto_portfolio"
    
    # Create Definition
    defi = PortfolioDefinition(
        id=pid,
        type=PortfolioType.TACTICAL,
        risk_profile=RiskProfile.AGGRESSIVE,
        horizon="7d",
        assets=[],
        rules=PortfolioRule(rebalance_interval_days=7),
        status=PortfolioStatus.ACTIVE
    )
    
    # Seed into State
    # Force last_rebalanced_at to be OLD (8 days ago)
    raw = defi.to_dict()
    raw["last_rebalanced_at"] = time.time() - (8 * 86400) 
    
    set_state({"portfolio": {"definitions": {pid: raw}}})
    print(f"Seeded {pid} with last_rebalanced_at = -8 days")
    
    print("--- 2. Triggering Scheduler Tick ---")
    _check_and_trigger_rebalance(agent)
    
    print("--- 3. Verifying Result ---")
    state = get_state()
    new_ts = state["portfolio"]["definitions"][pid]["last_rebalanced_at"]
    
    # If successful, ts should be ~now
    if new_ts > time.time() - 100:
        print(f"SUCCESS: Timestamp updated to {new_ts}")
    else:
        print(f"FAILURE: Timestamp mismatch (Still {new_ts})")

if __name__ == "__main__":
    try:
        test_automation()
    except Exception as e:
        print(f"Runtime Error: {e}")
