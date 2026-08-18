"""Operations: refresh runs, source health, job queue (07 §19)."""

import streamlit as st

from rental_agent.ui import queries
from rental_agent.ui.app import session_factory
from rental_agent.ui.theme import dense_table


def render() -> None:
    factory, _settings = session_factory()
    st.title("Operations")

    with factory() as session:
        runs = queries.recent_refresh_runs(session, limit=15)
        source_runs = queries.source_run_history(session)
        jobs = queries.job_queue_summary(session)

    st.subheader("Refresh runs")
    dense_table(runs, empty="No runs yet.")

    st.subheader("Source runs")
    dense_table(source_runs, empty="No source runs yet.")
    if source_runs:
        st.caption(
            "health_gate=False on search-discovered runs is by design: search "
            "absence never counts as disappearance evidence (B3)."
        )

    st.subheader("Job queue")
    dense_table(jobs, empty="Queue is empty.")
