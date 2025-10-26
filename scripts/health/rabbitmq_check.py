#!/usr/bin/env python3
import socket
import sys

try:
    sock = socket.create_connection(("localhost", 5672), timeout=1.5)
    sock.close()
    print("✅ RabbitMQ alive")
    sys.exit(0)
except Exception as exc:  # noqa: BLE001
    print(f"⚠️ RabbitMQ unreachable: {exc}")
    sys.exit(1)
