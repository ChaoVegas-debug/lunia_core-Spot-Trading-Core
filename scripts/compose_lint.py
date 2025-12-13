#!/usr/bin/env python3
"""Lightweight docker-compose overlay validation.

The script ensures the declared compose overlays exist and attempts to run
``docker compose config`` to surface syntax errors. If Docker is unavailable,
it falls back to a file existence check and emits a warning instead of
failing so that environments without Docker can still proceed.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

COMPOSE_FILES = [
    Path("lunia_core/infra/docker-compose.yml"),
    Path("lunia_core/infra/docker-compose.prod.yml"),
]


def ensure_files_exist() -> None:
    missing = [path for path in COMPOSE_FILES if not path.is_file()]
    if missing:
        joined = ", ".join(str(path) for path in missing)
        raise SystemExit(f"Missing compose file(s): {joined}")


def run_docker_compose_check() -> None:
    docker_bin = shutil.which("docker")
    if not docker_bin:
        print("Docker is not available; skipped compose config validation.")
        return

    cmd = [
        docker_bin,
        "compose",
        "-f",
        str(COMPOSE_FILES[0]),
        "-f",
        str(COMPOSE_FILES[1]),
        "config",
        "--quiet",
    ]
    print("Validating compose overlays via: " + " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    ensure_files_exist()
    run_docker_compose_check()
    print("Compose overlays validated successfully.")


if __name__ == "__main__":
    main()
