"""Operations: refresh runs, source health, job queue (07 §19)."""

import streamlit as st

from rental_agent.ui import queries
from rental_agent.ui.app import session_factory


def render() -> None:
    factory, _settings = session_factory()
    st.title("Operations")

    with factory() as session:
        runs = queries.recent_refresh_runs(session, limit=15)
        source_runs = queries.source_run_history(session)
        jobs = queries.job_queue_summary(session)

    st.subheader("Refresh runs")
    st.dataframe(runs, use_container_width=True) if runs else st.info("No runs yet.")

    st.subheader("Source runs")
    if source_runs:
        st.dataframe(source_runs, use_container_width=True)
        st.caption(
            "health_gate=False on search-discovered runs is by design: search "
            "absence never counts as disappearance evidence (B3)."
        )
    else:
        st.info("No source runs yet.")

    st.subheader("Job queue")
    st.dataframe(jobs, use_container_width=True) if jobs else st.info("Queue is empty.")
