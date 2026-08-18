"""Manual-selection and shortlist invariants (Phase 1 gate, 08 §9.3):

- criteria matches cannot create shortlist entries automatically
- marketing selection is independent from shortlist membership
- automatic (SYSTEM) actors cannot create manual selection states
"""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.conftest import requires_db

from rental_agent.canonical.selection_service import (
    ClientShortlistService,
    HumanActionRequired,
    MarketingSelectionService,
)
from rental_agent.contracts.enums import ActorType, SelectionStatus, ShortlistEntryStatus
from rental_agent.db.models import (
    AuditActionLog,
    ClientShortlistEntry,
    MarketingSelection,
)

pytestmark = requires_db


def test_system_actor_cannot_select(db_session: Session, seeded_listing):
    service = MarketingSelectionService(db_session)
    with pytest.raises(HumanActionRequired):
        service.set_selection(
            canonical_listing_id=seeded_listing,
            status=SelectionStatus.SELECTED,
            actor="refresh_worker",
            actor_type=ActorType.SYSTEM,
        )
    assert db_session.execute(select(func.count()).select_from(MarketingSelection)).scalar() == 0


def test_system_actor_cannot_touch_shortlist(db_session: Session, seeded_listing):
    service = ClientShortlistService(db_session)
    with pytest.raises(HumanActionRequired):
        service.create_preset(
            label="Client A",
            filter_definition={"layout": ["STUDIO"]},
            filter_schema_version="1",
            actor="refresh_worker",
            actor_type=ActorType.SYSTEM,
        )


def test_human_selection_is_persisted_and_audited(db_session: Session, seeded_listing):
    service = MarketingSelectionService(db_session)
    service.set_selection(
        canonical_listing_id=seeded_listing,
        status=SelectionStatus.SELECTED,
        actor="local_operator",
        actor_type=ActorType.HUMAN,
        note="great light",
    )
    db_session.commit()
    row = db_session.execute(select(MarketingSelection)).scalar_one()
    assert row.selection_status == "SELECTED"
    assert row.selected_by == "local_operator"
    audit = db_session.execute(select(AuditActionLog)).scalars().all()
    assert any(a.action_type == "marketing_selection_change" for a in audit)


def test_selection_and_shortlist_are_independent(db_session: Session, seeded_listing):
    selection_service = MarketingSelectionService(db_session)
    shortlist_service = ClientShortlistService(db_session)

    # Selecting for marketing creates no shortlist membership...
    selection_service.set_selection(
        canonical_listing_id=seeded_listing,
        status=SelectionStatus.SELECTED,
        actor="local_operator",
        actor_type=ActorType.HUMAN,
    )
    db_session.commit()
    assert db_session.execute(select(func.count()).select_from(ClientShortlistEntry)).scalar() == 0

    # ...and shortlisting creates no marketing selection.
    preset = shortlist_service.create_preset(
        label="Client B",
        filter_definition={"max_rent_minor": 350000},
        filter_schema_version="1",
        actor="local_operator",
        actor_type=ActorType.HUMAN,
    )
    shortlist_service.set_entry(
        client_search_preset_id=preset.client_search_preset_id,
        canonical_listing_id=seeded_listing,
        status=ShortlistEntryStatus.INCLUDED,
        actor="local_operator",
        actor_type=ActorType.HUMAN,
    )
    db_session.commit()
    selections = db_session.execute(select(MarketingSelection)).scalars().all()
    assert len(selections) == 1  # unchanged; shortlist write created no selection


def test_preset_with_map_geometry_roundtrip(db_session: Session):
    service = ClientShortlistService(db_session)
    polygon = "SRID=4326;POLYGON((-74.05 40.7, -73.9 40.7, -73.9 40.8, -74.05 40.8, -74.05 40.7))"
    preset = service.create_preset(
        label="Client C",
        filter_definition={"layout": ["ONE_BEDROOM"]},
        filter_schema_version="1",
        actor="local_operator",
        actor_type=ActorType.HUMAN,
        map_geometry_wkt=polygon,
    )
    db_session.commit()
    from sqlalchemy import text

    area = db_session.execute(
        text(
            "SELECT ST_Area(map_geometry) FROM app.client_search_preset "
            "WHERE client_search_preset_id = :id"
        ),
        {"id": preset.client_search_preset_id},
    ).scalar_one()
    assert area > 0
