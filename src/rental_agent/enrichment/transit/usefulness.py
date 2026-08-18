"""Transit usefulness classification v1 (04 §13).

Deterministic, conservative first version working from straight-line candidate
distances (routed walking arrives with a walking-route provider):

- SUBWAY/PATH complex within USEFUL_STRAIGHT_LINE_M → USEFUL with a direct-
  access reason; the distance basis is recorded so nothing masquerades as a
  validated walk.
- Candidates beyond that stay CANDIDATE with SERVICE_UNVERIFIED.
- Never a score: explicit reason codes only (04 §13.2).
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from rental_agent.config.logging import get_logger
from rental_agent.contracts import enums as e
from rental_agent.db.models import TransitAccess

log = get_logger(__name__)

USEFULNESS_RULE_VERSION = "usefulness-straightline-v1"
# Conservative direct-access band; calibration input, revisit with routed walking.
USEFUL_STRAIGHT_LINE_M = 800

MODE_REASON = {
    "SUBWAY": "DIRECT_SUBWAY_ACCESS",
    "PATH": "DIRECT_PATH_ACCESS",
}


@dataclass
class UsefulnessSummary:
    evaluated: int = 0
    useful: int = 0
    candidate: int = 0


def classify_usefulness(session: Session, limit: int = 5000) -> UsefulnessSummary:
    summary = UsefulnessSummary()
    rows = (
        session.execute(
            select(TransitAccess)
            .where(TransitAccess.usefulness_status == e.UsefulnessStatus.CANDIDATE.value)
            .limit(limit)
        )
        .scalars()
        .all()
    )
    for access in rows:
        summary.evaluated += 1
        if (
            access.straight_line_distance_m is not None
            and access.straight_line_distance_m <= USEFUL_STRAIGHT_LINE_M
            and access.mode in MODE_REASON
        ):
            access.usefulness_status = e.UsefulnessStatus.USEFUL.value
            access.usefulness_reasons = {
                "rule": USEFULNESS_RULE_VERSION,
                "reasons": [MODE_REASON[access.mode]],
                "distance_basis": "straight_line_only",
            }
            summary.useful += 1
        else:
            access.usefulness_reasons = {
                "rule": USEFULNESS_RULE_VERSION,
                "reasons": ["SERVICE_UNVERIFIED"],
                "distance_basis": "straight_line_only",
            }
            summary.candidate += 1
    log.info(
        "usefulness_run",
        evaluated=summary.evaluated,
        useful=summary.useful,
        candidate=summary.candidate,
    )
    return summary
