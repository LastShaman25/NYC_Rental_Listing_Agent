"""Engine and session factories.

External network/LLM/media calls must never run inside an open transaction
(06 §13.3); services persist intent, call outside, then commit results in a new
short transaction. Sessions here default to explicit, short-lived use.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from rental_agent.config.settings import Settings


def build_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.db.url,
        pool_size=settings.db.pool_size,
        pool_pre_ping=True,
        echo=settings.db.echo,
    )


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
