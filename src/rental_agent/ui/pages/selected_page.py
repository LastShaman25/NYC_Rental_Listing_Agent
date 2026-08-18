"""Selected listings + client shortlists + local CSV export (07 §18, §25)."""

import csv
import uuid
from datetime import UTC, datetime

import streamlit as st

from rental_agent.config.settings import load_settings
from rental_agent.ui import queries
from rental_agent.ui.app import session_factory

# Cells starting with these can execute as spreadsheet formulas (06 §28.5).
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t")


def _formula_safe(value) -> str:
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(_FORMULA_PREFIXES) else text


def render() -> None:
    factory, settings = session_factory()
    st.title("Selected")

    with factory() as session:
        rows = queries.inventory(session, queries.InventoryFilters(selected_only=True, limit=1000))
    active = [r for r in rows if r["lifecycle"] in ("ACTIVE", "CANDIDATE", "REAPPEARED")]
    inactive = [r for r in rows if r not in active]

    st.subheader(f"Selected listings ({len(rows)})")
    if inactive:
        st.warning(
            f"{len(inactive)} selected listing(s) are missing/inactive — kept for history, "
            "excluded from the default export."
        )
    if rows:
        st.dataframe(
            [
                {
                    "Address": r["address"],
                    "Layout": r["layout"],
                    "Rent": r["rent"],
                    "Lifecycle": r["lifecycle"],
                    "Laundry": r["laundry"],
                }
                for r in rows
            ],
            use_container_width=True,
        )
        include_inactive = st.checkbox("Include inactive selected listings in export")
        if st.button("Export selected to CSV"):
            path = _export(active if not include_inactive else rows)
            st.success(f"Exported to `{path}`")
    else:
        st.info("Nothing selected yet — use the Inventory page.")

    st.subheader("Client shortlists")
    with factory() as session:
        presets = queries.shortlist_presets(session)
        if not presets:
            st.caption("No client presets yet (create one on the Inventory page).")
        for preset in presets:
            entries = queries.shortlist_entries(session, preset.client_search_preset_id)
            with st.expander(f"{preset.label} ({len(entries)} entries)"):
                if entries:
                    st.dataframe(entries, use_container_width=True)
                else:
                    st.caption("Empty shortlist.")


def _export(rows) -> str:
    settings = load_settings()
    settings.paths.ensure_exists()
    stamp = datetime.now(tz=UTC).strftime("%Y-%m-%d_%H%M")
    directory = settings.paths.exports / f"{stamp}_selected_{uuid.uuid4().hex[:6]}"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "listings.csv"
    columns = [
        "listing_id",
        "address",
        "locality",
        "layout",
        "rent",
        "lifecycle",
        "laundry",
        "first_seen",
        "last_seen",
    ]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([_formula_safe(row.get(column)) for column in columns])
    return str(path)
