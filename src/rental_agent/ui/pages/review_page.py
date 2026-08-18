"""Review queue: duplicate candidates and conflicts needing human judgment (07 §17)."""

import uuid

import streamlit as st

from rental_agent.canonical.merge_service import MergeService
from rental_agent.contracts.enums import ActorType
from rental_agent.db.models import ReviewIssue
from rental_agent.ui import queries
from rental_agent.ui.app import session_factory


def render() -> None:
    factory, settings = session_factory()
    st.title("Review Queue")

    with factory() as session:
        candidates = queries.pending_duplicate_candidates(session)
        issues = queries.open_review_issues(session)

    st.subheader(f"Duplicate candidates ({len(candidates)})")
    if not candidates:
        st.success("No pending duplicate candidates.")
    for candidate in candidates:
        with st.container(border=True):
            st.markdown(
                f"Listing A `{candidate['listing_a']}` vs Listing B `{candidate['listing_b']}`"
            )
            st.json(candidate["evidence"])
            c1, c2, c3 = st.columns(3)
            candidate_id = uuid.UUID(candidate["candidate_id"])
            if c1.button("Same apartment — keep A", key=f"dup-a-{candidate_id}"):
                _resolve(factory, settings, candidate_id, True, uuid.UUID(candidate["listing_a"]))
            if c2.button("Same apartment — keep B", key=f"dup-b-{candidate_id}"):
                _resolve(factory, settings, candidate_id, True, uuid.UUID(candidate["listing_b"]))
            if c3.button("Different apartments", key=f"dup-d-{candidate_id}"):
                _resolve(factory, settings, candidate_id, False, None)

    st.subheader(f"Other open issues ({len(issues)})")
    for issue in issues:
        if issue["type"] == "DUPLICATE_CANDIDATE":
            continue  # handled above via candidate resolution
        with st.container(border=True):
            st.markdown(f"**{issue['severity']}** · {issue['type']} · {issue['created']:%Y-%m-%d}")
            st.json(issue["details"])
            note = st.text_input("Resolution note", key=f"note-{issue['issue_id']}")
            if st.button("Mark resolved", key=f"res-{issue['issue_id']}"):
                if not note and issue["severity"] == "BLOCKING":
                    st.error("Blocking issues require a resolution note (07 §17.5).")
                else:
                    with factory() as session:
                        row = session.get(ReviewIssue, uuid.UUID(issue["issue_id"]))
                        row.status = "RESOLVED"
                        row.resolved_by = settings.operator_id
                        row.resolution_note = note or None
                        from datetime import UTC, datetime

                        row.resolved_at = datetime.now(tz=UTC)
                        session.commit()
                    st.rerun()


def _resolve(factory, settings, candidate_id, confirmed: bool, survivor) -> None:
    with factory() as session:
        MergeService(session).resolve_duplicate_candidate(
            candidate_id,
            confirmed_duplicate=confirmed,
            actor=settings.operator_id,
            actor_type=ActorType.HUMAN,
            survivor_listing_id=survivor,
        )
        session.commit()
    st.rerun()
