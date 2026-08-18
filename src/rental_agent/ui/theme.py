"""Kinetic Mapview System theme (md/DESIGN.md) for the Streamlit workbench.

Implements what Streamlit can express of the design system: Inter typography,
desaturated slate palette, glass panels, 4px radii, dense tables, label-caps
headers, and compact chips. Structural items Streamlit cannot deliver (a 64px
icon-only nav rail, true full-viewport map underlay) are approximated: slim
sidebar, floating-panel styling on containers.
"""

import html as _html
import json
from datetime import date, datetime
from typing import Any

import streamlit as st

# Palette tokens from DESIGN.md frontmatter.
COLORS = {
    "surface": "#f7f9fb",
    "surface_container": "#eceef0",
    "on_surface": "#191c1e",
    "on_surface_variant": "#434655",
    "outline_variant": "#c3c6d7",
    "border_subtle": "#E2E8F0",
    "primary": "#004ac6",
    "primary_container": "#2563eb",
    "secondary": "#006c4a",
    "tertiary_container": "#bc4800",
    "error": "#ba1a1a",
    "status_shortlisted": "#3B82F6",
    "status_warning": "#F59E0B",
    "status_occupied": "#64748B",
    "surface_glass": "rgba(255, 255, 255, 0.85)",
}

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

/* High-specificity so Inter beats Streamlit's own font rules. */
html body .stApp, html body .stApp *,
html body [data-testid="stSidebar"] * {{
    font-family: 'Inter', -apple-system, 'Segoe UI', sans-serif !important;
}}
/* Icon fonts must keep their ligature families or they render as raw text
   (e.g. "keyboard_double_arrow_left"). */
html body .stApp [data-testid="stIconMaterial"],
html body [data-testid="stSidebar"] [data-testid="stIconMaterial"],
html body .stApp span[class*="material-symbols"],
html body [data-testid="stSidebar"] span[class*="material-symbols"] {{
    font-family: 'Material Symbols Rounded' !important;
}}
html body .stApp code, html body .stApp pre,
html body .stApp [data-testid="stJson"] * {{
    font-family: 'SFMono-Regular', Consolas, monospace !important;
}}

/* Command-center chrome: hide Streamlit's toolbar/deploy header, tighten the
   canvas (DESIGN.md: 16px panel margins, density first). */
[data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu {{
    display: none !important;
}}
[data-testid="stHeader"] {{ background: transparent; height: 2rem; }}
.stApp .block-container {{
    padding: 1rem 16px 2rem 16px; max-width: 100%;
}}
[data-testid="stSidebar"] {{ overflow-x: hidden; }}

/* Dense HTML data tables (st.dataframe is canvas-drawn and unstylable). */
table.ka-table {{
    width: 100%; border-collapse: collapse;
    background: {COLORS["surface_glass"]};
    border: 1px solid {COLORS["border_subtle"]}; border-radius: 4px;
}}
table.ka-table th {{
    text-align: left; padding: 6px 12px;
    font-size: 11px; font-weight: 700; letter-spacing: 0.05em;
    text-transform: uppercase; color: {COLORS["on_surface_variant"]};
    border-bottom: 1px solid {COLORS["outline_variant"]};
    white-space: nowrap;
}}
table.ka-table td {{
    padding: 6px 12px; font-size: 13px; line-height: 18px;
    border-bottom: 1px solid {COLORS["border_subtle"]};
    color: {COLORS["on_surface"]};
}}
table.ka-table tr:hover td {{ background: rgba(37, 99, 235, 0.04); }}
table.ka-table td.num {{ font-variant-numeric: tabular-nums; }}
.ka-pill {{
    display: inline-block; padding: 1px 8px; border-radius: 9999px;
    font-size: 11px; font-weight: 700; letter-spacing: 0.03em;
}}

/* Inventory listing cards (Stitch "Inventory List" panel). */
.ka-card {{
    background: #ffffff; border: 1px solid {COLORS["border_subtle"]};
    border-radius: 4px; padding: 10px 12px; margin-bottom: 4px;
}}
.ka-card.sel {{
    border-color: {COLORS["status_shortlisted"]};
    box-shadow: 0 0 0 1px {COLORS["status_shortlisted"]};
}}
.ka-card.warn {{ border-left: 4px solid {COLORS["status_warning"]}; }}
.ka-card-top {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }}
.ka-card-title {{
    font-size: 14px; font-weight: 600; line-height: 20px;
    letter-spacing: -0.01em; color: {COLORS["on_surface"]};
}}
.ka-card-sub {{ font-size: 12px; line-height: 16px; color: {COLORS["on_surface_variant"]}; }}
.ka-card-price {{
    font-size: 16px; font-weight: 600; line-height: 24px;
    color: {COLORS["primary"]}; white-space: nowrap;
}}
.ka-card-chips {{ margin-top: 6px; }}
.ka-mini {{
    display: inline-block; margin: 0 6px 2px 0; padding: 0 8px;
    font-size: 11px; font-weight: 700; line-height: 16px;
    letter-spacing: 0.05em; text-transform: uppercase;
    background: {COLORS["surface_container"]}; color: {COLORS["on_surface_variant"]};
    border-radius: 2px;
}}
.ka-card-warnnote {{
    margin-top: 4px; font-size: 11px; font-weight: 600;
    color: {COLORS["status_warning"]};
}}
.ka-label {{
    font-size: 11px; font-weight: 700; line-height: 16px;
    letter-spacing: 0.05em; text-transform: uppercase;
    color: {COLORS["on_surface_variant"]};
}}

/* Dashboard: freshness bar chart + sync status feed (Stitch dashboard). */
.ka-bars {{
    display: flex; align-items: flex-end; gap: 20px;
    height: 140px; padding: 8px 4px 0 4px;
}}
.ka-bar-slot {{
    flex: 1; display: flex; flex-direction: column; align-items: center; height: 100%;
}}
.ka-bar-count {{
    font-size: 12px; font-weight: 700; color: {COLORS["on_surface_variant"]};
    font-variant-numeric: tabular-nums;
}}
.ka-bar-fill {{
    width: 100%; max-width: 72px; margin-top: auto;
    background: rgba(37, 99, 235, 0.22); border: 1px solid rgba(37, 99, 235, 0.35);
    border-radius: 2px 2px 0 0;
}}
.ka-bar-name {{
    margin-top: 4px; font-size: 11px; font-weight: 700; letter-spacing: 0.05em;
    text-transform: uppercase; color: {COLORS["on_surface_variant"]};
}}
.ka-feed-item {{
    display: flex; gap: 8px; padding: 7px 2px;
    border-bottom: 1px solid {COLORS["border_subtle"]};
}}
.ka-feed-item:last-child {{ border-bottom: none; }}
.ka-dot {{
    width: 8px; height: 8px; border-radius: 50%; margin-top: 5px; flex: none;
}}
.ka-feed-title {{
    font-size: 13px; font-weight: 600; line-height: 18px; color: {COLORS["on_surface"]};
}}
.ka-feed-sub {{ font-size: 12px; line-height: 16px; color: {COLORS["on_surface_variant"]}; }}
.ka-panel-title {{
    font-size: 16px; font-weight: 600; line-height: 24px;
    color: {COLORS["on_surface"]};
}}

.stApp {{ background: {COLORS["surface"]}; }}

/* Headline-panel: 16px/600. Titles stay compact — hierarchy via weight. */
h1 {{ font-size: 22px !important; font-weight: 700 !important; letter-spacing: -0.01em; }}
h2, h3 {{ font-size: 16px !important; font-weight: 600 !important; }}

/* Label-caps for widget labels and table headers. */
[data-testid="stWidgetLabel"] p, thead th {{
    font-size: 11px !important; font-weight: 700 !important;
    letter-spacing: 0.05em; text-transform: uppercase;
    color: {COLORS["on_surface_variant"]};
}}

/* Glass floating panels: bordered containers and expanders. */
[data-testid="stVerticalBlockBorderWrapper"] > div,
details[data-testid="stExpander"] {{
    background: {COLORS["surface_glass"]};
    backdrop-filter: blur(12px);
    border: 1px solid {COLORS["border_subtle"]};
    border-radius: 4px;
}}

/* Dense data tables: compact cells, border-bottom rows, hover striping. */
[data-testid="stDataFrame"] {{ font-size: 13px; }}
[data-testid="stDataFrame"] [role="columnheader"] {{
    font-size: 11px !important; font-weight: 700 !important;
    letter-spacing: 0.05em; text-transform: uppercase;
}}

/* Compact inputs (32px) and 4px "tooled" radii everywhere. */
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
[data-testid="stSelectbox"] > div > div {{
    min-height: 32px; border-radius: 4px;
}}
.stButton button {{
    border-radius: 4px; border: 1px solid {COLORS["border_subtle"]};
    font-size: 13px; font-weight: 600; padding: 2px 12px; min-height: 32px;
    box-shadow: none;
}}
.stButton button:hover {{ border-color: {COLORS["primary"]}; color: {COLORS["primary"]}; }}

/* Slim navigation (rail approximation) + glass sidebar. */
[data-testid="stSidebar"] {{
    background: {COLORS["surface_glass"]};
    backdrop-filter: blur(12px);
    border-right: 1px solid {COLORS["border_subtle"]};
    min-width: 240px !important; max-width: 240px !important;
}}
[data-testid="stSidebarNav"] a {{ border-radius: 4px; font-size: 13px; }}
[data-testid="stSidebarNav"] a[aria-current="page"] {{
    background: {COLORS["primary"]}14;
    border-left: 3px solid {COLORS["primary"]};
}}

/* Metric cards read as instrument clusters. */
[data-testid="stMetric"] {{
    background: {COLORS["surface_glass"]};
    border: 1px solid {COLORS["border_subtle"]};
    border-radius: 4px; padding: 8px 12px;
}}
[data-testid="stMetricLabel"] p {{
    font-size: 11px !important; font-weight: 700 !important;
    letter-spacing: 0.05em; text-transform: uppercase;
    color: {COLORS["on_surface_variant"]};
}}
[data-testid="stMetricValue"] {{ font-size: 22px; font-weight: 700; }}

/* Compact filter chips. */
.ka-chip {{
    display: inline-block; padding: 2px 10px; margin: 0 6px 6px 0;
    font-size: 11px; font-weight: 700; letter-spacing: 0.03em;
    background: {COLORS["surface_container"]}; color: {COLORS["on_surface_variant"]};
    border: 1px solid {COLORS["border_subtle"]}; border-radius: 9999px;
}}
.ka-chip.active {{
    background: {COLORS["primary"]}; color: #ffffff; border-color: {COLORS["primary"]};
}}
</style>
"""


def apply_theme() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


# Tonal pills for recurring status values (background, foreground).
_PILL_STYLES = {
    "good": ("rgba(0, 108, 74, 0.10)", COLORS["secondary"]),
    "warn": ("rgba(245, 158, 11, 0.16)", "#92600a"),
    "bad": ("rgba(186, 26, 26, 0.10)", COLORS["error"]),
    "info": ("rgba(37, 99, 235, 0.10)", COLORS["primary"]),
    "muted": (COLORS["surface_container"], COLORS["on_surface_variant"]),
}
_STATUS_TONES = {
    "SUCCEEDED": "good",
    "COMPLETED": "good",
    "ACTIVE": "good",
    "IN_SCOPE": "good",
    "RESOLVED": "good",
    "RUNNING": "info",
    "SELECTED": "info",
    "ACTIVATED": "info",
    "SCHEDULED": "info",
    "PENDING": "warn",
    "DEGRADED": "warn",
    "PARTIAL_SUCCESS": "warn",
    "CANDIDATE": "warn",
    "MEDIUM": "warn",
    "MISSING": "warn",
    "REVIEW_REQUIRED": "warn",
    "OPEN": "warn",
    "CONFLICTING": "warn",
    "FAILED": "bad",
    "HIGH": "bad",
    "CRITICAL": "bad",
    "REMOVED": "bad",
    "EXCLUDED": "bad",
    "OUT_OF_SCOPE": "bad",
    "LOW": "muted",
    "INACTIVE": "muted",
    "UNKNOWN": "muted",
}


def _format_cell(value: Any) -> str:
    if value is None or value == "":
        return '<span style="color:#94a3b8">&mdash;</span>'
    if isinstance(value, datetime):
        return _html.escape(value.strftime("%m-%d %H:%M"))
    if isinstance(value, date):
        return _html.escape(value.isoformat())
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (dict, list)):
        value = json.dumps(value, default=str)
    text = str(value)
    if text.startswith(("http://", "https://")):
        display = text if len(text) <= 60 else text[:57] + "…"
        href = _html.escape(text, quote=True)
        return (
            f'<a href="{href}" target="_blank" rel="noopener" '
            f'style="color:{COLORS["primary"]};text-decoration:none">{_html.escape(display)}</a>'
        )
    tone = _STATUS_TONES.get(text)
    if tone:
        bg, fg = _PILL_STYLES[tone]
        style = f"background:{bg};color:{fg}"
        return f'<span class="ka-pill" style="{style}">{_html.escape(text)}</span>'
    if len(text) > 60:
        text = text[:57] + "…"
    return _html.escape(text)


def dense_table(
    rows: list[dict[str, Any]],
    columns: list[str | tuple[str, str]] | None = None,
    empty: str = "No data.",
) -> None:
    """Render rows as a DESIGN.md dense table (st.dataframe is canvas-drawn,
    so the design system's typography/density cannot reach it)."""
    if not rows:
        st.caption(empty)
        return
    if columns is None:
        cols: list[tuple[str, str]] = [(key, key.replace("_", " ")) for key in rows[0]]
    else:
        cols = [(c, c.replace("_", " ")) if isinstance(c, str) else c for c in columns]
    head = "".join(f"<th>{_html.escape(header)}</th>" for _, header in cols)
    body_rows = []
    for row in rows:
        cells = []
        for key, _ in cols:
            value = row.get(key)
            numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
            td_open = '<td class="num">' if numeric else "<td>"
            cells.append(f"{td_open}{_format_cell(value)}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    st.markdown(
        f'<table class="ka-table"><thead><tr>{head}</tr></thead>'
        f'<tbody>{"".join(body_rows)}</tbody></table>',
        unsafe_allow_html=True,
    )


_CARD_LAYOUT_SHORT = {
    "STUDIO": "Studio",
    "ONE_BEDROOM": "1BR",
    "TWO_BEDROOM": "2BR",
    "OUT_OF_SCOPE": "3BR+",
    "UNKNOWN": "Layout ?",
}
_CARD_WARN_LIFECYCLES = ("MISSING", "REVIEW_REQUIRED", "REAPPEARED")


def listing_card(row: dict[str, Any]) -> None:
    """Stitch inventory-list property card: address, locality, price, chips.

    Buttons cannot live inside raw HTML; render them separately after the card.
    """
    classes = ["ka-card"]
    selected = bool(row.get("selected"))
    lifecycle = str(row.get("lifecycle", ""))
    warn = lifecycle in _CARD_WARN_LIFECYCLES
    if selected:
        classes.append("sel")
    elif warn:
        classes.append("warn")
    star = (
        f'<span style="color:{COLORS["status_shortlisted"]}">&#9733;</span> ' if selected else ""
    )
    chips = [_CARD_LAYOUT_SHORT.get(str(row.get("layout", "")), str(row.get("layout", "")))]
    laundry = str(row.get("laundry", ""))
    if laundry and laundry != "Laundry unknown":
        chips.append(laundry)
    chip_html = "".join(f'<span class="ka-mini">{_html.escape(c)}</span>' for c in chips)
    warn_html = (
        f'<div class="ka-card-warnnote">&#9888; {_html.escape(lifecycle)}</div>' if warn else ""
    )
    rent = str(row.get("rent", "unknown"))
    st.markdown(
        f'<div class="{" ".join(classes)}">'
        f'<div class="ka-card-top"><div>'
        f'<div class="ka-card-title">{star}{_html.escape(str(row.get("address", "")))}</div>'
        f'<div class="ka-card-sub">{_html.escape(str(row.get("locality") or ""))}</div>'
        f"</div>"
        f'<div class="ka-card-price">{_html.escape(rent)}</div></div>'
        f'<div class="ka-card-chips">{chip_html}</div>{warn_html}</div>',
        unsafe_allow_html=True,
    )


def freshness_bars(buckets: list[tuple[str, int]]) -> None:
    """Vertical bar chart for last-seen freshness (Stitch "Inventory Freshness")."""
    peak = max((count for _, count in buckets), default=0) or 1
    slots = "".join(
        '<div class="ka-bar-slot">'
        f'<span class="ka-bar-count">{count}</span>'
        f'<div class="ka-bar-fill" style="height:{max(4, round(count / peak * 100))}%"></div>'
        f'<span class="ka-bar-name">{_html.escape(name)}</span></div>'
        for name, count in buckets
    )
    st.markdown(f'<div class="ka-bars">{slots}</div>', unsafe_allow_html=True)


_FEED_DOT = {
    "good": COLORS["secondary"],
    "warn": COLORS["status_warning"],
    "bad": COLORS["error"],
    "info": COLORS["primary"],
    "muted": COLORS["status_occupied"],
}


def feed_item(tone: str, title: str, subtitle: str) -> None:
    """One sync-status-feed row: colored dot + title + caption."""
    dot = _FEED_DOT.get(tone, _FEED_DOT["muted"])
    st.markdown(
        f'<div class="ka-feed-item"><span class="ka-dot" style="background:{dot}"></span>'
        f'<div><div class="ka-feed-title">{_html.escape(title)}</div>'
        f'<div class="ka-feed-sub">{_html.escape(subtitle)}</div></div></div>',
        unsafe_allow_html=True,
    )


def status_tone(status: str) -> str:
    """Map a status string to a feed/pill tone."""
    return _STATUS_TONES.get(status, "muted")


def panel_header(title: str, label: str | None = None) -> None:
    """Floating-panel header: headline-panel title + optional label-caps line."""
    label_html = f'<div class="ka-label">{_html.escape(label)}</div>' if label else ""
    st.markdown(
        f'<div class="ka-panel-title">{_html.escape(title)}</div>{label_html}',
        unsafe_allow_html=True,
    )


def filter_chips(chips: list[tuple[str, bool]]) -> None:
    """Render compact filter chips: (label, active)."""
    html = "".join(
        f'<span class="ka-chip{" active" if active else ""}">{label}</span>'
        for label, active in chips
    )
    st.markdown(html, unsafe_allow_html=True)


def marker_accent(state: dict) -> str:
    """Marker left-accent color per DESIGN.md component rules."""
    if state.get("selected"):
        return COLORS["status_shortlisted"]
    lifecycle = state.get("lifecycle", "")
    if lifecycle == "ACTIVE":
        return COLORS["secondary"]
    if lifecycle in ("REVIEW_REQUIRED", "MISSING") or state.get("warning"):
        return COLORS["status_warning"]
    return COLORS["status_occupied"]
