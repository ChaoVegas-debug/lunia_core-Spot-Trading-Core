#!/usr/bin/env python3
import sys

try:
    import redis

    client = redis.Redis(host="localhost", port=6379, socket_connect_timeout=1)
    client.ping()
    print("✅ Redis alive")
    sys.exit(0)
except Exception as exc:  # noqa: BLE001
    print(f"⚠️ Redis unreachable: {exc}")
    sys.exit(1)
