"""Alembic environment.

The database URL comes from application settings (RENTAL_DB_* environment
variables / .env), or from the ALEMBIC_DB_URL environment variable when set
(used by tests to target rental_test). Only the application's five schemas are
managed; PostGIS-internal schemas/tables are ignored.
"""

import os

from alembic import context
from geoalchemy2 import alembic_helpers
from sqlalchemy import create_engine

from rental_agent.config.settings import load_settings
from rental_agent.db import models  # noqa: F401  (registers all tables)
from rental_agent.db.base import SCHEMAS, Base

target_metadata = Base.metadata

MANAGED_SCHEMAS = set(SCHEMAS)


def _db_url() -> str:
    return os.environ.get("ALEMBIC_DB_URL") or load_settings().db.url


def include_name(name, type_, parent_names):
    if type_ == "schema":
        return name in MANAGED_SCHEMAS
    return True


def include_object(obj, name, type_, reflected, compare_to):
    # Enum CHECK constraints (named *_enum) are owned by the SQLAlchemy Enum
    # types; Postgres rewrites their SQL on reflection so autogenerate would
    # emit spurious drops. Enum-value changes are hand-written migrations.
    if type_ == "check_constraint" and name is not None and str(name).endswith("_enum"):
        return False
    # geoalchemy2 helper suppresses duplicate spatial-index operations and
    # PostGIS-internal objects.
    return alembic_helpers.include_object(obj, name, type_, reflected, compare_to)


def run_migrations_offline() -> None:
    context.configure(
        url=_db_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
        include_name=include_name,
        include_object=include_object,
        process_revision_directives=alembic_helpers.writer,
        render_item=alembic_helpers.render_item,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_db_url())
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=include_name,
            include_object=include_object,
            process_revision_directives=alembic_helpers.writer,
            render_item=alembic_helpers.render_item,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
