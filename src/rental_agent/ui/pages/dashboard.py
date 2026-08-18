"""Dashboard: is today's inventory usable, what changed, what needs attention (07 §8)."""

import streamlit as st

from rental_agent.ui import queries
from rental_agent.ui.app import session_factory


def render() -> None:
    factory, _settings = session_factory()
    st.title("Dashboard")
    with factory() as session:
        summary = queries.dashboard_summary(session)
        runs = queries.recent_refresh_runs(session)
        events = queries.recent_events(session)
        issues = queries.open_review_issues(session)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Listings (total)", summary["total"])
    c2.metric("Candidate", summary["candidate"])
    c3.metric("Active", summary["active"])
    c4.metric("Selected for marketing", summary["selected"])
    c5.metric("Open review issues", summary["open_issues"])
    st.caption(
        f"Transit stops loaded: {summary['transit_stops']:,} · "
        f"Pending duplicate candidates: {summary['pending_duplicates']}"
    )

    left, right = st.columns(2)
    with left:
        st.subheader("Recent refresh runs")
        if runs:
            st.dataframe(runs, use_container_width=True)
        else:
            st.info("No refresh runs recorded yet.")
    with right:
        st.subheader("Attention queue")
        if issues:
            st.dataframe(
                [
                    {
                        "severity": issue["severity"],
                        "type": issue["type"],
                        "created": issue["created"],
                    }
                    for issue in issues[:8]
                ],
                use_container_width=True,
            )
            st.page_link("review", label="Open review queue →")
        else:
            st.success("No open review issues.")

    st.subheader("Change feed")
    if events:
        st.dataframe(events, use_container_width=True)
    else:
        st.info("No listing events yet.")
