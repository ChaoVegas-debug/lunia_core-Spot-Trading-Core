from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "lunia_core"
sys.path.append(str(ROOT))

from app.services.auth.database import Base, engine, get_session  # type: ignore  # noqa: E402
from app.services.auth.models import AuditEvent, FeatureFlag, Limit, User  # type: ignore  # noqa: E402
from app.services.auth.tenants import ensure_default_tenants  # type: ignore  # noqa: E402
from app.services.auth.users import ensure_seed_admin  # type: ignore  # noqa: E402


def main() -> None:
    Base.metadata.create_all(bind=engine)
    session = get_session()
    default, demo = ensure_default_tenants(session)
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    ensure_seed_admin(session, email=admin_email, password=admin_password, tenant=default)
    # create a demo user for the demo tenant to aid UI verification
    ensure_seed_admin(session, email="demo-admin@example.com", password="demo-admin", tenant=demo)
    session.close()


if __name__ == "__main__":
    main()
