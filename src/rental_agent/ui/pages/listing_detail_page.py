"""Listing detail: facts, evidence expanders, sources, history, commutes (07 §11–15)."""

import urllib.parse
import uuid
from datetime import UTC, datetime

import streamlit as st

from rental_agent.enrichment.commute.research import CommuteResearchService
from rental_agent.enrichment.llm.openai_executor import OpenAiLlmExecutor
from rental_agent.ui import queries
from rental_agent.ui.app import session_factory
from rental_agent.ui.theme import dense_table


def render() -> None:
    factory, settings = session_factory()
    st.title("Listing Detail")

    listing_id_text = st.session_state.get("detail_listing_id") or st.text_input(
        "Listing ID", help="Open a listing from the Inventory page, or paste an ID."
    )
    if not listing_id_text:
        st.info("Pick a listing from the Inventory page.")
        return
    listing_id = uuid.UUID(str(listing_id_text))

    with factory() as session:
        detail = queries.listing_detail(session, listing_id)
        facts = queries.fact_history(session, listing_id)
        commutes = queries.commutes_for_listing(session, listing_id)
        destinations = queries.active_destinations(session)
        transit = queries.transit_for_listing(session, listing_id)
    if detail is None:
        st.error("Listing not found.")
        return

    listing = detail["listing"]
    address = detail["address"]
    title_col, price_col = st.columns([3, 1])
    with title_col:
        st.subheader(address.formatted_address if address else "[address unresolved]")
        if address and address.locality:
            st.caption(address.locality)
    with price_col:
        rent = (
            f"${listing.monthly_rent_minor // 100:,}/mo"
            if listing.monthly_rent_minor
            else "rent unknown"
        )
        st.markdown(
            f'<div class="ka-card-price" style="font-size:22px;text-align:right">{rent}</div>',
            unsafe_allow_html=True,
        )
    days_on_market = (datetime.now(tz=UTC) - listing.first_seen_at).days
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Layout", listing.layout_class)
    c2.metric("Lifecycle", listing.lifecycle_status)
    c3.metric("Laundry", detail["laundry_label"])
    c4.metric("Days on market", days_on_market)
    chips = [detail["laundry_label"]]
    if listing.indoor_laundry_badge_eligible:
        chips.append("In-unit W/D badge")
    if detail["selection"] is not None and detail["selection"].selection_status == "SELECTED":
        chips.append("Selected for marketing")
    st.markdown(
        "".join(f'<span class="ka-mini">{chip}</span>' for chip in chips),
        unsafe_allow_html=True,
    )
    for override in detail["overrides"]:
        st.warning(
            f"Active override on `{override.field_name}`: {override.override_value} "
            f"({override.reason_text})"
        )

    tab_overview, tab_evidence, tab_transit, tab_commutes, tab_map = st.tabs(
        ["Overview", "Evidence & History", "Transit", "Commutes", "Map"]
    )

    with tab_transit:
        st.info(
            "Straight-line candidate distances from official MTA/PATH data — not "
            "walking distances (routed walking arrives with a walking-route provider)."
        )
        if transit:
            for mode in ("SUBWAY", "PATH", "BUS"):
                options = [t for t in transit if t["mode"] == mode]
                if not options:
                    continue
                st.markdown(f"**{mode}**")
                dense_table(
                    [
                        {
                            "station": t["stop"],
                            "operator": t["operator"],
                            "straight-line": f"{t['straight_line_m']} m",
                            "rank": t["rank"],
                            "status": t["usefulness"],
                        }
                        for t in options
                    ]
                )
        else:
            st.caption(
                "No transit candidates — the listing may lack validated "
                "coordinates, or no station falls within the candidate radius."
            )

    with tab_overview:
        st.markdown("**Source links**")
        dense_table(detail["links"], empty="No source links.")
        if listing.description_current:
            st.markdown("**Description (contact-redacted)**")
            st.write(listing.description_current)
        st.caption(
            f"First seen {listing.first_seen_at:%Y-%m-%d} · "
            f"last seen {listing.last_seen_at:%Y-%m-%d} · "
            f"last material change {listing.last_material_change_at:%Y-%m-%d}"
        )

    with tab_evidence:
        st.markdown("**Why does each value say what it says?**")
        for fact_key, assertions in facts.items():
            with st.expander(f"{fact_key} ({len(assertions)} assertion(s))"):
                dense_table(assertions)
        st.markdown("**Event history**")
        dense_table(
            [
                {
                    "time": ev.event_time,
                    "event": ev.event_type,
                    "before": ev.before_values,
                    "after": ev.after_values,
                }
                for ev in detail["events"]
            ],
            empty="No events recorded.",
        )

    with tab_commutes:
        st.info(
            "Web-researched commute estimates for a typical weekday-morning trip. "
            "Not live routing results; verify with the map view. Research is "
            "on-demand and cached 14 days."
        )
        if commutes:
            for commute in commutes:
                minutes = (
                    f"{commute['range_min'] // 60}–{commute['range_max'] // 60} min"
                    if commute["range_min"] is not None
                    else "n/a"
                )
                transfers = commute["transfers"] if commute["transfers"] is not None else "?"
                with st.container(border=True):
                    name_col, range_col = st.columns([3, 1])
                    name_col.markdown(f"**{commute['destination']}**")
                    range_col.markdown(
                        f'<div class="ka-card-price" style="text-align:right">{minutes}</div>',
                        unsafe_allow_html=True,
                    )
                    chip_html = "".join(
                        f'<span class="ka-mini">{chip}</span>'
                        for chip in (
                            f"transfers {transfers}",
                            f"confidence {commute['confidence']}",
                            f"validation {commute['validation']}",
                        )
                    )
                    st.markdown(chip_html, unsafe_allow_html=True)
                    if commute["summary"]:
                        st.caption(commute["summary"])
                    if commute["routes"]:
                        st.caption("Routes: " + ", ".join(commute["routes"]))
                    with st.expander("Sources and validation detail"):
                        for source in commute["sources"]:
                            st.markdown(
                                f"- [{source.get('title') or source['url']}]({source['url']})"
                            )
                        st.json(commute["validation_reasons"] or {})
        else:
            st.caption("No commute research yet for this listing.")

        destination = st.selectbox(
            "Research commute to…",
            destinations,
            format_func=lambda d: d.display_name,
        )
        if st.button("Run web research now (Terra + web search)"):
            key = settings.providers.openai_api_key
            if key is None:
                st.error("OpenAI key not configured.")
            else:
                executor = OpenAiLlmExecutor(
                    settings.providers.llm_default_model_id,
                    settings.providers.llm_default_reasoning_effort,
                    api_key=key.get_secret_value(),
                )
                origin = (
                    f"{address.formatted_address}, {address.locality}" if address else "unknown"
                )
                location_hash = f"addr:{address.address_id}" if address else "addr:none"
                with st.spinner("Researching (typically 30–90s)…"), factory() as session:
                    service = CommuteResearchService(
                        session,
                        executor,
                        cache_days=settings.providers.commute_research_cache_days,
                    )
                    try:
                        service.research(
                            canonical_listing_id=listing_id,
                            destination_id=destination.destination_id,
                            origin_description=origin,
                            input_location_hash=location_hash,
                        )
                        session.commit()
                        st.rerun()
                    except Exception as exc:  # noqa: BLE001 - surfaced to operator
                        session.rollback()
                        st.error(f"Research rejected: {exc}")

    with tab_map:
        if detail["lat"] is not None:
            # Free keyless Google Maps embed for manual verification (B7).
            query = urllib.parse.quote(f"{detail['lat']},{detail['lon']}")
            st.components.v1.iframe(
                f"https://maps.google.com/maps?q={query}&z=16&output=embed", height=450
            )
            st.caption("Google Maps view of the listing location for manual verification.")
        else:
            st.info("No validated coordinates for this listing; nothing is shown at a guess.")
