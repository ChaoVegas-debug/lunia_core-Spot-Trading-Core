#!/usr/bin/env python3
import os
import socket
import sys

OFFLINE = os.environ.get("OFFLINE_CI") == "1"
HOST = os.environ.get("RABBITMQ_HOST", "localhost")
PORT = 5672

if OFFLINE:
    print("⚠️ RabbitMQ check skipped (OFFLINE_CI=1)")
    sys.exit(0)

try:
    sock = socket.create_connection((HOST, PORT), timeout=1.5)
    sock.close()
    print("✅ RabbitMQ alive")
except Exception as e:
    print(f"❌ RabbitMQ unreachable: {e}")
    sys.exit(1)