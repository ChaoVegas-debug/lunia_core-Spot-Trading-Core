"""Hot Reload Helper (PHASE 5)

Minimal helper for RiskGate to read governance state without restart.
"""
from forensic.risk.store import RiskConfigStore

# Global store instance
_governance_store: RiskConfigStore = None

def init_hot_reload_store(config_path: str = "data/risk_config.json"):
    """Initialize hot reload store."""
    global _governance_store
    _governance_store = RiskConfigStore(config_path)

def get_governance_state() -> dict:
    """Get current governance state (hot reload - always reloads from disk)."""
    if _governance_store is None:
        init_hot_reload_store()
    return _governance_store.get_current_state()
