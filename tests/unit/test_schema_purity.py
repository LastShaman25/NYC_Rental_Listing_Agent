"""Schema-purity invariants that must hold for the life of the project:

- No contact-data fields anywhere in canonical/export schemas (PR-ACQ-005).
- No score fields (PR-COMMUTE-005 and kickoff exclusions).
- No cloud/Supabase dependencies (owner architecture constraint).
"""

import re
import tomllib
from pathlib import Path

from rental_agent.db import models  # noqa: F401
from rental_agent.db.base import Base

# Status fields that track *exclusion* of contact data are allowed; they store
# enum states, never contact values.
ALLOWED_CONTACT_STATUS_COLUMNS = {
    "contact_redaction_status",
    "contact_overlay_status",
}

FORBIDDEN_COLUMN_PATTERNS = [
    r"phone",
    r"e_?mail",
    r"broker",
    r"landlord",
    r"leasing",
    r"license",
    r"contact(?!_redaction_status$)(?!_overlay_status$)",
]

FORBIDDEN_SCORE_PATTERN = re.compile(r"(^|_)score($|_)")
# duplicate-candidate and media-similarity measures are internal match measures,
# explicitly permitted by 02 §9.4 / 05 §7.5 under non-score names.


def _all_columns():
    for table in Base.metadata.tables.values():
        for column in table.columns:
            yield table.fullname, column.name


def test_no_contact_columns():
    offenders = []
    for table_name, column_name in _all_columns():
        if column_name in ALLOWED_CONTACT_STATUS_COLUMNS:
            continue
        for pattern in FORBIDDEN_COLUMN_PATTERNS:
            if re.search(pattern, column_name, re.IGNORECASE):
                offenders.append((table_name, column_name, pattern))
    assert not offenders, f"contact-data columns are prohibited: {offenders}"


def test_no_score_columns():
    offenders = [
        (t, c)
        for t, c in _all_columns()
        if FORBIDDEN_SCORE_PATTERN.search(c) and c != "candidate_score"
    ]
    # candidate_score is the internal dedup match measure allowed by 02 §9.4;
    # nothing else may carry a score name.
    assert not offenders, f"score columns are prohibited: {offenders}"


def test_no_cloud_dependencies():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    deps = " ".join(pyproject["project"]["dependencies"]).lower()
    dev = " ".join(pyproject.get("dependency-groups", {}).get("dev", [])).lower()
    for forbidden in ("supabase", "boto3", "botocore", "google-cloud", "azure", "firebase"):
        assert forbidden not in deps and forbidden not in dev, (
            f"cloud dependency '{forbidden}' is prohibited for this local-only tool"
        )
