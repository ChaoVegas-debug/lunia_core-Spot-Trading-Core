from __future__ import annotations

import os
from typing import Optional

from sqlalchemy.orm import Session

from .models import FeatureFlag, Limit, Tenant, TenantDomain

DEFAULT_TENANT_SLUG = os.getenv("DEFAULT_TENANT_SLUG", "default")


def get_tenant_by_slug(session: Session, slug: str) -> Optional[Tenant]:
    return session.query(Tenant).filter(Tenant.slug == slug).one_or_none()


def get_tenant_by_domain(session: Session, domain: str) -> Optional[Tenant]:
    return (
        session.query(Tenant)
        .join(TenantDomain)
        .filter(TenantDomain.domain == domain)
        .one_or_none()
    )


def ensure_tenant(
    session: Session,
    *,
    slug: str,
    name: Optional[str] = None,
    status: str = "active",
    app_name: Optional[str] = None,
    logo_url: Optional[str] = None,
    primary_color: Optional[str] = None,
    support_email: Optional[str] = None,
    environment: Optional[str] = None,
) -> Tenant:
    tenant = get_tenant_by_slug(session, slug)
    if tenant:
        return tenant
    tenant = Tenant(
        slug=slug,
        name=name or slug,
        status=status,
        app_name=app_name,
        logo_url=logo_url,
        primary_color=primary_color,
        support_email=support_email,
        environment=environment,
    )
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    return tenant


def ensure_default_tenants(session: Session) -> tuple[Tenant, Tenant]:
    default = ensure_tenant(
        session,
        slug=DEFAULT_TENANT_SLUG,
        name=os.getenv("BRAND_NAME", "Lunia"),
        app_name=os.getenv("BRAND_NAME", "Lunia"),
        logo_url=os.getenv("BRAND_LOGO_URL"),
        primary_color=os.getenv("BRAND_PRIMARY_COLOR"),
        support_email=os.getenv("BRAND_SUPPORT_EMAIL"),
        environment=os.getenv("BRAND_ENVIRONMENT", "prod"),
    )
    demo = ensure_tenant(session, slug="demo", name="Demo Tenant", app_name="Lunia Demo")
    return default, demo


def list_tenants(session: Session) -> list[Tenant]:
    return session.query(Tenant).order_by(Tenant.created_at.desc()).all()


def update_tenant(session: Session, tenant: Tenant, **kwargs) -> Tenant:
    for field, value in kwargs.items():
        if hasattr(tenant, field) and value is not None:
            setattr(tenant, field, value)
    session.commit()
    session.refresh(tenant)
    return tenant


def upsert_domains(session: Session, tenant: Tenant, domains: list[str]) -> Tenant:
    existing = {d.domain: d for d in tenant.domains}
    keep = set(domains)
    for domain in domains:
        if domain not in existing:
            session.add(TenantDomain(tenant_id=tenant.id, domain=domain))
    for domain, record in existing.items():
        if domain not in keep:
            session.delete(record)
    session.commit()
    session.refresh(tenant)
    return tenant


def tenant_limits(session: Session, tenant: Tenant) -> list[Limit]:
    return (
        session.query(Limit)
        .filter(Limit.scope == "tenant", Limit.subject == tenant.slug)
        .order_by(Limit.updated_at.desc())
        .all()
    )


def upsert_tenant_limits(session: Session, tenant: Tenant, limits: list[dict]) -> list[Limit]:
    results: list[Limit] = []
    for item in limits:
        key = str(item.get("key", "")).strip()
        if not key:
            continue
        value = str(item.get("value", ""))
        record = (
            session.query(Limit)
            .filter(Limit.scope == "tenant", Limit.subject == tenant.slug, Limit.key == key)
            .one_or_none()
        )
        if record:
            record.value = value
        else:
            record = Limit(scope="tenant", subject=tenant.slug, key=key, value=value)
            session.add(record)
        results.append(record)
    session.commit()
    for record in results:
        session.refresh(record)
    return results


def apply_tenant_feature_overrides(session: Session, tenant: Tenant) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for flag in session.query(FeatureFlag).filter(FeatureFlag.key.startswith(f"{tenant.slug}:")).all():
        overrides[flag.key] = flag.value
    return overrides


def resolve_tenant_from_request(session: Session, host: str, header_tenant: str | None) -> Tenant:
    if header_tenant:
        tenant = get_tenant_by_slug(session, header_tenant)
        if tenant:
            return tenant
    if host:
        tenant = get_tenant_by_domain(session, host)
        if tenant:
            return tenant
    return ensure_tenant(session, slug=DEFAULT_TENANT_SLUG, name="Default Tenant")
