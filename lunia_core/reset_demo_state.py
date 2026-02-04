
import logging
from lunia_core.app.core.state import reset_state

logging.basicConfig(level=logging.INFO)
print("Resetting system state to defaults...")
state = reset_state()
print("State reset complete.")
print(f"Portfolios: {len(state.get('portfolios', {}).get('definitions', {}))}")
print(f"System Mode: {state.get('system_mode')}")
print(f"Risk Profile: {state.get('strategies', {}).get('active_profile')}")
