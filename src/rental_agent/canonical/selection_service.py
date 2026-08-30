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
        canonical_listing_id: uuid.UUID | None = None,
        company_property_id: uuid.UUID | None = None,
        status: e.SelectionStatus,
        actor: str,
        actor_type: e.ActorType,
        note: str | None = None,
    ) -> MarketingSelection:
        """Targets exactly one of a canonical listing or a company portfolio
        property (owner request 2026-08-30 — company properties are selected
        for ads through the same workflow)."""
        _require_human(actor_type)
        if (canonical_listing_id is None) == (company_property_id is None):
            raise ValueError(
                "set_selection targets exactly one of "
                "canonical_listing_id / company_property_id"
            )
        now = _now()
        target_filter = (
            MarketingSelection.canonical_listing_id == canonical_listing_id
            if canonical_listing_id is not None
            else MarketingSelection.company_property_id == company_property_id
        )
        current = self._s.execute(
            select(MarketingSelection).where(target_filter)
        ).scalar_one_or_none()
        before = None if current is None else {"selection_status": current.selection_status}
        if current is None:
            current = MarketingSelection(
                canonical_listing_id=canonical_listing_id,
                company_property_id=company_property_id,
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
                target_type=(
                    "canonical_listing"
                    if canonical_listing_id is not None
                    else "company_property"
                ),
                target_id=canonical_listing_id
                if canonical_listing_id is not None
                else company_property_id,
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
        canonical_listing_id: uuid.UUID | None = None,
        company_property_id: uuid.UUID | None = None,
        status: e.ShortlistEntryStatus,
        actor: str,
        actor_type: e.ActorType,
        note: str | None = None,
    ) -> ClientShortlistEntry:
        """Explicit manual inclusion/exclusion only. This is the sole write path
        for shortlist membership; no query/filter code path calls it.

        Targets exactly one of a canonical listing or a company portfolio
        property (owner request 2026-08-29 — company properties are managed
        through the same client workflow)."""
        _require_human(actor_type)
        if (canonical_listing_id is None) == (company_property_id is None):
            raise ValueError(
                "set_entry targets exactly one of canonical_listing_id / company_property_id"
            )
        now = _now()
        target_filter = (
            ClientShortlistEntry.canonical_listing_id == canonical_listing_id
            if canonical_listing_id is not None
            else ClientShortlistEntry.company_property_id == company_property_id
        )
        entry = self._s.execute(
            select(ClientShortlistEntry).where(
                ClientShortlistEntry.client_search_preset_id == client_search_preset_id,
                target_filter,
            )
        ).scalar_one_or_none()
        before = None if entry is None else {"entry_status": entry.entry_status}
        if entry is None:
            entry = ClientShortlistEntry(
                client_search_preset_id=client_search_preset_id,
                canonical_listing_id=canonical_listing_id,
                company_property_id=company_property_id,
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
                target_id=canonical_listing_id
                if canonical_listing_id is not None
                else company_property_id,
                before_values=before,
                after_values={"entry_status": status.value},
                reason=note,
            )
        )
        self._s.flush()
        return entry

    def update_profile(
        self,
        *,
        client_search_preset_id: uuid.UUID,
        profile: dict,
        actor: str,
        actor_type: e.ActorType,
    ) -> ClientSearchPreset:
        """Store the client's needs profile (owner decision 2026-08-18).

        Lives inside filter_definition["client_profile"] — describes needs
        (budget, layouts, income, gender, ...), never identity/contact data;
        the label stays a pseudonym.
        """
        _require_human(actor_type)
        preset = self._s.get(ClientSearchPreset, client_search_preset_id)
        if preset is None:
            raise ValueError("client preset not found")
        before = dict(preset.filter_definition or {})
        updated = dict(preset.filter_definition or {})
        updated["client_profile"] = profile
        preset.filter_definition = updated
        self._s.add(
            AuditActionLog(
                actor=actor,
                actor_type=actor_type.value,
                action_type="client_profile_updated",
                target_type="client_search_preset",
                target_id=client_search_preset_id,
                before_values={"client_profile": before.get("client_profile")},
                after_values={"client_profile": profile},
            )
        )
        self._s.flush()
        return preset

    def restore_preset(
        self,
        *,
        client_search_preset_id: uuid.UUID,
        actor: str,
        actor_type: e.ActorType,
    ) -> ClientSearchPreset:
        """Un-archive a soft-removed client (labels are unique, so re-adding a
        removed pseudonym restores it — entries and profile come back)."""
        _require_human(actor_type)
        preset = self._s.get(ClientSearchPreset, client_search_preset_id)
        if preset is None:
            raise ValueError("client preset not found")
        preset.archived_at = None
        self._s.add(
            AuditActionLog(
                actor=actor,
                actor_type=actor_type.value,
                action_type="client_preset_restored",
                target_type="client_search_preset",
                target_id=client_search_preset_id,
                after_values={"label": preset.label},
            )
        )
        self._s.flush()
        return preset

    def archive_preset(
        self,
        *,
        client_search_preset_id: uuid.UUID,
        actor: str,
        actor_type: e.ActorType,
    ) -> ClientSearchPreset:
        """Soft-remove a client: preset + entries stay for audit, hidden from UI."""
        _require_human(actor_type)
        preset = self._s.get(ClientSearchPreset, client_search_preset_id)
        if preset is None:
            raise ValueError("client preset not found")
        preset.archived_at = _now()
        self._s.add(
            AuditActionLog(
                actor=actor,
                actor_type=actor_type.value,
                action_type="client_preset_archived",
                target_type="client_search_preset",
                target_id=client_search_preset_id,
                after_values={"label": preset.label},
            )
        )
        self._s.flush()
        return preset
