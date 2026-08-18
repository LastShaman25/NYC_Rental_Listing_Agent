"""Inventory workspace: filters + map + table + manual selection/shortlist (07 §9–10)."""

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

LAYOUTS = ["STUDIO", "ONE_BEDROOM", "TWO_BEDROOM", "OUT_OF_SCOPE", "UNKNOWN"]
LIFECYCLES = ["CANDIDATE", "ACTIVE", "MISSING", "INACTIVE", "REAPPEARED", "REVIEW_REQUIRED"]


def render() -> None:
    factory, settings = session_factory()
    st.title("Inventory")

    with st.sidebar:
        st.subheader("Filters")
        layouts = st.multiselect("Layout", LAYOUTS, default=[])
        lifecycle = st.multiselect("Lifecycle", LIFECYCLES, default=[])
        locality = st.text_input("Locality contains")
        max_rent = st.number_input("Max rent $ (0 = any)", min_value=0, step=100, value=0)
        selected_only = st.checkbox("Selected for marketing only")

    drawn = st.session_state.get("drawn_geometry")
    filters = queries.InventoryFilters(
        layouts=layouts or None,
        lifecycle=lifecycle or None,
        locality=locality or None,
        max_rent_minor=int(max_rent) * 100 if max_rent else None,
        selected_only=selected_only,
        geometry_geojson=drawn,
    )
    with factory() as session:
        rows = queries.inventory(session, filters)

    caption = f"{len(rows)} listings match the current filters"
    if drawn:
        caption += " · drawn-area filter active"
    st.caption(caption)
    if drawn and st.button("Clear drawn-area filter"):
        del st.session_state["drawn_geometry"]
        st.rerun()

    markers = [
        MapMarker(
            listing_id=row["listing_id"],
            latitude=row["lat"],
            longitude=row["lon"],
            precision=LocationPrecision(row["precision"]),
            state={
                "label": f"{row['layout']} · {row['rent']}",
                "selected": row["selected"],
            },
        )
        for row in rows
        if row["lat"] is not None and row["lon"] is not None
    ]
    unmapped = len(rows) - len(markers)
    if unmapped:
        st.caption(f"{unmapped} listing(s) lack validated coordinates and appear only below.")
    fmap = FoliumMapAdapter(settings.providers.map_tile_provider_code).render(
        MapRenderRequest(markers=markers, drawn_geometry_geojson=drawn)
    )
    map_state = st_folium(
        fmap,
        use_container_width=True,
        height=450,
        returned_objects=["last_active_drawing"],
    )
    st.caption("Draw a polygon/rectangle on the map to filter the listings to that area.")
    new_drawing = (map_state or {}).get("last_active_drawing")
    if new_drawing and new_drawing.get("geometry") != drawn:
        st.session_state["drawn_geometry"] = new_drawing["geometry"]
        st.rerun()

    st.subheader("Listings")
    if not rows:
        st.info("No listings match — or no acquisition run has completed yet.")
        return

    header = st.columns([3, 1, 1, 1, 2, 1, 1])
    for col, name in zip(
        header,
        ["Address", "Layout", "Rent", "Lifecycle", "Laundry", "Selected", ""],
        strict=False,
    ):
        col.markdown(f"**{name}**")
    for row in rows[:100]:
        cols = st.columns([3, 1, 1, 1, 2, 1, 1])
        cols[0].write(row["address"])
        cols[1].write(row["layout"])
        cols[2].write(row["rent"])
        cols[3].write(row["lifecycle"])
        cols[4].write(row["laundry"])
        listing_id = row["listing_id"]
        label = "Deselect" if row["selected"] else "Select"
        if cols[5].button(label, key=f"sel-{listing_id}"):
            with factory() as session:
                MarketingSelectionService(session).set_selection(
                    canonical_listing_id=uuid.UUID(listing_id),
                    status=(
                        SelectionStatus.REMOVED if row["selected"] else SelectionStatus.SELECTED
                    ),
                    actor=settings.operator_id,
                    actor_type=ActorType.HUMAN,
                )
                session.commit()
            st.rerun()
        if cols[6].button("Detail", key=f"det-{listing_id}"):
            st.session_state["detail_listing_id"] = listing_id
            st.switch_page("detail")

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
