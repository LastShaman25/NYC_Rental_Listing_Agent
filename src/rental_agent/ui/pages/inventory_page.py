"""Inventory workspace: filters + map + list + manual selection/shortlist (07 §9–10).

Layout follows the Stitch "Map & Inventory Command Center" screen: a Filters
panel on the left, the map as the central canvas, and an Inventory List of
property cards on the right. Streamlit cannot truly float panels over the map,
so the panels are styled columns flanking it.
"""

import uuid

import streamlit as st
from streamlit_folium import st_folium

from rental_agent.canonical.selection_service import (
    ClientShortlistService,
    MarketingSelectionService,
)
from rental_agent.contracts.enums import (
    ActorType,
    LocationPrecision,
    SelectionStatus,
    ShortlistEntryStatus,
)
from rental_agent.contracts.providers import MapMarker, MapRenderRequest
from rental_agent.ui import queries
from rental_agent.ui.app import session_factory
from rental_agent.ui.map_adapter import FoliumMapAdapter
from rental_agent.ui.theme import filter_chips, listing_card, panel_header

# Display label -> canonical layout_class value (Stitch layout chips).
LAYOUT_CHOICES = {
    "Studio": "STUDIO",
    "1BR": "ONE_BEDROOM",
    "2BR": "TWO_BEDROOM",
    "3BR+": "OUT_OF_SCOPE",
    "Unknown": "UNKNOWN",
}
LIFECYCLES = ["CANDIDATE", "ACTIVE", "MISSING", "INACTIVE", "REAPPEARED", "REVIEW_REQUIRED"]
_IN_UNIT_LAUNDRY = [
    "IN_UNIT_WASHER_DRYER_CONFIRMED",
    "IN_UNIT_WASHER_ONLY",
    "IN_UNIT_DRYER_ONLY",
    "IN_UNIT_HOOKUP_ONLY",
]
_LAYOUT_SHORT = {
    "STUDIO": "ST",
    "ONE_BEDROOM": "1BR",
    "TWO_BEDROOM": "2BR",
    "OUT_OF_SCOPE": "3BR+",
    "UNKNOWN": "?",
}
LIST_CAP = 40


def render() -> None:
    factory, settings = session_factory()
    st.title("Inventory")

    filters_col, map_col, list_col = st.columns([14, 34, 17], gap="small")

    with filters_col, st.container(border=True):
        panel_header("Filters")
        st.markdown('<div class="ka-label">Price range</div>', unsafe_allow_html=True)
        min_col, max_col = st.columns(2)
        min_rent = min_col.number_input(
            "Min $", min_value=0, step=100, value=0, label_visibility="collapsed"
        )
        max_rent = max_col.number_input(
            "Max $ (0 = any)", min_value=0, step=100, value=0, label_visibility="collapsed"
        )
        st.markdown('<div class="ka-label">Layout</div>', unsafe_allow_html=True)
        layout_labels = st.pills(
            "Layout",
            list(LAYOUT_CHOICES),
            selection_mode="multi",
            label_visibility="collapsed",
        )
        layouts = [LAYOUT_CHOICES[label] for label in layout_labels or []]
        st.markdown('<div class="ka-label">Locality</div>', unsafe_allow_html=True)
        locality = st.text_input(
            "Locality contains", placeholder="e.g. Hoboken", label_visibility="collapsed"
        )
        st.markdown('<div class="ka-label">Laundry</div>', unsafe_allow_html=True)
        in_unit = st.checkbox("In-unit")
        building = st.checkbox("Building")
        laundry: list[str] = []
        if in_unit:
            laundry += _IN_UNIT_LAUNDRY
        if building:
            laundry.append("BUILDING_SHARED_LAUNDRY")
        selected_only = st.checkbox("Selected for marketing only")
        with st.expander("Lifecycle"):
            lifecycle = st.multiselect("Lifecycle", LIFECYCLES, label_visibility="collapsed")
        drawn = st.session_state.get("drawn_geometry")
        if drawn and st.button("Clear drawn-area filter", width="stretch"):
            del st.session_state["drawn_geometry"]
            st.rerun()

    filters = queries.InventoryFilters(
        layouts=layouts or None,
        lifecycle=lifecycle or None,
        laundry=laundry or None,
        locality=locality or None,
        min_rent_minor=int(min_rent) * 100 if min_rent else None,
        max_rent_minor=int(max_rent) * 100 if max_rent else None,
        selected_only=selected_only,
        geometry_geojson=drawn,
    )
    with factory() as session:
        rows = queries.inventory(session, filters)

    with map_col:
        chips: list[tuple[str, bool]] = [(f"{len(rows)} MATCHES", True)]
        chips += [(label, True) for label in layout_labels or []]
        chips += [(state, True) for state in lifecycle]
        if locality:
            chips.append((f"IN {locality.upper()}", True))
        if min_rent:
            chips.append((f"≥ ${int(min_rent):,}", True))
        if max_rent:
            chips.append((f"≤ ${int(max_rent):,}", True))
        if laundry:
            chips.append(("LAUNDRY", True))
        if selected_only:
            chips.append(("SELECTED ONLY", True))
        if drawn:
            chips.append(("DRAWN AREA", True))
        filter_chips(chips)

        markers = [
            MapMarker(
                listing_id=row["listing_id"],
                latitude=row["lat"],
                longitude=row["lon"],
                precision=LocationPrecision(row["precision"]),
                state={
                    # marker-id style: dense "1BR $3,400" badge label (DESIGN.md).
                    "label": f"{_LAYOUT_SHORT.get(row['layout'], '?')} {row['rent']}",
                    "selected": row["selected"],
                    "lifecycle": row["lifecycle"],
                },
            )
            for row in rows
            if row["lat"] is not None and row["lon"] is not None
        ]
        fmap = FoliumMapAdapter(settings.providers.map_tile_provider_code).render(
            MapRenderRequest(markers=markers, drawn_geometry_geojson=drawn)
        )
        map_state = st_folium(
            fmap,
            use_container_width=True,  # st_folium's own parameter, not Streamlit's
            height=620,
            returned_objects=["last_active_drawing"],
        )
        st.caption("Draw a polygon/rectangle on the map to filter the listings to that area.")
        new_drawing = (map_state or {}).get("last_active_drawing")
        if new_drawing and new_drawing.get("geometry") != drawn:
            st.session_state["drawn_geometry"] = new_drawing["geometry"]
            st.rerun()

    with list_col, st.container(border=True):
        panel_header("Inventory List", f"{len(rows)} results")
        unmapped = sum(1 for row in rows if row["lat"] is None or row["lon"] is None)
        if unmapped:
            st.caption(f"{unmapped} listing(s) lack validated coordinates (list only).")
        if not rows:
            st.info("No listings match — or no acquisition run has completed yet.")
        for row in rows[:LIST_CAP]:
            listing_card(row)
            listing_id = row["listing_id"]
            select_col, detail_col = st.columns([3, 1], gap="small")
            label = "Deselect" if row["selected"] else "Select for Ad"
            if select_col.button(label, key=f"sel-{listing_id}", width="stretch"):
                with factory() as session:
                    MarketingSelectionService(session).set_selection(
                        canonical_listing_id=uuid.UUID(listing_id),
                        status=(
                            SelectionStatus.REMOVED
                            if row["selected"]
                            else SelectionStatus.SELECTED
                        ),
                        actor=settings.operator_id,
                        actor_type=ActorType.HUMAN,
                    )
                    session.commit()
                st.rerun()
            if detail_col.button("Open", key=f"det-{listing_id}", width="stretch"):
                st.session_state["detail_listing_id"] = listing_id
                st.switch_page("detail")
        if len(rows) > LIST_CAP:
            st.caption(f"Showing first {LIST_CAP} of {len(rows)} — refine the filters.")

    _shortlist_controls(factory, settings, rows)


def _shortlist_controls(factory, settings, rows) -> None:
    st.subheader("Client shortlists")
    st.caption(
        "Live filter matches are never saved automatically — only explicit "
        "additions below create shortlist entries."
    )
    with factory() as session:
        presets = queries.shortlist_presets(session)
    with st.expander("Add a listing to a client shortlist"):
        new_label = st.text_input("New client label (pseudonym only)")
        if st.button("Create preset") and new_label:
            with factory() as session:
                ClientShortlistService(session).create_preset(
                    label=new_label,
                    filter_definition={},
                    filter_schema_version="1",
                    actor=settings.operator_id,
                    actor_type=ActorType.HUMAN,
                )
                session.commit()
            st.rerun()
        if presets and rows:
            preset = st.selectbox(
                "Client", presets, format_func=lambda p: p.label, key="shortlist-preset"
            )
            listing_choice = st.selectbox(
                "Listing",
                rows,
                format_func=lambda r: f"{r['address']} ({r['layout']}, {r['rent']})",
                key="shortlist-listing",
            )
            note = st.text_input("Note (optional)", key="shortlist-note")
            if st.button("Add to shortlist"):
                with factory() as session:
                    ClientShortlistService(session).set_entry(
                        client_search_preset_id=preset.client_search_preset_id,
                        canonical_listing_id=uuid.UUID(listing_choice["listing_id"]),
                        status=ShortlistEntryStatus.INCLUDED,
                        actor=settings.operator_id,
                        actor_type=ActorType.HUMAN,
                        note=note or None,
                    )
                    session.commit()
                st.success(f"Added to {preset.label}'s shortlist.")
