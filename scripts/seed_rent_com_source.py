"""Register the rent_com source (owner decision 2026-08-18). Idempotent."""

from sqlalchemy import select

from rental_agent.config.settings import load_settings
from rental_agent.db.engine import build_engine, build_session_factory
from rental_agent.db.models import Source

settings = load_settings()
factory = build_session_factory(build_engine(settings))
with factory() as session:
    existing = session.execute(
        select(Source).where(Source.source_code == "rent_com")
    ).scalar_one_or_none()
    if existing is None:
        session.add(
            Source(
                source_code="rent_com",
                display_name="Rent.com",
                source_type="LISTING",
                access_method="OTHER_APPROVED",
                approval_status="APPROVED",
                enabled=True,
                policy_version="search-index-1",
            )
        )
        session.commit()
        print("rent_com source registered")
    else:
        print("rent_com source already registered")
