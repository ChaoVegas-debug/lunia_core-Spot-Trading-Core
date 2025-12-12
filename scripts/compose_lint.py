import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

def _ensure_pyyaml() -> None:
    try:
        import yaml  # type: ignore
        return
    except ImportError:
        pass

    wheelhouse = Path(
        os.getenv(
            "WHEELHOUSE_DIR",
            Path(__file__).resolve().parent.parent / "wheelhouse",
        )
    )
    hint = (
        "PyYAML is required for compose linting. "
        "Install with: pip install --no-index --find-links wheelhouse pyyaml\n"
        "(build wheels first via: make wheelhouse).\n"
    )

    wheel_present = wheelhouse.exists() and any(
        p.name.lower().startswith("pyyaml-") for p in wheelhouse.glob("*.whl")
    )
    if not wheel_present:
        sys.stderr.write(
            f"PyYAML wheel not found in {wheelhouse}. Run make wheelhouse first.\n{hint}"
        )
        raise SystemExit(1)

    try:
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-index",
                "--find-links",
                str(wheelhouse),
                "pyyaml",
            ]
        )
    except Exception as exc:  # pragma: no cover - pip failures are surfaced to the user
        sys.stderr.write(f"Failed to auto-install PyYAML from wheelhouse: {exc}\n{hint}")
        raise SystemExit(1)


_ensure_pyyaml()
import yaml  # type: ignore  # noqa: E402

BASE_PATH = Path(__file__).resolve().parent.parent / "lunia_core" / "infra"
BASE_COMPOSE = BASE_PATH / "docker-compose.yml"
PROD_COMPOSE = BASE_PATH / "docker-compose.prod.yml"


def load_yaml(path: Path) -> Dict:
    if not path.exists():
        raise FileNotFoundError(f"Compose file not found: {path}")
    with path.open("r", encoding="utf-8") as fp:
        return yaml.safe_load(fp)


def ensure_no_host_ports(service: Dict, name: str, errors: List[str]):
    ports = service.get("ports")
    if ports not in (None, []):
        errors.append(f"[{name}] must not expose host ports in prod overlay")


def ensure_healthcheck(service: Dict, name: str, errors: List[str]):
    if "healthcheck" not in service:
        errors.append(f"[{name}] missing healthcheck definition")


def ensure_traefik_volume(service: Dict, errors: List[str]):
    volumes = service.get("volumes") or []
    has_acme = any("/letsencrypt" in v for v in volumes)
    if not has_acme:
        errors.append("[traefik] missing ACME storage volume mapping")


def ensure_monitoring_profiles(compose: Dict, errors: List[str]):
    monitoring = [
        name
        for name, svc in (compose.get("services") or {}).items()
        if "profiles" in svc and "monitoring" in svc["profiles"]
    ]
    required = {"prometheus", "grafana", "node-exporter"}
    missing = sorted(required.difference(monitoring))
    if missing:
        errors.append(f"Monitoring services missing profile tag: {', '.join(missing)}")


def main() -> int:
    errors: List[str] = []

    base = load_yaml(BASE_COMPOSE)
    prod = load_yaml(PROD_COMPOSE)

    prod_services = prod.get("services") or {}
    base_services = base.get("services") or {}

    # Healthchecks on required services in base
    for svc_name in ("api", "redis"):
        if svc_name not in base_services:
            errors.append(f"[{svc_name}] service missing in base compose")
            continue
        ensure_healthcheck(base_services[svc_name], svc_name, errors)

    # Prod overlay must not expose app/api ports directly
    for svc_name in ("api", "frontend"):
        if svc_name not in prod_services:
            errors.append(f"[{svc_name}] service missing in prod overlay")
            continue
        ensure_no_host_ports(prod_services[svc_name], svc_name, errors)

    # Traefik checks
    traefik = prod_services.get("traefik")
    if not traefik:
        errors.append("[traefik] service missing in prod overlay")
    else:
        ensure_traefik_volume(traefik, errors)
        ensure_healthcheck(traefik, "traefik", errors)

    # Monitoring profile tagging
    ensure_monitoring_profiles(base, errors)

    if errors:
        sys.stderr.write("Compose lint failed:\n")
        for err in errors:
            sys.stderr.write(f" - {err}\n")
        return 1

    print("Compose lint passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
