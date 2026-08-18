"""Declarative base, naming conventions, and shared column helpers.

Physical layout follows 06 §5.2 schema namespaces: app, ops, raw, config, audit.
Enums are stored as constrained text (CHECK constraints), never native PostgreSQL
enums, so value sets evolve through ordinary migrations (02 §5.2).
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import Enum as SAEnum
from sqlalchemy import MetaData, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime, Text

SCHEMAS = ("app", "ops", "raw", "config", "audit")

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {
        dict[str, Any]: JSONB,
        datetime: DateTime(timezone=True),
        str: Text,
    }


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


def enum_text(enum_cls: type[StrEnum], name: str, **kw: Any) -> Mapped[str]:
    """Constrained-text enum column: VARCHAR + named CHECK constraint.

    native_enum=False keeps value sets migration-evolvable (02 §5.2);
    validate_strings raises on invalid values before they reach the database.
    """
    return mapped_column(
        SAEnum(
            enum_cls,
            name=f"{name}_enum",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda cls: [m.value for m in cls],
            length=64,
        ),
        **kw,
    )


def created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def updated_at() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
