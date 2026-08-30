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
from zoneinfo import ZoneInfo

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
    ("/company", "company", "Company Portfolio", "Company", "domain"),
    ("/clients", "clients", "Clients", "Clients", "group"),
    ("/selected", "selected", "Selected", "Selected", "ad_units"),
    ("/studio", "studio", "Studio", "Studio", "edit_note"),
]
# Kinetic Mapview tertiary — the company-property accent on maps and chips.
_COMPANY_ACCENT = "#943700"
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


# Display timezone (owner check 2026-08-29): the DB session hands back
# UTC-aware datetimes, which the UI used to print verbatim — 4-5h ahead of
# local. Matches Settings.timezone's America/New_York default (08 §6).
_TZ = ZoneInfo("America/New_York")


def _local(value: datetime) -> datetime:
    return value.astimezone(_TZ) if value.tzinfo is not None else value


def _stamp(value: datetime | None) -> str:
    return _local(value).strftime("%m-%d %H:%M") if value else "—"


def _safe_next(raw: str | None, fallback: str) -> str:
    return raw if raw and raw.startswith("/") and not raw.startswith("//") else fallback


# Shared by the listing and company post generators (owner 2026-08-30:
# company properties go through the same Studio).
def _facts_block(facts: list[str]) -> str:
    return (
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
        "语言：全文自然中文。除品牌名（Whole Foods、Trader Joe's、Costco 等）、"
        "地铁线路字母/数字、车站名和 PATH 外，正文不得出现任何英文单词；"
        "设施和餐饮一律用上面给出的中文说法。"
    )


def _fact_check_warnings(draft: str | None, facts_text: str) -> list[str]:
    """Deterministic fact-check: claims the verified facts cannot support get
    flagged for the operator to delete before posting. Checked against the
    facts alone — the constraint trailer mentions these words itself."""
    warnings: list[str] = []
    if not draft:
        return warnings
    # University/commute line without any verified commute facts = invented.
    if "通勤（已核实研究，可写）" not in facts_text and ("🎓" in draft or "分钟" in draft):
        warnings.append(
            "学校/通勤：本房源没有已核实的通勤研究数据，"
            "文中所有“X分钟”和🎓整行都是编造的，请删除"
            "（可先在房源详情页运行通勤研究）"
        )
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
    return warnings


def _shape_commute_cards(commutes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One card shape for listing AND company detail pages."""
    cards = []
    for c in commutes:
        if c["range_min"] is not None:
            rng = f"{c['range_min'] // 60}–{c['range_max'] // 60}m"
        else:
            rng = "n/a"
        conf = str(c["confidence"] or "UNKNOWN")
        cards.append(
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
    return cards


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


def _group_by_building(
    rows: list[dict[str, Any]], company_buildings: set[str] | None = None
) -> list[dict[str, Any]]:
    """One property per building: units listed, rent shown as a range (owner
    decision 2026-08-18 — no overlapping markers for multi-unit buildings).
    Buildings in ``company_buildings`` are flagged (and highlighted on the map)
    as company portfolio properties."""
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
        prop["company"] = bool(company_buildings) and prop["building_id"] in (
            company_buildings or set()
        )
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
                "company": prop["company"],
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
                last_refresh = _local(stamp).strftime("%Y-%m-%d %H:%M")
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
        from sqlalchemy import select as _select

        from rental_agent.db.models import CompanyProperty

        with factory() as session:
            rows = queries.inventory(session, filters)
            counts = queries.laundry_counts(session)
            client_presets = [
                {"id": str(p.client_search_preset_id), "label": p.label}
                for p in queries.shortlist_presets(session)
            ]
            company_rows = session.execute(_select(CompanyProperty)).scalars().all()
            company_buildings = {
                str(r.matched_building_id)
                for r in company_rows
                if r.matched_building_id is not None
            }
            selected_company = queries.selected_company_ids(session)
            company_data = []
            for r in company_rows:
                if r.latitude is None:
                    continue
                availability = r.availability or {}
                unit_labels = []
                rents = []
                for u in availability.get("available_units", [])[:8]:
                    rent = u.get("monthly_rent_usd")
                    if rent:
                        rents.append(int(rent))
                    unit_labels.append(
                        {
                            "label": str(u.get("layout") or u.get("unit_label") or "unit"),
                            "rent": f"${rent:,}" if rent else "",
                            "when": str(u.get("availability_text") or "").strip(),
                        }
                    )
                if rents and min(rents) != max(rents):
                    rent_label = f"${min(rents):,}–${max(rents):,}"
                elif rents:
                    rent_label = f"${rents[0]:,}"
                else:
                    rent_label = ""
                # Marker badge shows the same compact info as listing markers
                # ("$3.4k", "3u $6.4k–$8.4k") — the NAME lives in the detail
                # panel, like regular properties (owner feedback 2026-08-29).
                unit_total = len(availability.get("available_units", []))
                if rents and unit_total > 1:
                    marker_label = (
                        f"{unit_total}u {_kfmt(min(rents) * 100)}–{_kfmt(max(rents) * 100)}"
                    )
                elif rents:
                    marker_label = _kfmt(rents[0] * 100)
                elif unit_total:
                    marker_label = f"{unit_total}u"
                else:
                    marker_label = ""
                page_name = str(availability.get("page_property_name") or "").strip()
                company_data.append(
                    {
                        "id": str(r.company_property_id),
                        "name": r.name,
                        "page_name": (
                            page_name
                            if page_name and page_name.lower() != r.name.lower()
                            else None
                        ),
                        "lat": r.latitude,
                        "lon": r.longitude,
                        "url": r.resolved_url or r.original_url,
                        "address": ", ".join(
                            p for p in (r.address_text, r.locality) if p
                        ),
                        "units": unit_total,
                        "unit_list": unit_labels,
                        "rent_label": rent_label,
                        "marker_label": marker_label,
                        "selected": str(r.company_property_id) in selected_company,
                        "no_units_stated": availability.get("no_units_stated", False),
                        "checked": r.check_status == "CHECKED",
                        "last_checked": _stamp(r.last_checked_at),
                        "building": str(r.matched_building_id) if r.matched_building_id else None,
                    }
                )
        for row in rows:
            row["warn"] = row["lifecycle"] in _WARN_LIFECYCLES
            row["layout_label"] = _LAYOUT_LABELS.get(row["layout"], row["layout"])
            laundry_text = str(row["laundry"])
            row["laundry_chip"] = "" if laundry_text == "Laundry unknown" else laundry_text
        properties = _group_by_building(rows, company_buildings)
        markers = [p["marker"] for p in properties if p["marker"] is not None]
        # Standalone company markers: geocoded portfolio properties whose
        # building is not on the map right now (matched-and-displayed ones are
        # highlighted on their listing marker instead).
        displayed_buildings = {p["building_id"] for p in properties if p["marker"] is not None}
        company_markers = [
            {k: v for k, v in c.items() if k != "building"}
            for c in company_data
            if c["building"] is None or c["building"] not in displayed_buildings
        ]
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
            company_markers_json=json.dumps(company_markers),
            company_accent=_COMPANY_ACCENT,
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
            from sqlalchemy import select as _select

            from rental_agent.db.models import CompanyProperty

            company_row = session.execute(
                _select(
                    CompanyProperty.name, CompanyProperty.company_property_id
                ).where(CompanyProperty.matched_building_id == listing.building_id)
            ).first()
            company_name = company_row[0] if company_row else None
            company_id = str(company_row[1]) if company_row else None
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
            commute_cards = _shape_commute_cards(commutes)
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
                "company": company_name,
                "company_id": company_id,
                "address_line": address.formatted_address if address else "[address unresolved]",
                "locality": address.locality if address else None,
                "rent_major": rent_major,
                "rent_suffix": "/mo" if listing.monthly_rent_minor else "",
                "lifecycle": listing.lifecycle_status,
                "selected": selected,
                "layout_label": _LAYOUT_LABELS.get(listing.layout_class, listing.layout_class),
                "laundry_label": detail["laundry_label"],
                "days_on_market": (datetime.now(tz=UTC) - listing.first_seen_at).days,
                "first_seen": _local(listing.first_seen_at).strftime("%Y-%m-%d"),
                "last_change": _local(listing.last_material_change_at).strftime("%Y-%m-%d"),
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
            company_rows = queries.selected_company_properties(session)
        inactive = [
            r for r in rows if r["lifecycle"] not in ("ACTIVE", "CANDIDATE", "REAPPEARED")
        ]
        return render(
            "selected.html",
            request,
            "selected",
            rows=rows,
            company_rows=company_rows,
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
                    "company_id": entry.get("company_id"),
                    "url": entry.get("url"),
                    "address": entry["address"],
                    "layout": _LAYOUT_LABELS.get(str(entry["layout"]), str(entry["layout"])),
                    "rent": (
                        f"${entry['rent_minor'] // 100:,}"
                        + ("+" if entry.get("company_id") else "")
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
            error=request.query_params.get("error"),
            started=request.query_params.get("started"),
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
            company_rows = queries.selected_company_properties(session)
        active = [r for r in rows if r["lifecycle"] in ("ACTIVE", "CANDIDATE", "REAPPEARED")]
        return render(
            "studio.html",
            request,
            "studio",
            rows=active,
            company_rows=company_rows,
            draft=None,
            draft_listing_id=request.query_params.get("listing"),
            error=request.query_params.get("error"),
        )

    @app.get("/review")
    def review_redirect() -> RedirectResponse:
        return RedirectResponse("/settings?section=review", status_code=303)

    @app.get("/operations")
    def operations_redirect() -> RedirectResponse:
        return RedirectResponse("/settings?section=logs", status_code=303)

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
        providers = getattr(settings, "providers", None)
        key = getattr(providers, "openai_api_key", None) if providers is not None else None
        llm_config = {
            "has_key": key is not None,
            "key_hint": ("…" + key.get_secret_value()[-4:]) if key is not None else "",
            "base_url": (getattr(providers, "llm_base_url", None) or "")
            if providers is not None
            else "",
            "model": getattr(providers, "llm_default_model_id", "")
            if providers is not None
            else "",
        }
        # Apple-settings style: one topic shown at a time (owner request
        # 2026-08-29); ?section= picks it, review shows an attention badge.
        active_section = request.query_params.get("section") or "refresh"
        if active_section not in ("refresh", "llm", "review", "logs"):
            active_section = "refresh"
        review_count = len(candidates) + len(shaped_issues)
        nav_sections = [
            {"key": "refresh", "label": "Data Refresh", "icon": "sync", "badge": None},
            {"key": "llm", "label": "LLM API", "icon": "smart_toy", "badge": None},
            {
                "key": "review",
                "label": "Data Review",
                "icon": "rule",
                "badge": review_count or None,
            },
            {"key": "logs", "label": "Logs", "icon": "receipt_long", "badge": None},
        ]
        return render(
            "settings.html",
            request,
            "settings",
            sections=sections,
            candidates=candidates,
            issues=shaped_issues,
            llm_config=llm_config,
            active_section=active_section,
            nav_sections=nav_sections,
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
            "/settings?section=logs&started=Manual+acquisition+run+launched+—+watch+LOG+·+REFRESH+RUNS+below+(takes+a+few+minutes)",
            status_code=303,
        )

    @app.post("/actions/run-enrichment")
    def run_enrichment(force: Annotated[str, Form()] = "") -> RedirectResponse:
        args = ["--force"] if force else []
        _spawn_job("rental_agent.jobs.detail_enrichment", *args)
        return RedirectResponse(
            "/settings?section=refresh&started=Detail+enrichment+launched+—+unchanged+pages+are+"
            + ("re-extracted+(force)" if force else "skipped")
            + "+·+watch+the+log+files",
            status_code=303,
        )

    # -- company property portfolio (owner request 2026-08-29) -----------------

    def _company_upload_dir() -> Path:
        paths = getattr(settings, "paths", None)
        root = paths.raw if paths is not None else Path("local_data") / "raw"
        directory = root / "company"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    @app.get("/company", response_class=HTMLResponse)
    def company_page(request: Request) -> HTMLResponse:
        from sqlalchemy import select as _select

        from rental_agent.db.models import CompanyProperty

        with factory() as session:
            rows = (
                session.execute(_select(CompanyProperty).order_by(CompanyProperty.name))
                .scalars()
                .all()
            )
            selected_company = queries.selected_company_ids(session)
            shaped = []
            for r in rows:
                availability = r.availability or {}
                units = availability.get("available_units", [])
                unit_bits = []
                for u in units[:6]:
                    label = str(u.get("layout") or u.get("unit_label") or "unit")
                    rent = u.get("monthly_rent_usd")
                    unit_bits.append(f"{label} ${rent:,}" if rent else label)
                page_name = str(availability.get("page_property_name") or "").strip()
                shaped.append(
                    {
                        "id": str(r.company_property_id),
                        "name": r.name,
                        "selected": str(r.company_property_id) in selected_company,
                        "page_name": (
                            page_name
                            if page_name and page_name.lower() != r.name.lower()
                            else None
                        ),
                        "url": r.resolved_url or r.original_url,
                        "url_kind": r.resolved_url_kind,
                        "link_status": r.link_status,
                        "address": r.address_text,
                        "locality": r.locality,
                        "mapped": r.latitude is not None,
                        "matched": r.matched_building_id is not None,
                        "check_status": r.check_status,
                        "check_error": r.check_error,
                        "last_checked": _stamp(r.last_checked_at),
                        "units": unit_bits,
                        "unit_count": len(units),
                        "no_units_stated": availability.get("no_units_stated", False),
                        "evidence": availability.get("evidence", ""),
                        "source_document": r.source_document,
                    }
                )
        # Aggregated review groups (owner request 2026-08-29): failed links
        # first — they are the ones needing attention — then working, then
        # never-checked.
        failed_rows = [r for r in shaped if r["check_status"] == "FAILED"]
        working_rows = [r for r in shaped if r["check_status"] == "CHECKED"]
        pending_rows = [
            r for r in shaped if r["check_status"] not in ("CHECKED", "FAILED")
        ]
        groups = [
            {
                "key": "failed",
                "title": f"FAILED LINKS — NEEDS REVIEW ({len(failed_rows)})",
                "rows": failed_rows,
                "tone": "error",
            },
            {
                "key": "working",
                "title": f"WORKING LINKS ({len(working_rows)})",
                "rows": working_rows,
                "tone": "ok",
            },
            {
                "key": "pending",
                "title": f"NOT CHECKED YET ({len(pending_rows)})",
                "rows": pending_rows,
                "tone": "muted",
            },
        ]
        return render(
            "company.html",
            request,
            "company",
            groups=[g for g in groups if g["rows"]],
            total=len(shaped),
            checked_count=len(working_rows),
            failed_count=len(failed_rows),
            unit_total=sum(r["unit_count"] for r in shaped),
            error=request.query_params.get("error"),
            started=request.query_params.get("started"),
        )

    @app.get("/company/{company_property_id}", response_class=HTMLResponse)
    def company_detail(request: Request, company_property_id: uuid.UUID) -> HTMLResponse:
        """Dedicated detail page for a company property (owner request
        2026-08-30) — same structure as the listing detail page."""
        from sqlalchemy import select as _select

        from rental_agent.db.models import CompanyProperty, MarketingSelection

        with factory() as session:
            prop = session.get(CompanyProperty, company_property_id)
            if prop is None:
                return RedirectResponse("/company", status_code=303)  # type: ignore[return-value]
            availability = prop.availability or {}
            units = []
            rents = []
            for u in availability.get("available_units", []):
                rent = u.get("monthly_rent_usd")
                if rent:
                    rents.append(int(rent))
                units.append(
                    {
                        "label": str(u.get("layout") or u.get("unit_label") or "unit"),
                        "unit_label": str(u.get("unit_label") or ""),
                        "rent": f"${rent:,}" if rent else "rent unstated",
                        "when": str(u.get("availability_text") or "").strip(),
                    }
                )
            if rents and min(rents) != max(rents):
                rent_major, rent_suffix = f"${min(rents):,}–${max(rents):,}", "/mo"
            elif rents:
                rent_major, rent_suffix = f"${rents[0]:,}", "/mo"
            elif prop.check_status == "CHECKED":
                rent_major, rent_suffix = "no units advertised", ""
            else:
                rent_major, rent_suffix = "not checked yet", ""
            selected = (
                session.execute(
                    _select(MarketingSelection.selection_status).where(
                        MarketingSelection.company_property_id == company_property_id
                    )
                ).scalar()
                == "SELECTED"
            )
            client_presets = [
                {"id": str(p.client_search_preset_id), "label": p.label}
                for p in queries.shortlist_presets(session)
            ]
            # Routed walking stored by the check job (04 §12: minutes only
            # ever come from the router); live straight-line lookup is the
            # meters-only fallback until a check has routed this property.
            stored_transit = availability.get("nearby_transit")
            if stored_transit:
                transit = [dict(t) for t in stored_transit]
            elif prop.latitude is not None and prop.longitude is not None:
                transit = queries.transit_near_point(
                    session, prop.latitude, prop.longitude
                )
            else:
                transit = []
            if prop.latitude is not None:
                from urllib.parse import quote as _quote

                for t in transit:
                    destination = _quote(f"{t['stop']} station, New York")
                    t["gmaps_url"] = (
                        "https://www.google.com/maps/dir/?api=1"
                        f"&origin={prop.latitude},{prop.longitude}"
                        f"&destination={destination}&travelmode=walking"
                    )
            inventory_units = (
                queries.listings_in_building(session, prop.matched_building_id)
                if prop.matched_building_id is not None
                else []
            )
            commute_cards = _shape_commute_cards(
                queries.commutes_for_company(session, company_property_id)
            )
            destinations = queries.active_destinations(session)
            links = []
            if prop.original_url:
                links.append(
                    {
                        "source": f"company file ({prop.source_document})",
                        "url": prop.original_url,
                        "status": prop.link_status if prop.resolved_url is None else (
                            "OK" if prop.resolved_url == prop.original_url else "SUPERSEDED"
                        ),
                        "last_seen": _stamp(prop.last_checked_at),
                    }
                )
            if prop.resolved_url and prop.resolved_url != prop.original_url:
                links.append(
                    {
                        "source": f"agent-repaired ({prop.resolved_url_kind or 'unknown'})",
                        "url": prop.resolved_url,
                        "status": prop.link_status,
                        "last_seen": _stamp(prop.last_checked_at),
                    }
                )
            page_name = str(availability.get("page_property_name") or "").strip()
            # Listing-detail parity (07 §11): laundry with evidence state,
            # amenity/fee chips, description, floor plan, check history.
            laundry_type = str(availability.get("laundry_type") or "UNKNOWN")
            chips = []
            if availability.get("fee_status") == "NO_FEE":
                chips.append("No fee (page-stated)")
            chips.extend(str(a) for a in (availability.get("amenities") or [])[:10])
            history = [
                {
                    "time": _stamp(datetime.fromisoformat(entry["at"]))
                    if entry.get("at")
                    else "—",
                    "event": entry.get("event", ""),
                    "details": (
                        f"{entry.get('unit_count', 0)} units"
                        + (
                            f" · ${entry['min_rent']:,}–${entry['max_rent']:,}"
                            if entry.get("min_rent")
                            else ""
                        )
                    ),
                }
                for entry in (prop.check_log or [])
            ]
            evidence_facts = {
                key: value
                for key, value in (
                    ("availability", availability.get("evidence")),
                    ("laundry", availability.get("laundry_evidence")),
                    ("fee", availability.get("fee_evidence")),
                    (
                        "amenities (web-researched)",
                        ", ".join(availability.get("amenities_sources") or []),
                    ),
                )
                if value
            }
            d = {
                "company_id": str(company_property_id),
                "days_in_portfolio": (datetime.now(tz=UTC) - prop.created_at).days,
                "laundry_label": queries.laundry_label(laundry_type, False),
                "laundry_unknown": laundry_type == "UNKNOWN",
                "chips": chips,
                "description": availability.get("description"),
                "floor_plan_present": availability.get("floor_plan_present", False),
                "floor_plan_url": availability.get("floor_plan_url"),
                "history": history,
                "evidence_facts": evidence_facts,
                "name": prop.name,
                "page_name": (
                    page_name
                    if page_name and page_name.lower() != prop.name.lower()
                    else None
                ),
                "address_line": prop.address_text or "[address unresolved]",
                "locality": prop.locality,
                "rent_major": rent_major,
                "rent_suffix": rent_suffix,
                "selected": selected,
                "check_status": prop.check_status,
                "check_error": prop.check_error,
                "link_status": prop.link_status,
                "url_kind": prop.resolved_url_kind,
                "url": prop.resolved_url or prop.original_url,
                "units": units,
                "no_units_stated": availability.get("no_units_stated", False),
                "page_confirmed": availability.get("page_is_this_property", False),
                "evidence": availability.get("evidence", ""),
                "snapshot_stamp": (
                    _stamp(datetime.fromisoformat(availability["checked_at"]))
                    if availability.get("checked_at")
                    else ""
                ),
                "last_checked": _stamp(prop.last_checked_at),
                "added": _stamp(prop.created_at),
                "source_document": prop.source_document,
                "links": links,
                "inventory_units": inventory_units,
                "transit": transit,
                "commutes": commute_cards,
                "destinations": [
                    {"id": str(dest.destination_id), "name": dest.display_name}
                    for dest in destinations
                ],
                "lat": prop.latitude,
            }
            if rents and min(rents) != max(rents):
                marker_text = f"★ {_kfmt(min(rents) * 100)}–{_kfmt(max(rents) * 100)}"
            elif rents:
                marker_text = f"★ {_kfmt(rents[0] * 100)}"
            else:
                marker_text = "★"
            location = (
                {"lat": prop.latitude, "lon": prop.longitude, "label": marker_text}
                if prop.latitude is not None
                else None
            )
        return render(
            "company_detail.html",
            request,
            "company",
            d=d,
            client_presets=client_presets,
            location_json=json.dumps(location),
        )

    @app.post("/actions/company-upload")
    async def company_upload(request: Request) -> RedirectResponse:
        from urllib.parse import quote

        from sqlalchemy import select as _select

        from rental_agent.db.models import CompanyProperty
        from rental_agent.enrichment.company.portfolio import (
            extract_entries,
            name_fingerprint,
            parse_company_document,
        )

        form = await request.form()
        upload = form.get("file")
        filename = getattr(upload, "filename", "") or ""
        suffix = Path(filename).suffix.lower()
        if not filename or suffix not in (".docx", ".pdf"):
            return RedirectResponse(
                "/company?error=Upload+a+.docx+or+.pdf+company+file", status_code=303
            )
        safe_name = Path(filename).name
        destination = _company_upload_dir() / safe_name
        destination.write_bytes(await upload.read())  # type: ignore[union-attr]
        try:
            doc = parse_company_document(destination)
        except Exception:  # noqa: BLE001 - corrupt uploads get a friendly error
            return RedirectResponse(
                f"/company?error=Could+not+parse+{quote(safe_name)}+—+is+it+a+valid+file%3F",
                status_code=303,
            )
        llm = None
        providers = getattr(settings, "providers", None)
        if providers is not None and getattr(providers, "openai_api_key", None) is not None:
            from rental_agent.enrichment.llm.openai_executor import executor_from_settings

            llm = executor_from_settings(providers)
        entries, method = extract_entries(doc, llm)
        if not entries:
            return RedirectResponse(
                "/company?error=No+properties+found+in+the+file+(need+names+with+links)",
                status_code=303,
            )
        added = updated = 0
        with factory() as session:
            for entry in entries:
                fingerprint = name_fingerprint(entry.name)
                existing = session.execute(
                    _select(CompanyProperty).where(
                        CompanyProperty.name_fingerprint == fingerprint
                    )
                ).scalar_one_or_none()
                if existing is None:
                    session.add(
                        CompanyProperty(
                            name=entry.name,
                            name_fingerprint=fingerprint,
                            source_document=safe_name,
                            original_url=entry.url,
                            address_text=entry.address,
                        )
                    )
                    added += 1
                else:
                    existing.source_document = safe_name
                    if entry.url and entry.url != existing.original_url:
                        # The file's link changed: restart from it next check.
                        existing.original_url = entry.url
                        existing.resolved_url = None
                        existing.resolved_url_kind = None
                        existing.link_status = "UNCHECKED"
                        existing.check_status = "PENDING"
                    if entry.address and not existing.address_text:
                        existing.address_text = entry.address
                    updated += 1
            session.commit()
        message = (
            f"{safe_name}: {added} added, {updated} updated ({method} parse). "
            "Run “Check availability now” to fetch units."
        )
        return RedirectResponse(f"/company?started={quote(message)}", status_code=303)

    def _company_status_file() -> Path:
        from rental_agent.jobs.company_refresh import status_path

        return status_path(getattr(getattr(settings, "paths", None), "logs", None))

    @app.post("/actions/company-check")
    def company_check(
        force: Annotated[str, Form()] = "", failed_only: Annotated[str, Form()] = ""
    ) -> RedirectResponse:
        from rental_agent.jobs.company_refresh import write_status

        args = (["--force"] if force else []) + (["--failed-only"] if failed_only else [])
        # Seed the live indicator before the detached job's first heartbeat.
        write_status(
            _company_status_file(),
            state="launching",
            mode="failed_only" if failed_only else ("force" if force else "all"),
        )
        _spawn_job("rental_agent.jobs.company_refresh", *args)
        label = "Re-check+of+failed+properties" if failed_only else "Availability+check"
        return RedirectResponse(
            f"/company?started={label}+launched+—+the+status+pill+above+tracks+"
            "progress+live",
            status_code=303,
        )

    @app.get("/api/company/status")
    def company_status() -> dict[str, Any]:
        """Live condition for the Company page's single status indicator."""
        path = _company_status_file()
        if not path.exists():
            return {"state": "idle"}
        try:
            data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"state": "idle"}
        data.setdefault("state", "idle")
        data["stalled"] = False
        for key in ("updated_at", "finished_at"):
            raw = data.get(key)
            if not raw:
                continue
            try:
                parsed = datetime.fromisoformat(raw)
            except ValueError:
                continue
            data[key.replace("_at", "_stamp")] = _stamp(parsed)
            if key == "updated_at" and data["state"] in ("launching", "running"):
                # A detached job that died mid-run stops heartbeating; after
                # 4 quiet minutes the indicator says so instead of spinning.
                data["stalled"] = (datetime.now(tz=UTC) - parsed).total_seconds() > 240
        return data

    @app.post("/actions/company-delete/{property_id}")
    def company_delete(property_id: uuid.UUID) -> RedirectResponse:
        from rental_agent.db.models import CompanyProperty

        with factory() as session:
            row = session.get(CompanyProperty, property_id)
            if row is not None:
                session.delete(row)
                session.commit()
        return RedirectResponse("/company", status_code=303)

    # -- owner LLM API configuration (owner request 2026-08-29) ----------------

    @app.post("/actions/llm-config")
    def save_llm_config(
        api_key: Annotated[str, Form()] = "",
        base_url: Annotated[str, Form()] = "",
        model: Annotated[str, Form()] = "",
        clear_key: Annotated[str, Form()] = "",
    ) -> RedirectResponse:
        import os
        from urllib.parse import quote, urlparse

        from pydantic import SecretStr

        from rental_agent.config.env_file import update_env_file

        api_key = api_key.strip()
        base_url = base_url.strip().rstrip("/")
        model = model.strip()
        if base_url and urlparse(base_url).scheme not in ("http", "https"):
            return RedirectResponse(
                "/settings?section=llm&error=Base+URL+must+start+with+http(s)://", status_code=303
            )
        values: dict[str, str | None] = {
            "RENTAL_PROVIDER_LLM_BASE_URL": base_url or None,
            "RENTAL_PROVIDER_LLM_DEFAULT_MODEL_ID": model or None,
        }
        if clear_key:
            values["RENTAL_PROVIDER_OPENAI_API_KEY"] = None
        elif api_key:
            values["RENTAL_PROVIDER_OPENAI_API_KEY"] = api_key
        update_env_file(Path(".env"), values)
        # Spawned jobs inherit os.environ, which outranks .env — keep it in sync.
        for env_key, value in values.items():
            if value is None:
                os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = value
        providers = getattr(settings, "providers", None)
        if providers is not None:
            if clear_key:
                providers.openai_api_key = None
            elif api_key:
                providers.openai_api_key = SecretStr(api_key)
            providers.llm_base_url = base_url or None
            if model:
                providers.llm_default_model_id = model
        # Cheap reachability probe (models listing — no tokens billed).
        note = ""
        effective_key = api_key or (
            providers.openai_api_key.get_secret_value()
            if providers is not None and getattr(providers, "openai_api_key", None)
            else ""
        )
        if not clear_key and effective_key:
            import httpx

            probe_url = (base_url or "https://api.openai.com/v1") + "/models"
            try:
                probe = httpx.get(
                    probe_url,
                    headers={"Authorization": f"Bearer {effective_key}"},
                    timeout=8.0,
                )
                note = (
                    " · endpoint verified"
                    if probe.status_code == 200
                    else f" · warning: endpoint answered HTTP {probe.status_code}"
                )
            except httpx.HTTPError:
                note = " · warning: endpoint unreachable"
        message = ("LLM API key removed" if clear_key else "LLM API settings saved") + note
        return RedirectResponse(f"/settings?section=llm&started={quote(message)}", status_code=303)

    # -- actions ---------------------------------------------------------------

    @app.post("/actions/company-select/{company_property_id}")
    def toggle_company_select(
        company_property_id: uuid.UUID, next: Annotated[str, Form()] = "/inventory"
    ) -> RedirectResponse:
        """Select-for-Ad toggle for company portfolio properties (owner
        request 2026-08-30) — same audited service as listings."""
        from sqlalchemy import select as _select

        from rental_agent.db.models import MarketingSelection

        with factory() as session:
            current = session.execute(
                _select(MarketingSelection.selection_status).where(
                    MarketingSelection.company_property_id == company_property_id
                )
            ).scalar()
            MarketingSelectionService(session).set_selection(
                company_property_id=company_property_id,
                status=SelectionStatus.REMOVED
                if current == "SELECTED"
                else SelectionStatus.SELECTED,
                actor=settings.operator_id,
                actor_type=ActorType.HUMAN,
            )
            session.commit()
        return RedirectResponse(_safe_next(next, "/inventory"), status_code=303)

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
    def create_preset(label: Annotated[str, Form()] = "") -> RedirectResponse:
        from urllib.parse import quote

        from sqlalchemy import func as _func
        from sqlalchemy import select as _select

        from rental_agent.db.models import ClientSearchPreset

        label = label.strip()
        if not label:
            return RedirectResponse(
                "/clients?error=Client+name+cannot+be+empty", status_code=303
            )
        with factory() as session:
            # Labels are unique (DB constraint): a duplicate used to escape as
            # a 500 (owner report 2026-08-30). Case-insensitive match so
            # "amy"/"Amy" never confuse; an archived match is restored —
            # its shortlist entries and profile come back.
            existing = session.execute(
                _select(ClientSearchPreset).where(
                    _func.lower(ClientSearchPreset.label) == label.lower()
                )
            ).scalars().first()
            if existing is not None and existing.archived_at is None:
                return RedirectResponse(
                    f"/clients?error=Client+%E2%80%9C{quote(existing.label)}%E2%80%9D"
                    "+already+exists",
                    status_code=303,
                )
            if existing is not None:
                ClientShortlistService(session).restore_preset(
                    client_search_preset_id=existing.client_search_preset_id,
                    actor=settings.operator_id,
                    actor_type=ActorType.HUMAN,
                )
                session.commit()
                return RedirectResponse(
                    f"/clients?client={existing.client_search_preset_id}"
                    f"&started=Restored+previously+removed+client+%E2%80%9C"
                    f"{quote(existing.label)}%E2%80%9D+with+its+saved+entries",
                    status_code=303,
                )
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
        listing_id: Annotated[uuid.UUID | None, Form()] = None,
        company_id: Annotated[uuid.UUID | None, Form()] = None,
        note: Annotated[str, Form()] = "",
        next: Annotated[str, Form()] = "",
    ) -> RedirectResponse:
        if (listing_id is None) == (company_id is None):
            return RedirectResponse("/clients", status_code=303)
        with factory() as session:
            ClientShortlistService(session).set_entry(
                client_search_preset_id=preset_id,
                canonical_listing_id=listing_id,
                company_property_id=company_id,
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
        listing_id: Annotated[uuid.UUID | None, Form()] = None,
        company_id: Annotated[uuid.UUID | None, Form()] = None,
    ) -> RedirectResponse:
        if (listing_id is None) == (company_id is None):
            return RedirectResponse("/clients", status_code=303)
        with factory() as session:
            ClientShortlistService(session).set_entry(
                client_search_preset_id=preset_id,
                canonical_listing_id=listing_id,
                company_property_id=company_id,
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
                return RedirectResponse(
                    "/settings?section=review&error=Candidate+not+found", status_code=303
                )
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
        return RedirectResponse("/settings?section=review", status_code=303)

    @app.post("/actions/resolve-issue/{issue_id}")
    def resolve_issue(issue_id: uuid.UUID, note: Annotated[str, Form()] = "") -> RedirectResponse:
        with factory() as session:
            row = session.get(ReviewIssue, issue_id)
            if row is None:
                return RedirectResponse(
                    "/settings?section=review&error=Issue+not+found", status_code=303
                )
            if not note and row.severity == "BLOCKING":
                return RedirectResponse(
                    "/settings?section=review&error=Blocking+issues+require+a+resolution+note+(07+%C2%A717.5)",
                    status_code=303,
                )
            row.status = "RESOLVED"
            row.resolved_by = settings.operator_id
            row.resolution_note = note or None
            row.resolved_at = datetime.now(tz=UTC)
            session.commit()
        return RedirectResponse("/settings?section=review", status_code=303)

    @app.post("/actions/commute/{listing_id}")
    def research_commute(
        listing_id: uuid.UUID, destination_id: Annotated[uuid.UUID, Form()]
    ) -> RedirectResponse:
        from rental_agent.enrichment.commute.research import CommuteResearchService
        from rental_agent.enrichment.llm.openai_executor import executor_from_settings

        providers = getattr(settings, "providers", None)
        if providers is None or getattr(providers, "openai_api_key", None) is None:
            return RedirectResponse(f"/listing/{listing_id}", status_code=303)
        with factory() as session:
            detail = queries.listing_detail(session, listing_id)
            if detail is None:
                return RedirectResponse("/inventory", status_code=303)
            address = detail["address"]
            origin = f"{address.formatted_address}, {address.locality}" if address else "unknown"
            location_hash = f"addr:{address.address_id}" if address else "addr:none"
            executor = executor_from_settings(providers)
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

    @app.post("/actions/company-commute/{company_property_id}")
    def research_company_commute(
        company_property_id: uuid.UUID, destination_id: Annotated[uuid.UUID, Form()]
    ) -> RedirectResponse:
        """On-demand commute research for a company property — same service
        the check job uses (owner request 2026-08-30)."""
        from rental_agent.db.models import CompanyProperty
        from rental_agent.enrichment.commute.research import CommuteResearchService
        from rental_agent.enrichment.llm.openai_executor import executor_from_settings

        providers = getattr(settings, "providers", None)
        if providers is None or getattr(providers, "openai_api_key", None) is None:
            return RedirectResponse(f"/company/{company_property_id}", status_code=303)
        with factory() as session:
            prop = session.get(CompanyProperty, company_property_id)
            if prop is None:
                return RedirectResponse("/company", status_code=303)
            service = CommuteResearchService(
                session,
                executor_from_settings(providers),
                cache_days=providers.commute_research_cache_days,
            )
            try:
                service.research(
                    company_property_id=company_property_id,
                    destination_id=destination_id,
                    origin_description=(
                        f"{prop.address_text or prop.name}, {prop.locality or 'New York'}"
                    ),
                    input_location_hash=(
                        f"company:{company_property_id}:"
                        f"{prop.latitude or 0:.5f},{prop.longitude or 0:.5f}"
                    ),
                )
                session.commit()
            except Exception:
                session.rollback()
        return RedirectResponse(f"/company/{company_property_id}", status_code=303)

    def _generate_company_post(
        request: Request, company_id: uuid.UUID, instructions: str
    ) -> HTMLResponse:
        """Studio draft for a selected company property — same house rules,
        facts assembled from the availability snapshot + researched commutes
        (owner request 2026-08-30)."""
        from rental_agent.db.models import CompanyProperty
        from rental_agent.webui.local_llm import LocalLlmUnavailable, generate_post
        from rental_agent.webui.zh import LAUNDRY_ZH, TRANSIT_MODE_ZH, amenities_zh

        with factory() as session:
            prop = session.get(CompanyProperty, company_id)
            if prop is None:
                return RedirectResponse("/studio", status_code=303)  # type: ignore[return-value]
            availability = prop.availability or {}
            facts = [
                (
                    f"位置（内部参考，按规则只写区域）: "
                    f"{prop.address_text or prop.name}, {prop.locality or ''}"
                ).rstrip(", "),
            ]
            laundry_zh = LAUNDRY_ZH.get(str(availability.get("laundry_type") or ""))
            if laundry_zh:
                facts.append(f"洗衣设施: {laundry_zh}")
            # Owner rule 2026-08-18: NJ apartment buildings charge no broker fee.
            locality_blob = f"{prop.locality or ''}"
            if any(t in locality_blob for t in ("Jersey City", "Hoboken", "Fort Lee")):
                facts.append("中介费: 无中介费（新泽西公寓楼盘均无中介费，业主确认规则）")
            elif availability.get("fee_status") == "NO_FEE":
                facts.append("中介费: 无中介费（房源页面明确标注）")
            translated = amenities_zh(
                [str(a) for a in (availability.get("amenities") or [])]
            )
            if translated:
                facts.append("楼内设施（房源页面明确列出）: " + "、".join(translated))
            url = prop.resolved_url or prop.original_url
            if url:
                facts.append(f"房源链接: {url}")
            units = availability.get("available_units", [])
            if units:
                facts.append("同楼在租房型（挂牌价 gross rent，页面标注的可入住时间）:")
                for u in units:
                    rent = u.get("monthly_rent_usd")
                    label = str(u.get("layout") or u.get("unit_label") or "unit")
                    when = str(u.get("availability_text") or "").strip()
                    line = f"  {label}: " + (f"${rent:,}" if rent else "价格未标注")
                    if when:
                        line += f"（{when}）"
                    facts.append(line)
            if availability.get("description"):
                facts.append(f"页面描述原文: {availability['description']}")
            elif availability.get("evidence"):
                facts.append(f"页面描述原文: {availability['evidence']}")
            for t in (availability.get("nearby_transit") or [])[:4]:
                if t.get("walk_min"):
                    mode_zh = TRANSIT_MODE_ZH.get(str(t.get("mode")), str(t.get("mode")))
                    facts.append(f"{mode_zh}站: {t['stop']}，步行 {t['walk_min']} 分钟")
            commutes = queries.commutes_for_company(session, company_id)
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
            active = [
                r
                for r in queries.inventory(
                    session, queries.InventoryFilters(selected_only=True, limit=1000)
                )
                if r["lifecycle"] in ("ACTIVE", "CANDIDATE", "REAPPEARED")
            ]
            company_rows = queries.selected_company_properties(session)
        try:
            draft = generate_post(_facts_block(facts), instructions)
            error = None
        except LocalLlmUnavailable as exc:
            draft = None
            error = str(exc)
        return render(
            "studio.html",
            request,
            "studio",
            rows=active,
            company_rows=company_rows,
            draft=draft,
            draft_listing_id=f"company:{company_id}",
            error=error,
            warnings=_fact_check_warnings(draft, "\n".join(facts)),
        )

    @app.post("/actions/generate-post", response_class=HTMLResponse)
    def generate_post_action(
        request: Request,
        listing_id: Annotated[str, Form()],
        instructions: Annotated[str, Form()] = "",
    ) -> HTMLResponse:
        from rental_agent.webui.local_llm import LocalLlmUnavailable, generate_post

        # Company properties share the Studio (owner 2026-08-30): their
        # dropdown values are prefixed "company:<id>".
        if listing_id.startswith("company:"):
            try:
                company_id = uuid.UUID(listing_id.removeprefix("company:"))
            except ValueError:
                return RedirectResponse("/studio", status_code=303)  # type: ignore[return-value]
            return _generate_company_post(request, company_id, instructions)
        try:
            target_id = uuid.UUID(listing_id)
        except ValueError:
            return RedirectResponse("/studio", status_code=303)  # type: ignore[return-value]

        with factory() as session:
            detail = queries.listing_detail(session, target_id)
            if detail is None:
                return RedirectResponse("/studio", status_code=303)  # type: ignore[return-value]
            transit = queries.transit_for_listing(session, target_id)
            commutes = queries.commutes_for_listing(session, target_id)
            rows = queries.inventory(
                session, queries.InventoryFilters(selected_only=True, limit=1000)
            )
            from rental_agent.webui.zh import (
                LAUNDRY_ZH,
                TRANSIT_MODE_ZH,
                amenities_zh,
                cuisines_zh,
            )

            listing = detail["listing"]
            address = detail["address"]
            siblings = queries.listings_in_building(session, listing.building_id)
            facts = [
                (
                    f"位置（内部参考，按规则只写区域）: {address.formatted_address}, "
                    f"{address.locality}"
                    if address
                    else "位置: 未知"
                ),
            ]
            laundry_zh = LAUNDRY_ZH.get(listing.laundry_type)
            if laundry_zh:
                facts.append(f"洗衣设施: {laundry_zh}")
            # Owner rule 2026-08-18: NJ apartment buildings charge no broker fee.
            if address and address.locality in ("Jersey City", "Hoboken", "Fort Lee"):
                facts.append("中介费: 无中介费（新泽西公寓楼盘均无中介费，业主确认规则）")
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
                from rental_agent.enrichment.llm.openai_executor import executor_from_settings
                from rental_agent.enrichment.poi.research import NearbyPoiResearchService

                poi_service = NearbyPoiResearchService(
                    session, executor_from_settings(settings.providers)
                )
                poi = poi_service.get_fresh(target_id)
                if poi is None and address is not None:
                    poi = poi_service.research(
                        target_id, f"{address.formatted_address}, {address.locality}, NY area"
                    )
                    session.commit()
            page_facts = queries.fact_history(session, target_id)
            fee = next((a for a in page_facts.get("fee_status", []) if a["current"]), None)
            if fee and fee["value"] == "NO_FEE" and "中介费" not in "".join(facts):
                facts.append("中介费: 无中介费（房源页面明确标注）")
            amenities_fact = next(
                (a for a in page_facts.get("amenities", []) if a["current"]), None
            )
            if amenities_fact and isinstance(amenities_fact["value"], list):
                translated = amenities_zh([str(x) for x in amenities_fact["value"]])
                if translated:
                    facts.append("楼内设施（房源页面明确列出）: " + "、".join(translated))
            if poi:
                if poi.get("food_categories"):
                    food_zh = cuisines_zh([str(x) for x in poi["food_categories"]])
                    if food_zh:
                        facts.append(
                            "周边餐饮品类（已核实网络来源，只写品类）: " + "、".join(food_zh)
                        )
                if poi.get("stores"):
                    # Store names stay as brands (Whole Foods, Costco...) — the
                    # owner's prompt allows named stores in English.
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
                mode_zh = TRANSIT_MODE_ZH.get(str(t["mode"]), str(t["mode"]))
                distance = walk or f"，直线 {t['straight_line_m']} 米"
                facts.append(f"{mode_zh}站: {t['stop']}{distance}")
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
        active = [r for r in rows if r["lifecycle"] in ("ACTIVE", "CANDIDATE", "REAPPEARED")]
        try:
            draft = generate_post(_facts_block(facts), instructions)
            error = None
        except LocalLlmUnavailable as exc:
            draft = None
            error = str(exc)
        warnings = _fact_check_warnings(draft, "\n".join(facts))
        with factory() as session:
            company_rows = queries.selected_company_properties(session)
        return render(
            "studio.html",
            request,
            "studio",
            rows=active,
            company_rows=company_rows,
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
            from sqlalchemy import select as _select

            from rental_agent.db.models import CompanyProperty

            company = session.execute(
                _select(CompanyProperty.name).where(
                    CompanyProperty.matched_building_id == listing.building_id
                )
            ).scalar()
            return {
                "found": True,
                "company": company,
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
