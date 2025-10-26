#!/usr/bin/env python3
import os
import subprocess
import sys

PYTHON = os.environ.get("PYTHON", "python3")
CHECKS = [
    [PYTHON, "scripts/health/redis_check.py"],
    [PYTHON, "scripts/health/rabbitmq_check.py"],
]

success = True
for command in CHECKS:
    exit_code = subprocess.call(command)
    success = success and (exit_code == 0)

if success:
    print("✅ All infra checks passed.")
    sys.exit(0)

print("⚠️ Some services unavailable.")
sys.exit(1)
