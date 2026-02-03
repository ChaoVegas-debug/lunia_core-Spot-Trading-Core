
import os
from pathlib import Path

# Base Directory: lunia_core (parent of app)
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = BASE_DIR.parent / "data" # /Users/.../lunia_core-Spot-Trading-Core/data
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR = DATA_DIR

# Secrets
SECRETS_FILE = LOG_DIR.parent / ".secrets.json"
