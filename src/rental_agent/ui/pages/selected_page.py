"""Selected listings + client shortlists + local CSV export (07 §18, §25)."""

import csv
import uuid
from datetime import UTC, datetime

import streamlit as st

from rental_agent.config.settings import load_settings
from rental_agent.ui import queries
from rental_agent.ui.app import session_factory
from rental_agent.ui.theme import dense_table, panel_header

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
        dense_table(
            [
                {
                    "address": r["address"],
                    "layout": r["layout"],
                    "rent": r["rent"],
                    "lifecycle": r["lifecycle"],
                    "laundry": r["laundry"],
                }
                for r in rows
            ]
        )
        include_inactive = st.checkbox("Include inactive selected listings in export")
        if st.button("Export selected to CSV (with companion files)"):
            import uuid as _uuid

            from rental_agent.exports.csv_export import export_listings

            settings_local = load_settings()
            settings_local.paths.ensure_exists()
            chosen = active if not include_inactive else rows
            with factory() as session:
                result = export_listings(
                    session,
                    settings_local.paths.exports,
                    listing_ids=[_uuid.UUID(r["listing_id"]) for r in chosen],
                    export_type="selected",
                )
            st.success(
                f"Exported to `{result.directory}` — "
                + ", ".join(f"{name}: {count}" for name, count in result.counts.items())
            )
    else:
        st.info("Nothing selected yet — use the Inventory page.")

    st.subheader("Client shortlists")
    with factory() as session:
        presets = queries.shortlist_presets(session)
        preset_entries = {
            preset.client_search_preset_id: queries.shortlist_entries(
                session, preset.client_search_preset_id
            )
            for preset in presets
        }
    if not presets:
        st.caption("No client presets yet (create one on the Inventory page).")
        return
    clients_col, entries_col = st.columns([1, 2], gap="small")
    with clients_col, st.container(border=True):
        panel_header("Active Clients", f"{len(presets)} presets")
        client_labels = [
            f"{p.label} · {len(preset_entries[p.client_search_preset_id])}" for p in presets
        ]
        chosen_index = st.radio(
            "Client",
            range(len(presets)),
            format_func=lambda i: client_labels[i],
            label_visibility="collapsed",
        )
        chosen_preset = presets[chosen_index or 0]
    with entries_col, st.container(border=True):
        panel_header(chosen_preset.label, "Shortlist entries")
        dense_table(
            preset_entries[chosen_preset.client_search_preset_id], empty="Empty shortlist."
        )


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
