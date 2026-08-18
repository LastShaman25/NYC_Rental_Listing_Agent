"""Register the apartments_com source (owner decision 2026-08-18). Idempotent."""

from sqlalchemy import select

from rental_agent.config.settings import load_settings
from rental_agent.db.engine import build_engine, build_session_factory
from rental_agent.db.models import Source

settings = load_settings()
factory = build_session_factory(build_engine(settings))
with factory() as session:
    existing = session.execute(
        select(Source).where(Source.source_code == "apartments_com")
    ).scalar_one_or_none()
    if existing is None:
        session.add(
            Source(
                source_code="apartments_com",
                display_name="Apartments.com",
                source_type="LISTING",
                access_method="OTHER_APPROVED",
                approval_status="APPROVED",
                enabled=True,
                policy_version="search-index-1",
            )
        )
        session.commit()
        print("apartments_com source registered")
    else:
        print("apartments_com source already registered")
