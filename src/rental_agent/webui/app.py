"""FastAPI app serving the Stitch "Metro Rental Command Center" screens.

Visual truth is the Stitch project (templates reproduce its Tailwind markup
verbatim); functional truth is /md: no scores, commute ranges with confidence,
no fabricated data, manual-only selection and shortlists (07). Pages render
read models from ui/queries.py and call canonical services for writes — no
business rules live here (07 §23.1).

Run: uv run --no-sync uvicorn rental_agent.webui.app:app --port 8600
"""

import json
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text as sql_text
from sqlalchemy.orm import sessionmaker

from rental_agent.canonical.merge_service import MergeService
from rental_agent.canonical.selection_service import (
    ClientShortlistService,
    MarketingSelectionService,
)
from rental_agent.contracts.enums import ActorType, SelectionStatus, ShortlistEntryStatus
from rental_agent.db.models import ReviewIssue
from rental_agent.ui import queries

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

_LAYOUT_CHIPS = [
    ("STUDIO", "Studio"),
    ("ONE_BEDROOM", "1BR"),
    ("TWO_BEDROOM", "2BR"),
    ("OUT_OF_SCOPE", "3BR+"),
    ("UNKNOWN", "Unknown"),
]
_LAYOUT_LABELS = dict(_LAYOUT_CHIPS)
_LAYOUT_SHORT = {
    "STUDIO": "ST",
    "ONE_BEDROOM": "1BR",
    "TWO_BEDROOM": "2BR",
    "OUT_OF_SCOPE": "3BR+",
    "UNKNOWN": "?",
}
_LIFECYCLES = ["CANDIDATE", "ACTIVE", "MISSING", "INACTIVE", "REAPPEARED", "REVIEW_REQUIRED"]
_WARN_LIFECYCLES = ("MISSING", "REVIEW_REQUIRED", "REAPPEARED")
_IN_UNIT_LAUNDRY = [
    "IN_UNIT_WASHER_DRYER_CONFIRMED",
    "IN_UNIT_WASHER_ONLY",
    "IN_UNIT_DRYER_ONLY",
    "IN_UNIT_HOOKUP_ONLY",
]
# One nav, on the rail only (owner decision 2026-08-18): Dash, Map, Clients,
# Selected, Studio; Settings (with the Log and data review) sits at the rail
# bottom. The old Operations/Review pages fold into /settings.
_NAV = [
    ("/", "dashboard", "Dashboard", "Dash", "monitoring"),
    ("/inventory", "inventory", "Inventory", "Map", "map"),
    ("/clients", "clients", "Clients", "Clients", "group"),
    ("/selected", "selected", "Selected", "Selected", "ad_units"),
    ("/studio", "studio", "Studio", "Studio", "edit_note"),
]
_GOOD_STATUSES = ("SUCCEEDED", "COMPLETED", "ACTIVE")
_BAD_STATUSES = ("FAILED",)


def _marker_accent(selected: bool, lifecycle: str) -> str:
    if selected:
        return "#3B82F6"
    if lifecycle == "ACTIVE":
        return "#006c4a"
    if lifecycle in _WARN_LIFECYCLES:
        return "#F59E0B"
    return "#64748B"


def _tone(status: str) -> str:
    if status in _GOOD_STATUSES:
        return "good"
    if status in _BAD_STATUSES:
        return "bad"
    if status in ("PENDING", "DEGRADED", "PARTIAL_SUCCESS", "RUNNING"):
        return "warn"
    return "info"


def _stamp(value: datetime | None) -> str:
    return value.strftime("%m-%d %H:%M") if value else "—"


def _safe_next(raw: str | None, fallback: str) -> str:
    return raw if raw and raw.startswith("/") and not raw.startswith("//") else fallback


def _nav_items(active: str) -> list[dict[str, str | bool]]:
    return [
        {"href": href, "title": title, "label": label, "icon": icon, "active": key == active}
        for href, key, title, label, icon in _NAV
    ]


def _kfmt(rent_minor: int) -> str:
    """Compact marker price, e.g. $3.2k (the Stitch marker style)."""
    value = rent_minor / 100_000
    text = f"{value:.1f}".removesuffix(".0")
    return f"${text}k"


def _rent_range_label(units: list[dict[str, Any]]) -> str:
    rents = [u["rent_minor"] for u in units if u["rent_minor"] is not None]
    if not rents:
        return "unknown"
    low, high = min(rents), max(rents)
    if low == high:
        return f"${low // 100:,}"
    return f"${low // 100:,}–${high // 100:,}"


def _group_by_building(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One property per building: units listed, rent shown as a range (owner
    decision 2026-08-18 — no overlapping markers for multi-unit buildings)."""
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        prop = grouped.setdefault(
            row["building_id"],
            {
                "building_id": row["building_id"],
                "address": row["address"],
                "locality": row["locality"],
                "lat": row["lat"],
                "lon": row["lon"],
                "units": [],
            },
        )
        prop["units"].append(row)
    properties = []
    for prop in grouped.values():
        units = sorted(
            prop["units"], key=lambda u: (u["rent_minor"] is None, u["rent_minor"] or 0)
        )
        prop["units"] = units
        prop["primary"] = units[0]
        prop["rent_label"] = _rent_range_label(units)
        prop["selected"] = any(u["selected"] for u in units)
        prop["warn"] = any(u["warn"] for u in units)
        prop["lifecycle"] = ", ".join(sorted({u["lifecycle"] for u in units if u["warn"]}))
        rents = [u["rent_minor"] for u in units if u["rent_minor"] is not None]
        if len(units) == 1:
            label = f"{_LAYOUT_SHORT.get(units[0]['layout'], '?')} {_kfmt(rents[0])}"
        else:
            label = f"{len(units)}u {_kfmt(min(rents))}–{_kfmt(max(rents))}"
        accent = "#3B82F6" if prop["selected"] else (
            "#F59E0B" if prop["warn"] else _marker_accent(False, units[0]["lifecycle"])
        )
        prop["marker"] = (
            {
                "id": prop["primary"]["listing_id"],
                "lat": prop["lat"],
                "lon": prop["lon"],
                "label": label,
                "accent": accent,
            }
            if prop["lat"] is not None and prop["lon"] is not None
            else None
        )
        properties.append(prop)
    return properties


def create_app(factory: sessionmaker | None = None, settings: Any = None) -> FastAPI:
    if factory is None or settings is None:
        from rental_agent.config.settings import load_settings
        from rental_agent.db.engine import build_engine, build_session_factory

        settings = load_settings()
        factory = build_session_factory(build_engine(settings))

    app = FastAPI(title="Metro Rental Command Center")

    def render(template: str, request: Request, active: str, **context: Any) -> HTMLResponse:
        with factory() as session:
            open_issues = queries.dashboard_summary(session)["open_issues"]
        return _TEMPLATES.TemplateResponse(
            request,
            template,
            {
                "nav_items": _nav_items(active),
                "settings_active": active == "settings",
                "open_issue_count": open_issues,
                **context,
            },
        )

    # -- pages -----------------------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request) -> HTMLResponse:
        with factory() as session:
            started = time.perf_counter()
            session.execute(sql_text("SELECT 1"))
            latency_ms = round((time.perf_counter() - started) * 1000)
            summary = queries.dashboard_summary(session)
            runs = queries.recent_refresh_runs(session)
            source_runs = queries.source_run_history(session)
            buckets = queries.freshness_buckets(session)
            rows = queries.inventory(
                session, queries.InventoryFilters(has_rent=True, limit=500)
            )
        for row in rows:
            row["warn"] = row["lifecycle"] in _WARN_LIFECYCLES
            row["layout_label"] = _LAYOUT_LABELS.get(row["layout"], row["layout"])
        coverage_markers = [
            p["marker"] for p in _group_by_building(rows) if p["marker"] is not None
        ]
        peak = max((count for _, count in buckets), default=0) or 1
        freshness = [
            {"name": name, "count": count, "pct": max(4, round(count / peak * 100))}
            for name, count in buckets
        ]
        feed = [
            {
                "tone": _tone(str(run["status"])),
                "title": f"Refresh {run['status']}",
                "subtitle": str(run["run"]),
                "stamp": _stamp(run["started"]),
            }
            for run in runs[:4]
        ] + [
            {
                "tone": _tone(str(run["status"])),
                "title": f"{run['source']} {run['status']}",
                "subtitle": (
                    f"{(run.get('counts') or {}).get('discovered', '?')} discovered · "
                    f"{(run.get('counts') or {}).get('persisted_new', '?')} persisted"
                ),
                "stamp": _stamp(run["started"]),
            }
            for run in source_runs[:4]
        ]
        last_refresh = "never"
        if runs:
            stamp = runs[0]["completed"] or runs[0]["started"]
            if stamp:
                last_refresh = stamp.strftime("%Y-%m-%d %H:%M")
        return render(
            "dashboard.html",
            request,
            "dashboard",
            summary=summary,
            freshness=freshness,
            feed=feed,
            last_refresh=last_refresh,
            db_latency_ms=latency_ms,
            attention_count=summary["open_issues"] + summary["pending_duplicates"],
            markers_json=json.dumps(coverage_markers),
        )

    @app.get("/inventory", response_class=HTMLResponse)
    def inventory(request: Request) -> HTMLResponse:
        params = request.query_params
        layouts = params.getlist("layout")
        lifecycle = params.getlist("lifecycle")
        min_rent = params.get("min_rent") or ""
        max_rent = params.get("max_rent") or ""
        locality = params.get("locality") or ""
        in_unit = params.get("in_unit") == "1"
        building = params.get("building") == "1"
        selected_only = params.get("selected_only") == "1"
        floor_plan_only = params.get("floor_plan") == "1"
        geometry_raw = params.get("geometry") or ""
        geometry: dict[str, Any] | None = None
        if geometry_raw:
            try:
                geometry = json.loads(geometry_raw)
            except json.JSONDecodeError:
                geometry_raw = ""
        laundry: list[str] = []
        if in_unit:
            laundry += _IN_UNIT_LAUNDRY
        if building:
            laundry.append("BUILDING_SHARED_LAUNDRY")
        filters = queries.InventoryFilters(
            layouts=layouts or None,
            lifecycle=lifecycle or None,
            laundry=laundry or None,
            locality=locality or None,
            min_rent_minor=int(min_rent) * 100 if min_rent.isdigit() and int(min_rent) else None,
            max_rent_minor=int(max_rent) * 100 if max_rent.isdigit() and int(max_rent) else None,
            selected_only=selected_only,
            has_rent=True,  # rent-unknown listings are excluded from the workspace
            has_floor_plan=floor_plan_only,
            geometry_geojson=geometry,
        )
        with factory() as session:
            rows = queries.inventory(session, filters)
            counts = queries.laundry_counts(session)
            client_presets = [
                {"id": str(p.client_search_preset_id), "label": p.label}
                for p in queries.shortlist_presets(session)
            ]
        for row in rows:
            row["warn"] = row["lifecycle"] in _WARN_LIFECYCLES
            row["layout_label"] = _LAYOUT_LABELS.get(row["layout"], row["layout"])
            laundry_text = str(row["laundry"])
            row["laundry_chip"] = "" if laundry_text == "Laundry unknown" else laundry_text
        properties = _group_by_building(rows)
        markers = [p["marker"] for p in properties if p["marker"] is not None]
        retained = [(k, v) for k, v in params.multi_items() if k != "geometry"]
        from urllib.parse import urlencode

        clear_geometry_url = "/inventory" + ("?" + urlencode(retained) if retained else "")
        return render(
            "inventory.html",
            request,
            "inventory",
            properties=properties,
            unit_count=len(rows),
            laundry_counts=counts,
            laundry_filter_active=bool(laundry),
            list_cap=60,
            visible_count=min(len(properties), 60),
            unmapped_count=len(properties) - len(markers),
            markers_json=json.dumps(markers),
            geometry_json=json.dumps(geometry),
            client_presets_json=json.dumps(client_presets),
            clear_geometry_url=clear_geometry_url,
            filters={
                "min_rent": min_rent,
                "max_rent": max_rent,
                "locality": locality,
                "in_unit": in_unit,
                "building": building,
                "selected_only": selected_only,
                "floor_plan": floor_plan_only,
                "geometry": geometry_raw,
            },
            layout_chips=[
                {"value": value, "label": label, "on": value in layouts}
                for value, label in _LAYOUT_CHIPS
            ],
            lifecycle_chips=[
                {"value": state, "label": state.replace("_", " ").title(), "on": state in lifecycle}
                for state in _LIFECYCLES
            ],
        )

    @app.get("/listing/{listing_id}", response_class=HTMLResponse)
    def listing_detail(request: Request, listing_id: uuid.UUID) -> HTMLResponse:
        with factory() as session:
            detail = queries.listing_detail(session, listing_id)
            if detail is None:
                return RedirectResponse("/inventory", status_code=303)  # type: ignore[return-value]
            facts = queries.fact_history(session, listing_id)
            commutes = queries.commutes_for_listing(session, listing_id)
            destinations = queries.active_destinations(session)
            transit = queries.transit_for_listing(session, listing_id)
            listing = detail["listing"]
            units = queries.listings_in_building(session, listing.building_id)
            floor_plans = queries.floor_plans_for_listing(
                session, listing_id, listing.building_id
            )
            # Google Maps walking directions (keyless deep link) as the primary
            # verification for each station; the OSRM number is the cross-check
            # (owner decision 2026-08-18: prioritize Google Maps distances).
            if detail["lat"] is not None:
                from urllib.parse import quote as _quote

                for t in transit:
                    destination = _quote(f"{t['stop']} station, New York")
                    t["gmaps_url"] = (
                        "https://www.google.com/maps/dir/?api=1"
                        f"&origin={detail['lat']},{detail['lon']}"
                        f"&destination={destination}&travelmode=walking"
                    )
            address = detail["address"]
            selected = (
                detail["selection"] is not None
                and detail["selection"].selection_status == "SELECTED"
            )
            chips = []
            if listing.indoor_laundry_badge_eligible:
                chips.append("In-unit W/D (validated)")
            for fact_key in ("fee_status", "amenities"):
                current = next(
                    (a for a in facts.get(fact_key, []) if a["current"]), None
                )
                if current is None:
                    continue
                if fact_key == "fee_status" and current["value"] == "NO_FEE":
                    chips.append("No fee (page-stated)")
                elif fact_key == "amenities" and isinstance(current["value"], list):
                    chips.extend(str(a) for a in current["value"][:10])
            for override in detail["overrides"]:
                chips.append(f"Override: {override.field_name} = {override.override_value}")
            commute_cards = []
            for c in commutes:
                if c["range_min"] is not None:
                    rng = f"{c['range_min'] // 60}–{c['range_max'] // 60}m"
                else:
                    rng = "n/a"
                conf = str(c["confidence"] or "UNKNOWN")
                commute_cards.append(
                    {
                        "destination": c["destination"],
                        "icon": (
                            "flight_takeoff"
                            if "airport" in str(c["destination"]).lower()
                            else "business_center"
                        ),
                        "routes": ", ".join(c["routes"] or []) or "routes unrecorded",
                        "range": rng,
                        "confidence": conf,
                        "validation": str(c["validation"] or ""),
                        "conf_class": "text-secondary" if conf == "HIGH" else "text-status-warning",
                        "conf_icon": "check_circle" if conf == "HIGH" else "info",
                        "summary": c["summary"],
                        "sources": [
                            {"url": s["url"], "title": s.get("title") or s["url"]}
                            for s in (c["sources"] or [])
                        ],
                    }
                )
            events = [
                {
                    "time": _stamp(ev.event_time),
                    "event": ev.event_type,
                    "details": json.dumps(ev.after_values, default=str)[:80]
                    if ev.after_values
                    else "",
                    "dot": "#F59E0B" if "EXCLU" in ev.event_type else "#3B82F6",
                }
                for ev in detail["events"]
            ]
            fact_view = {
                key: [
                    {
                        "value": str(a["value"]),
                        "status": a["status"],
                        "derivation": a["derivation"],
                        "asserted_at": _stamp(a["asserted_at"]),
                        "current": a["current"],
                    }
                    for a in assertions
                ]
                for key, assertions in facts.items()
            }
            rent_major = (
                f"${listing.monthly_rent_minor // 100:,}"
                if listing.monthly_rent_minor
                else "rent unknown"
            )
            d = {
                "listing_id": str(listing_id),
                "address_line": address.formatted_address if address else "[address unresolved]",
                "locality": address.locality if address else None,
                "rent_major": rent_major,
                "rent_suffix": "/mo" if listing.monthly_rent_minor else "",
                "lifecycle": listing.lifecycle_status,
                "selected": selected,
                "layout_label": _LAYOUT_LABELS.get(listing.layout_class, listing.layout_class),
                "laundry_label": detail["laundry_label"],
                "days_on_market": (datetime.now(tz=UTC) - listing.first_seen_at).days,
                "first_seen": listing.first_seen_at.strftime("%Y-%m-%d"),
                "last_change": listing.last_material_change_at.strftime("%Y-%m-%d"),
                "chips": chips,
                "description": listing.description_current,
                "links": [
                    {
                        "source": link["source"],
                        "url": link["url"],
                        "status": link["status"],
                        "last_seen": _stamp(link["last_seen"]),
                    }
                    for link in detail["links"]
                ],
                "events": events,
                "facts": fact_view,
                "fact_count": sum(len(v) for v in fact_view.values()),
                "units": [
                    {**unit, "current": unit["listing_id"] == str(listing_id)}
                    for unit in units
                ],
                "floor_plans": floor_plans,
                "transit": transit,
                "commutes": commute_cards,
                "destinations": [
                    {"id": str(dest.destination_id), "name": dest.display_name}
                    for dest in destinations
                ],
                "lat": detail["lat"],
            }
            location = (
                {
                    "lat": detail["lat"],
                    "lon": detail["lon"],
                    "label": f"{_LAYOUT_SHORT.get(listing.layout_class, '?')} {rent_major}",
                }
                if detail["lat"] is not None
                else None
            )
        return render(
            "detail.html", request, "inventory", d=d, location_json=json.dumps(location)
        )

    @app.get("/selected", response_class=HTMLResponse)
    def selected_page(request: Request) -> HTMLResponse:
        exported = request.query_params.get("exported")
        with factory() as session:
            rows = queries.inventory(
                session, queries.InventoryFilters(selected_only=True, limit=1000)
            )
            client_presets = [
                {"id": str(p.client_search_preset_id), "label": p.label}
                for p in queries.shortlist_presets(session)
            ]
        inactive = [
            r for r in rows if r["lifecycle"] not in ("ACTIVE", "CANDIDATE", "REAPPEARED")
        ]
        return render(
            "selected.html",
            request,
            "selected",
            rows=rows,
            inactive_count=len(inactive),
            exported=exported,
            client_presets=client_presets,
        )

    @app.get("/clients", response_class=HTMLResponse)
    def clients_page(request: Request) -> HTMLResponse:
        client = request.query_params.get("client")
        with factory() as session:
            all_rows = queries.inventory(
                session, queries.InventoryFilters(has_rent=True, limit=500)
            )
            presets = queries.shortlist_presets(session)
            preset_entries = {
                str(p.client_search_preset_id): queries.shortlist_entries(
                    session, p.client_search_preset_id
                )
                for p in presets
            }
        chosen_id = client if client in preset_entries else (
            str(presets[0].client_search_preset_id) if presets else None
        )
        chosen_entries = None
        chosen_label = None
        chosen_profile: dict[str, Any] = {}
        income_max_rent = None
        if chosen_id is not None:
            raw_entries = [
                entry for entry in preset_entries[chosen_id] if entry["status"] != "REMOVED"
            ]
            chosen_entries = [
                {
                    "listing_id": entry["listing_id"],
                    "address": entry["address"],
                    "layout": _LAYOUT_LABELS.get(str(entry["layout"]), str(entry["layout"])),
                    "rent": (
                        f"${entry['rent_minor'] // 100:,}"
                        if entry["rent_minor"] is not None
                        else "unknown"
                    ),
                    "lifecycle": entry["lifecycle"],
                    "note": entry["note"] or "",
                }
                for entry in raw_entries
            ]
            chosen = next(
                p for p in presets if str(p.client_search_preset_id) == chosen_id
            )
            chosen_label = chosen.label.upper()
            chosen_profile = (chosen.filter_definition or {}).get("client_profile", {})
            income = chosen_profile.get("annual_income")
            if isinstance(income, (int, float)) and income > 0:
                # NYC 40x rule: max sustainable monthly rent.
                income_max_rent = f"${int(income / 40):,}"
        return render(
            "clients.html",
            request,
            "clients",
            all_rows=all_rows,
            presets=[
                {
                    "id": str(p.client_search_preset_id),
                    "label": p.label,
                    "count": len(
                        [
                            entry
                            for entry in preset_entries[str(p.client_search_preset_id)]
                            if entry["status"] != "REMOVED"
                        ]
                    ),
                    "chosen": str(p.client_search_preset_id) == chosen_id,
                }
                for p in presets
            ],
            chosen_id=chosen_id,
            chosen_entries=chosen_entries,
            chosen_label=chosen_label,
            profile=chosen_profile,
            income_max_rent=income_max_rent,
        )

    @app.get("/studio", response_class=HTMLResponse)
    def studio_page(request: Request) -> HTMLResponse:
        with factory() as session:
            rows = queries.inventory(
                session, queries.InventoryFilters(selected_only=True, limit=1000)
            )
        active = [r for r in rows if r["lifecycle"] in ("ACTIVE", "CANDIDATE", "REAPPEARED")]
        return render(
            "studio.html",
            request,
            "studio",
            rows=active,
            draft=None,
            draft_listing_id=request.query_params.get("listing"),
            error=request.query_params.get("error"),
        )

    @app.get("/review")
    def review_redirect() -> RedirectResponse:
        return RedirectResponse("/settings", status_code=303)

    @app.get("/operations")
    def operations_redirect() -> RedirectResponse:
        return RedirectResponse("/settings", status_code=303)

    @app.get("/settings", response_class=HTMLResponse)
    def settings_page(request: Request) -> HTMLResponse:
        with factory() as session:
            candidates = queries.pending_duplicate_candidates(session)
            issues = queries.open_review_issues(session)
        for c in candidates:
            c["evidence_pretty"] = json.dumps(c["evidence"], indent=2, default=str)
        shaped_issues = [
            {
                "issue_id": issue["issue_id"],
                "severity": issue["severity"],
                "type": issue["type"],
                "created": _stamp(issue["created"]),
                "details_pretty": json.dumps(issue["details"], indent=2, default=str),
            }
            for issue in issues
            if issue["type"] != "DUPLICATE_CANDIDATE"
        ]
        with factory() as session:
            runs = queries.recent_refresh_runs(session, limit=15)
            source_runs = queries.source_run_history(session)
            jobs = queries.job_queue_summary(session)

        def shape(rows: list[dict[str, Any]]) -> tuple[list[str], list[dict[str, str]]]:
            if not rows:
                return [], []
            headers = list(rows[0].keys())
            shaped = [
                {
                    k: (
                        _stamp(v)
                        if isinstance(v, datetime)
                        else json.dumps(v, default=str)
                        if isinstance(v, (dict, list))
                        else str(v if v is not None else "—")
                    )
                    for k, v in row.items()
                }
                for row in rows
            ]
            return headers, shaped

        sections = []
        for title, rows, empty, note in (
            ("REFRESH RUNS", runs, "No runs yet.", None),
            (
                "SOURCE RUNS",
                source_runs,
                "No source runs yet.",
                "health_gate=False on search-discovered runs is by design: search "
                "absence never counts as disappearance evidence (B3).",
            ),
            ("JOB QUEUE", jobs, "Queue is empty.", None),
        ):
            headers, shaped = shape(rows)
            sections.append(
                {"title": title, "headers": headers, "rows": shaped, "empty": empty, "note": note}
            )
        return render(
            "settings.html",
            request,
            "settings",
            sections=sections,
            candidates=candidates,
            issues=shaped_issues,
            error=request.query_params.get("error"),
            started=request.query_params.get("started"),
        )

    def _spawn_job(module: str, *extra_args: str) -> None:
        """Launch a pipeline job as a detached local process; progress shows up
        in the Log below (refresh runs / model executions) and the log files."""
        import subprocess

        project_root = Path(__file__).resolve().parents[3]
        subprocess.Popen(  # noqa: S603 - fixed local module names only
            [sys.executable, "-m", module, *extra_args],
            cwd=str(project_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    @app.post("/actions/run-acquisition")
    def run_acquisition() -> RedirectResponse:
        _spawn_job("rental_agent.jobs.weekday_refresh", "--manual")
        return RedirectResponse(
            "/settings?started=Manual+acquisition+run+launched+—+watch+LOG+·+REFRESH+RUNS+below+(takes+a+few+minutes)",
            status_code=303,
        )

    @app.post("/actions/run-enrichment")
    def run_enrichment(force: Annotated[str, Form()] = "") -> RedirectResponse:
        args = ["--force"] if force else []
        _spawn_job("rental_agent.jobs.detail_enrichment", *args)
        return RedirectResponse(
            "/settings?started=Detail+enrichment+launched+—+unchanged+pages+are+"
            + ("re-extracted+(force)" if force else "skipped")
            + "+·+watch+the+log+files",
            status_code=303,
        )

    # -- actions ---------------------------------------------------------------

    @app.post("/actions/select/{listing_id}")
    def toggle_select(
        listing_id: uuid.UUID, next: Annotated[str, Form()] = "/inventory"
    ) -> RedirectResponse:
        with factory() as session:
            current = queries.listing_detail(session, listing_id)
            currently_selected = (
                current is not None
                and current["selection"] is not None
                and current["selection"].selection_status == "SELECTED"
            )
            MarketingSelectionService(session).set_selection(
                canonical_listing_id=listing_id,
                status=SelectionStatus.REMOVED if currently_selected else SelectionStatus.SELECTED,
                actor=settings.operator_id,
                actor_type=ActorType.HUMAN,
            )
            session.commit()
        return RedirectResponse(_safe_next(next, "/inventory"), status_code=303)

    @app.post("/actions/preset")
    def create_preset(label: Annotated[str, Form()]) -> RedirectResponse:
        with factory() as session:
            ClientShortlistService(session).create_preset(
                label=label,
                filter_definition={},
                filter_schema_version="1",
                actor=settings.operator_id,
                actor_type=ActorType.HUMAN,
            )
            session.commit()
        return RedirectResponse("/clients", status_code=303)

    @app.post("/actions/shortlist")
    def add_shortlist_entry(
        preset_id: Annotated[uuid.UUID, Form()],
        listing_id: Annotated[uuid.UUID, Form()],
        note: Annotated[str, Form()] = "",
        next: Annotated[str, Form()] = "",
    ) -> RedirectResponse:
        with factory() as session:
            ClientShortlistService(session).set_entry(
                client_search_preset_id=preset_id,
                canonical_listing_id=listing_id,
                status=ShortlistEntryStatus.INCLUDED,
                actor=settings.operator_id,
                actor_type=ActorType.HUMAN,
                note=note or None,
            )
            session.commit()
        return RedirectResponse(
            _safe_next(next, f"/clients?client={preset_id}"), status_code=303
        )

    @app.post("/actions/remove-entry")
    def remove_shortlist_entry(
        preset_id: Annotated[uuid.UUID, Form()],
        listing_id: Annotated[uuid.UUID, Form()],
    ) -> RedirectResponse:
        with factory() as session:
            ClientShortlistService(session).set_entry(
                client_search_preset_id=preset_id,
                canonical_listing_id=listing_id,
                status=ShortlistEntryStatus.REMOVED,
                actor=settings.operator_id,
                actor_type=ActorType.HUMAN,
            )
            session.commit()
        return RedirectResponse(f"/clients?client={preset_id}", status_code=303)

    @app.post("/actions/client-profile/{preset_id}")
    async def update_client_profile(preset_id: uuid.UUID, request: Request) -> RedirectResponse:
        form = await request.form()
        profile: dict[str, Any] = {"schema_version": 1}
        for key in (
            "budget_min",
            "budget_max",
            "annual_income",
            "household_size",
        ):
            raw = str(form.get(key) or "").replace(",", "").strip()
            if raw.isdigit() and int(raw) > 0:
                profile[key] = int(raw)
        layouts = [str(v) for v in form.getlist("layouts") if v in ("Studio", "1BR", "2BR")]
        if layouts:
            profile["layouts"] = layouts
        if str(form.get("gender") or "") in ("male", "female"):
            profile["gender"] = str(form.get("gender"))
        for key in ("pets", "guarantor"):
            if str(form.get(key) or "") in ("yes", "no"):
                profile[key] = str(form.get(key))
        for key in ("areas", "move_in", "notes"):
            value = str(form.get(key) or "").strip()
            if value:
                profile[key] = value
        with factory() as session:
            ClientShortlistService(session).update_profile(
                client_search_preset_id=preset_id,
                profile=profile,
                actor=settings.operator_id,
                actor_type=ActorType.HUMAN,
            )
            session.commit()
        return RedirectResponse(f"/clients?client={preset_id}", status_code=303)

    @app.post("/actions/archive-client/{preset_id}")
    def archive_client(preset_id: uuid.UUID) -> RedirectResponse:
        with factory() as session:
            ClientShortlistService(session).archive_preset(
                client_search_preset_id=preset_id,
                actor=settings.operator_id,
                actor_type=ActorType.HUMAN,
            )
            session.commit()
        return RedirectResponse("/clients", status_code=303)

    @app.post("/actions/export")
    def export_selected(include_inactive: Annotated[str, Form()] = "") -> RedirectResponse:
        from rental_agent.exports.csv_export import export_listings

        with factory() as session:
            rows = queries.inventory(
                session, queries.InventoryFilters(selected_only=True, limit=1000)
            )
            chosen = [
                r
                for r in rows
                if include_inactive or r["lifecycle"] in ("ACTIVE", "CANDIDATE", "REAPPEARED")
            ]
            settings.paths.ensure_exists()
            result = export_listings(
                session,
                settings.paths.exports,
                listing_ids=[uuid.UUID(r["listing_id"]) for r in chosen],
                export_type="selected",
            )
        from urllib.parse import quote

        return RedirectResponse(
            f"/selected?exported={quote(str(result.directory))}", status_code=303
        )

    @app.post("/actions/duplicate/{candidate_id}")
    def resolve_duplicate(
        candidate_id: uuid.UUID, decision: Annotated[str, Form()]
    ) -> RedirectResponse:
        with factory() as session:
            candidates = queries.pending_duplicate_candidates(session)
            match = next(
                (c for c in candidates if c["candidate_id"] == str(candidate_id)), None
            )
            if match is None:
                return RedirectResponse("/settings?error=Candidate+not+found", status_code=303)
            survivor = None
            if decision == "keep_a":
                survivor = uuid.UUID(match["listing_a"])
            elif decision == "keep_b":
                survivor = uuid.UUID(match["listing_b"])
            MergeService(session).resolve_duplicate_candidate(
                candidate_id,
                confirmed_duplicate=decision in ("keep_a", "keep_b"),
                actor=settings.operator_id,
                actor_type=ActorType.HUMAN,
                survivor_listing_id=survivor,
            )
            session.commit()
        return RedirectResponse("/settings", status_code=303)

    @app.post("/actions/resolve-issue/{issue_id}")
    def resolve_issue(issue_id: uuid.UUID, note: Annotated[str, Form()] = "") -> RedirectResponse:
        with factory() as session:
            row = session.get(ReviewIssue, issue_id)
            if row is None:
                return RedirectResponse("/settings?error=Issue+not+found", status_code=303)
            if not note and row.severity == "BLOCKING":
                return RedirectResponse(
                    "/settings?error=Blocking+issues+require+a+resolution+note+(07+%C2%A717.5)",
                    status_code=303,
                )
            row.status = "RESOLVED"
            row.resolved_by = settings.operator_id
            row.resolution_note = note or None
            row.resolved_at = datetime.now(tz=UTC)
            session.commit()
        return RedirectResponse("/settings", status_code=303)

    @app.post("/actions/commute/{listing_id}")
    def research_commute(
        listing_id: uuid.UUID, destination_id: Annotated[uuid.UUID, Form()]
    ) -> RedirectResponse:
        from rental_agent.enrichment.commute.research import CommuteResearchService
        from rental_agent.enrichment.llm.openai_executor import OpenAiLlmExecutor

        key = settings.providers.openai_api_key
        if key is None:
            return RedirectResponse(f"/listing/{listing_id}", status_code=303)
        with factory() as session:
            detail = queries.listing_detail(session, listing_id)
            if detail is None:
                return RedirectResponse("/inventory", status_code=303)
            address = detail["address"]
            origin = f"{address.formatted_address}, {address.locality}" if address else "unknown"
            location_hash = f"addr:{address.address_id}" if address else "addr:none"
            executor = OpenAiLlmExecutor(
                settings.providers.llm_default_model_id,
                settings.providers.llm_default_reasoning_effort,
                api_key=key.get_secret_value(),
            )
            service = CommuteResearchService(
                session,
                executor,
                cache_days=settings.providers.commute_research_cache_days,
            )
            try:
                service.research(
                    canonical_listing_id=listing_id,
                    destination_id=destination_id,
                    origin_description=origin,
                    input_location_hash=location_hash,
                )
                session.commit()
            except Exception:
                session.rollback()
        return RedirectResponse(f"/listing/{listing_id}", status_code=303)

    @app.post("/actions/generate-post", response_class=HTMLResponse)
    def generate_post_action(
        request: Request,
        listing_id: Annotated[uuid.UUID, Form()],
        instructions: Annotated[str, Form()] = "",
    ) -> HTMLResponse:
        from rental_agent.webui.local_llm import LocalLlmUnavailable, generate_post

        with factory() as session:
            detail = queries.listing_detail(session, listing_id)
            if detail is None:
                return RedirectResponse("/studio", status_code=303)  # type: ignore[return-value]
            transit = queries.transit_for_listing(session, listing_id)
            commutes = queries.commutes_for_listing(session, listing_id)
            rows = queries.inventory(
                session, queries.InventoryFilters(selected_only=True, limit=1000)
            )
            listing = detail["listing"]
            address = detail["address"]
            siblings = queries.listings_in_building(session, listing.building_id)
            facts = [
                (
                    f"位置（内部参考，按规则只写区域）: {address.formatted_address}, "
                    f"{address.locality}"
                    if address
                    else "位置: unknown"
                ),
                f"Laundry: {detail['laundry_label']}",
            ]
            for link in detail["links"]:
                facts.append(f"房源链接: {link['url']}")
            rentable = [s for s in siblings if s["rent_minor"] is not None]
            if len(rentable) > 1:
                facts.append("同楼在租房型（挂牌价 gross rent）:")
                for s in rentable:
                    facts.append(
                        f"  {_LAYOUT_LABELS.get(s['layout'], s['layout'])}: {s['rent']}"
                    )
            elif listing.monthly_rent_minor:
                layout_label = _LAYOUT_LABELS.get(listing.layout_class, listing.layout_class)
                facts.append(
                    f"房型与挂牌价: {layout_label} ${listing.monthly_rent_minor // 100:,}"
                )
            else:
                facts.append("挂牌价: unknown")
            # Nearby POI facts: researched from live web sources (owner decision
            # 2026-08-18 — never from the local model's memory). Cached 30 days.
            poi = None
            openai_key = getattr(getattr(settings, "providers", None), "openai_api_key", None)
            if openai_key is not None:
                from rental_agent.enrichment.llm.openai_executor import OpenAiLlmExecutor
                from rental_agent.enrichment.poi.research import NearbyPoiResearchService

                poi_service = NearbyPoiResearchService(
                    session,
                    OpenAiLlmExecutor(
                        settings.providers.llm_default_model_id,
                        settings.providers.llm_default_reasoning_effort,
                        api_key=openai_key.get_secret_value(),
                    ),
                )
                poi = poi_service.get_fresh(listing_id)
                if poi is None and address is not None:
                    poi = poi_service.research(
                        listing_id, f"{address.formatted_address}, {address.locality}, NY area"
                    )
                    session.commit()
            page_facts = queries.fact_history(session, listing_id)
            fee = next((a for a in page_facts.get("fee_status", []) if a["current"]), None)
            if fee and fee["value"] == "NO_FEE":
                facts.append("中介费: 无中介费（房源页面明确标注）")
            amenities_fact = next(
                (a for a in page_facts.get("amenities", []) if a["current"]), None
            )
            if amenities_fact and isinstance(amenities_fact["value"], list):
                facts.append(
                    "楼内设施（房源页面明确列出）: "
                    + ", ".join(str(x) for x in amenities_fact["value"])
                )
            if poi:
                if poi.get("food_categories"):
                    facts.append(
                        "周边餐饮品类（已核实网络来源，只写品类）: "
                        + ", ".join(str(x) for x in poi["food_categories"])
                    )
                if poi.get("stores"):
                    facts.append(
                        "周边超市/商店（已核实网络来源，可写名字）: "
                        + ", ".join(str(x) for x in poi["stores"])
                    )
            if listing.description_current:
                facts.append(f"页面描述原文: {listing.description_current}")
            for t in transit[:4]:
                walk = (
                    f"，步行 {t['walk_min']} 分钟" if t.get("walk_min") is not None else ""
                )
                facts.append(f"地铁站: {t['stop']} ({t['mode']}) {t['straight_line_m']} m{walk}")
            # Posting policy (owner 2026-08-18): only commutes ≤25 min are
            # post-worthy; the fastest (ideally <15 min) lead.
            timed = sorted(
                (
                    c
                    for c in commutes
                    if c["range_min"] is not None
                    and c["range_max"] is not None
                    and c["range_max"] <= 25 * 60
                ),
                key=lambda c: c["range_min"],
            )
            for c in timed[:5]:
                routes = ", ".join(c["routes"] or []) or "线路未记录"
                facts.append(
                    f"通勤（已核实研究，可写）: {c['destination']} "
                    f"{c['range_min'] // 60}-{c['range_max'] // 60} 分钟，线路: {routes}"
                )
        facts_block = (
            "房源信息（已核实，仅使用这些事实）:\n"
            + "\n".join(f"- {fact}" for fact in facts)
            + "\n\n【硬性约束】上面没有提供的信息一律不写，包括："
            "中介费（没提供就一个字不提）、入住时间（没提供就删掉整行）、"
            "免租优惠、楼内设施。凡是标注 unknown 的信息直接省略，不要写“未知”。"
            "周边餐饮/超市/商店：只有上面明确给出“周边餐饮品类”或“周边超市/商店”时才写；"
            "没有给出就整段删掉（包括模板里“周边…随便挑，走路到…”那一行），一个字不写。"
            "学校/通勤：只能写上面“通勤（已核实研究，可写）”列出的地点和分钟数——"
            "这些都在25分钟以内；优先挑15分钟以内的写在前面；上面没列的学校一律不写。"
            "写通勤时注明交通方式（地铁🚇/公交🚌/PATH），按给出的线路判断"
            "（数字或字母线路=地铁，M/Bx/B+数字=公交）。"
            "地铁站名和步行分钟数只用上面提供的。"
        )
        active = [r for r in rows if r["lifecycle"] in ("ACTIVE", "CANDIDATE", "REAPPEARED")]
        try:
            draft = generate_post(facts_block, instructions)
            error = None
        except LocalLlmUnavailable as exc:
            draft = None
            error = str(exc)
        # Deterministic fact-check: claims the verified facts cannot support
        # get flagged for the operator to delete before posting. Checked
        # against the facts alone — the constraint trailer in facts_block
        # mentions these words itself.
        facts_text = "\n".join(facts)
        warnings = []
        if draft:
            for phrase, label in (
                ("入住", "入住时间：数据库中没有已核实的入住日期，这一行请删除或人工核实"),
                ("中介费", "中介费：来源数据未说明，按规则应一个字不提"),
                ("免租", "免租优惠：来源数据未提及，请删除或人工核实"),
                ("洗碗机", "洗碗机：来源数据未提及"),
                ("健身", "健身房：来源数据未提及"),
                ("门卫", "门卫/doorman：来源数据未提及"),
                ("日料", "周边餐饮：日料未经核实来源确认，请删除或核实"),
                ("韩餐", "周边餐饮：韩餐未经核实来源确认，请删除或核实"),
                ("中餐", "周边餐饮：中餐未经核实来源确认，请删除或核实"),
                ("墨西哥", "周边餐饮：墨西哥菜未经核实来源确认"),
                ("意大利", "周边餐饮：意大利菜未经核实来源确认"),
                ("Costco", "周边商店：Costco 未经核实来源确认"),
                ("Whole Foods", "周边商店：Whole Foods 未经核实来源确认"),
                ("Trader", "周边商店：Trader Joe's 未经核实来源确认"),
                ("Target", "周边商店：Target 未经核实来源确认"),
            ):
                if phrase in draft and phrase not in facts_text:
                    warnings.append(label)
        return render(
            "studio.html",
            request,
            "studio",
            rows=active,
            draft=draft,
            draft_listing_id=str(listing_id),
            error=error,
            warnings=warnings,
        )

    @app.get("/api/listing/{listing_id}/card")
    def listing_card_api(listing_id: uuid.UUID) -> dict[str, Any]:
        """Abbreviated property data for the floating map panel (owner decision
        2026-08-18: map selection opens a floating summary; the full detail
        page is reached from the Selected page)."""
        with factory() as session:
            detail = queries.listing_detail(session, listing_id)
            if detail is None:
                return {"found": False}
            listing = detail["listing"]
            address = detail["address"]
            transit = queries.transit_for_listing(session, listing_id)
            units = queries.listings_in_building(session, listing.building_id)
            floor_plans = queries.floor_plans_for_listing(
                session, listing_id, listing.building_id
            )
            selected = (
                detail["selection"] is not None
                and detail["selection"].selection_status == "SELECTED"
            )
            return {
                "found": True,
                "listing_id": str(listing_id),
                "address": address.formatted_address if address else "[address unresolved]",
                "locality": address.locality if address else None,
                "rent": (
                    f"${listing.monthly_rent_minor // 100:,}"
                    if listing.monthly_rent_minor
                    else "rent unknown"
                ),
                "layout": _LAYOUT_LABELS.get(listing.layout_class, listing.layout_class),
                "lifecycle": listing.lifecycle_status,
                "laundry": detail["laundry_label"],
                "selected": selected,
                "days_on_market": (datetime.now(tz=UTC) - listing.first_seen_at).days,
                "floor_plan": bool(floor_plans),
                "source_url": detail["links"][0]["url"] if detail["links"] else None,
                "units": [
                    {
                        "listing_id": u["listing_id"],
                        "label": _LAYOUT_LABELS.get(u["layout"], u["layout"]),
                        "rent": u["rent"],
                    }
                    for u in units
                ],
                "transit": [
                    {
                        "stop": t["stop"],
                        "mode": t["mode"],
                        "walk_min": t["walk_min"],
                        "distance_m": t["walking_m"] or t["straight_line_m"],
                    }
                    for t in transit[:3]
                ],
            }

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        with factory() as session:
            session.execute(sql_text("SELECT 1"))
        return {"status": "ok"}

    return app


app = create_app()
