import os
import subprocess
import sys

# Разрешаем переопределить интерпретатор через $PYTHON, иначе берём текущий
PYTHON = os.environ.get("PYTHON", sys.executable or "python3")


def test_health_scripts_smoke_offline():
    """
    OFFLINE-дружелюбный смок-тест: запускаем health-скрипты с OFFLINE_CI=1,
    чтобы проверки Redis/RabbitMQ проходили без поднятой инфраструктуры.
    """
    env = os.environ.copy()
    env["OFFLINE_CI"] = "1"

    assert subprocess.call([PYTHON, "scripts/health/redis_check.py"], env=env) == 0
    assert subprocess.call([PYTHON, "scripts/health/rabbitmq_check.py"], env=env) == 0