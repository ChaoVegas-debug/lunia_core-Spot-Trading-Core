#!/usr/bin/env python3
import os
import subprocess
import sys

# Выбираем интерпретатор: $PYTHON -> текущий sys.executable -> "python3"
PYTHON = os.environ.get("PYTHON") or sys.executable or "python3"

CHECKS = [
    [PYTHON, "scripts/health/redis_check.py"],
    [PYTHON, "scripts/health/rabbitmq_check.py"],
]


def main() -> None:
    success = True
    for cmd in CHECKS:
        exit_code = subprocess.call(cmd)
        success = success and (exit_code == 0)

    if success:
        print("✅ All infra checks passed.")
        sys.exit(0)
    else:
        print("⚠️ Some services unavailable.")
        sys.exit(1)


if __name__ == "__main__":
    main()