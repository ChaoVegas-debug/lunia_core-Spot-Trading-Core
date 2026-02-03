
import json
import sys
from pathlib import Path

# Paths
ROOT_DIR = Path.cwd()
SECRETS_FILE = ROOT_DIR / ".secrets.json"

# Credentials from Engineer (Masked in Logs, Plain in File)
# API: ckPpwSL8I7dnUTJcwUDEcVIXzKbrVOTqHmv7TLYTG8qY3vSV3HsMcJvEE52IEN9v
# SECRET: IuPnzSGcia743emsE06kx5MspuZcFybPaVwxTceYJCmOd9aRnAYFBSwBrClUsyDI

def inject_keys():
    print(f"[INJECTOR] Writing to {SECRETS_FILE}")
    
    # Load existing or create new
    if SECRETS_FILE.exists():
        try:
            data = json.loads(SECRETS_FILE.read_text())
        except:
            data = {}
    else:
        data = {}

    # Update Binance
    data["binance"] = {
        "api_key": "pOeBUvoqG0wt4c1NmGPcPeXCqCgxim1VYA3bZEvcszvqH6RkVK6bhWEefyD7MlDB",
        "api_secret": "QIWUMB69qABsvPv2PnYAtksIMXUJO7zWKMjGcZJljIOrw8lBZUYIo8wEFZRR6SVX",
        "is_testnet": False # LIVE
    }

    # Write Atomic
    SECRETS_FILE.write_text(json.dumps(data, indent=2))
    print("[INJECTOR] SUCCESS. Keys written.")
    print(f"[INJECTOR] Target: {data['binance']['api_key'][:10]}... (Mainnet=True)")

if __name__ == "__main__":
    inject_keys()
