import os
import subprocess


def test_health_scripts_smoke() -> None:
    python_executable = os.environ.get("PYTHON", "python3")
    subprocess.call([python_executable, "scripts/health/redis_check.py"])
    subprocess.call([python_executable, "scripts/health/rabbitmq_check.py"])
