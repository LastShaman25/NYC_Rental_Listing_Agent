"""Source-observation persistence with idempotent insert (PR-ACQ-002)."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from rental_agent.contracts import enums as e
from rental_agent.contracts.observation import ParsedSourceObservation
from rental_agent.db.models import SourceObservation


class ObservationRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def insert_idempotent(
        self,
        observation: ParsedSourceObservation,
        *,
        source_id: uuid.UUID,
        source_run_id: uuid.UUID,
        content_hash: str,
        parse_status: e.ParseStatus,
        raw_payload_ref: str | None = None,
    ) -> uuid.UUID | None:
        """Insert an observation; returns its id, or None when the identical
        observation (idempotency key) already exists. Reprocessing identical
        input must create no duplicate effects (02 §6.4)."""
        stmt = (
            pg_insert(SourceObservation)
            .values(
                source_id=source_id,
                source_run_id=source_run_id,
                source_native_id=observation.source_native_id,
                source_url=observation.source_url,
                observed_at=observation.observed_at,
                retrieved_at=observation.retrieved_at,
                content_hash=content_hash,
                raw_payload_ref=raw_payload_ref,
                parsed_payload=observation.model_dump(mode="json"),
                parse_status=parse_status.value,
                contact_redaction_status=observation.description.redaction_status.value,
                adapter_version=observation.extraction.adapter_version,
                schema_version=observation.schema_version,
            )
            .on_conflict_do_nothing()
            .returning(SourceObservation.source_observation_id)
        )
        return self._s.execute(stmt).scalar_one_or_none()

    def latest_for_identity(
        self, source_id: uuid.UUID, source_native_id: str
    ) -> SourceObservation | None:
        stmt = (
            select(SourceObservation)
            .where(
                SourceObservation.source_id == source_id,
                SourceObservation.source_native_id == source_native_id,
            )
            .order_by(SourceObservation.observed_at.desc())
            .limit(1)
        )
        return self._s.execute(stmt).scalar_one_or_none()

    def count_between(self, source_id: uuid.UUID, start: datetime, end: datetime) -> int:
        stmt = select(SourceObservation).where(
            SourceObservation.source_id == source_id,
            SourceObservation.observed_at >= start,
            SourceObservation.observed_at < end,
        )
        return len(self._s.execute(stmt).scalars().all())
