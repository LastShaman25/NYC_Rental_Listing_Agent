"""Manual marketing selection and client-shortlist services.

Invariants enforced here (02 §19, 08 §16.3, PR-UI-004):
- Only a HUMAN actor may create or change selection or shortlist state; any
  SYSTEM-actor attempt raises. Automatic jobs therefore cannot select.
- Marketing selection and shortlist membership are fully independent states;
  neither service touches the other's table.
- Live filter matches are never persisted as shortlist entries; only explicit
  inclusion/exclusion by the operator creates a row.
- Every state change is audited in audit.action_log.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from rental_agent.contracts import enums as e
from rental_agent.db.models import (
    AuditActionLog,
    ClientSearchPreset,
    ClientShortlistEntry,
    MarketingSelection,
)


class HumanActionRequired(PermissionError):
    """Raised when a non-human actor attempts a human-only write."""


def _require_human(actor_type: e.ActorType) -> None:
    if actor_type is not e.ActorType.HUMAN:
        raise HumanActionRequired(
            "marketing selection and shortlist membership are manual human actions"
        )


def _now() -> datetime:
    return datetime.now(tz=UTC)


class MarketingSelectionService:
    def __init__(self, session: Session) -> None:
        self._s = session

    def set_selection(
        self,
        *,
        canonical_listing_id: uuid.UUID,
        status: e.SelectionStatus,
        actor: str,
        actor_type: e.ActorType,
        note: str | None = None,
    ) -> MarketingSelection:
        _require_human(actor_type)
        now = _now()
        current = self._s.execute(
            select(MarketingSelection).where(
                MarketingSelection.canonical_listing_id == canonical_listing_id
            )
        ).scalar_one_or_none()
        before = None if current is None else {"selection_status": current.selection_status}
        if current is None:
            current = MarketingSelection(
                canonical_listing_id=canonical_listing_id,
                selection_status=status.value,
                selected_by=actor,
                selected_at=now,
                note=note,
            )
            self._s.add(current)
        else:
            current.selection_status = status.value
            current.selected_by = actor
            current.selected_at = now
            if note is not None:
                current.note = note
        self._s.add(
            AuditActionLog(
                actor=actor,
                actor_type=actor_type.value,
                action_type="marketing_selection_change",
                target_type="canonical_listing",
                target_id=canonical_listing_id,
                before_values=before,
                after_values={"selection_status": status.value},
                reason=note,
            )
        )
        self._s.flush()
        return current


class ClientShortlistService:
    def __init__(self, session: Session) -> None:
        self._s = session

    def create_preset(
        self,
        *,
        label: str,
        filter_definition: dict,
        filter_schema_version: str,
        actor: str,
        actor_type: e.ActorType,
        map_geometry_wkt: str | None = None,
        note: str | None = None,
    ) -> ClientSearchPreset:
        _require_human(actor_type)
        preset = ClientSearchPreset(
            label=label,
            filter_definition=filter_definition,
            filter_schema_version=filter_schema_version,
            map_geometry=map_geometry_wkt,
            note=note,
            created_by=actor,
        )
        self._s.add(preset)
        self._s.add(
            AuditActionLog(
                actor=actor,
                actor_type=actor_type.value,
                action_type="client_preset_created",
                target_type="client_search_preset",
                after_values={"label": label},
            )
        )
        self._s.flush()
        return preset

    def set_entry(
        self,
        *,
        client_search_preset_id: uuid.UUID,
        canonical_listing_id: uuid.UUID,
        status: e.ShortlistEntryStatus,
        actor: str,
        actor_type: e.ActorType,
        note: str | None = None,
    ) -> ClientShortlistEntry:
        """Explicit manual inclusion/exclusion only. This is the sole write path
        for shortlist membership; no query/filter code path calls it."""
        _require_human(actor_type)
        now = _now()
        entry = self._s.execute(
            select(ClientShortlistEntry).where(
                ClientShortlistEntry.client_search_preset_id == client_search_preset_id,
                ClientShortlistEntry.canonical_listing_id == canonical_listing_id,
            )
        ).scalar_one_or_none()
        before = None if entry is None else {"entry_status": entry.entry_status}
        if entry is None:
            entry = ClientShortlistEntry(
                client_search_preset_id=client_search_preset_id,
                canonical_listing_id=canonical_listing_id,
                entry_status=status.value,
                added_by=actor,
                added_at=now,
                note=note,
            )
            self._s.add(entry)
        else:
            entry.entry_status = status.value
            if note is not None:
                entry.note = note
        self._s.add(
            AuditActionLog(
                actor=actor,
                actor_type=actor_type.value,
                action_type="client_shortlist_change",
                target_type="client_shortlist_entry",
                target_id=canonical_listing_id,
                before_values=before,
                after_values={"entry_status": status.value},
                reason=note,
            )
        )
        self._s.flush()
        return entry
