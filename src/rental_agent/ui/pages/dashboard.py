"""Dashboard: is today's inventory usable, what changed, what needs attention (07 §8).

Layout follows the Stitch "Operational Health Dashboard": KPI cards, an
Inventory Freshness chart, a Sync Status Feed of source runs, and a system
health strip. All numbers are real; nothing is fabricated to fill the design.
"""

import time

import streamlit as st
from sqlalchemy import text as sql_text

from rental_agent.ui import queries
from rental_agent.ui.app import session_factory
from rental_agent.ui.theme import (
    dense_table,
    feed_item,
    freshness_bars,
    panel_header,
    status_tone,
)


def render() -> None:
    factory, _settings = session_factory()
    st.title("Dashboard")
    st.caption("Real-time inventory operations and system health.")

    with factory() as session:
        started = time.perf_counter()
        session.execute(sql_text("SELECT 1"))
        db_latency_ms = (time.perf_counter() - started) * 1000
        summary = queries.dashboard_summary(session)
        runs = queries.recent_refresh_runs(session)
        source_runs = queries.source_run_history(session)
        events = queries.recent_events(session)
        issues = queries.open_review_issues(session)
        buckets = queries.freshness_buckets(session)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Listings (total)", summary["total"])
    c2.metric("Candidate", summary["candidate"])
    c3.metric("Active", summary["active"])
    c4.metric("Selected for marketing", summary["selected"])
    c5.metric("Open review issues", summary["open_issues"])

    left, right = st.columns([2, 1], gap="small")
    with left:
        with st.container(border=True):
            panel_header("Inventory Freshness", "Active + candidate, by last-seen age")
            freshness_bars(buckets)
        with st.container(border=True):
            panel_header("Attention queue")
            if issues:
                dense_table(
                    [
                        {
                            "severity": issue["severity"],
                            "type": issue["type"],
                            "created": issue["created"],
                        }
                        for issue in issues[:8]
                    ]
                )
                st.page_link("review", label="Open review queue →")
            else:
                st.caption("No open review issues.")
    with right, st.container(border=True):
        panel_header("Sync Status Feed")
        if not runs and not source_runs:
            st.caption("No runs recorded yet.")
        for run in runs[:4]:
            stamp = run["started"].strftime("%m-%d %H:%M") if run["started"] else "—"
            feed_item(
                status_tone(str(run["status"])),
                f"Refresh {run['status']}",
                f"{run['run']} · {stamp}",
            )
        for source_run in source_runs[:4]:
            stamp = (
                source_run["started"].strftime("%m-%d %H:%M") if source_run["started"] else "—"
            )
            counts = source_run.get("counts") or {}
            discovered = counts.get("discovered", "?")
            persisted = counts.get("persisted_new", "?")
            feed_item(
                status_tone(str(source_run["status"])),
                f"{source_run['source']} {source_run['status']}",
                f"{discovered} discovered · {persisted} persisted · {stamp}",
            )

    st.subheader("Change feed")
    dense_table(
        [
            {
                "time": ev["time"],
                "event": ev["event"],
                "listing": ev["listing_id"][:8],
                "details": ev["after"],
            }
            for ev in events
        ],
        empty="No listing events yet.",
    )

    last_refresh = "never"
    if runs:
        stamp = runs[0]["completed"] or runs[0]["started"]
        if stamp is not None:
            last_refresh = stamp.strftime("%Y-%m-%d %H:%M")
    st.caption(
        f"DB latency: {db_latency_ms:.0f} ms · "
        f"Transit stops loaded: {summary['transit_stops']:,} · "
        f"Pending duplicate candidates: {summary['pending_duplicates']} · "
        f"Last refresh: {last_refresh}"
    )
