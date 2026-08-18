"""Candidate source-registry seed (03 §5.2).

Every candidate starts PROPOSED and disabled. Nothing here grants permission to
acquire; enablement requires an approved policy record (03 §6.2). Owner decision
2026-08-17: StreetEasy is the first source to evaluate, still subject to
access-method approval.
"""

from dataclasses import dataclass

from rental_agent.contracts.enums import AccessMethod, SourceApprovalStatus, SourceType


@dataclass(frozen=True)
class SourceSeed:
    source_code: str
    display_name: str
    source_type: SourceType
    access_method: AccessMethod
    approval_status: SourceApprovalStatus
    base_domain: str | None
    policy_version: str


CANDIDATE_SOURCES: tuple[SourceSeed, ...] = (
    SourceSeed(
        "streeteasy",
        "StreetEasy",
        SourceType.LISTING,
        AccessMethod.BROWSER,  # provisional; final method requires Phase 0 approval
        SourceApprovalStatus.PROPOSED,
        "streeteasy.com",
        "0-proposed",
    ),
    SourceSeed(
        "zillow_rentals",
        "Zillow Rentals",
        SourceType.LISTING,
        AccessMethod.BROWSER,
        SourceApprovalStatus.PROPOSED,
        "zillow.com",
        "0-proposed",
    ),
    SourceSeed(
        "apartments_com",
        "Apartments.com",
        SourceType.LISTING,
        AccessMethod.BROWSER,
        SourceApprovalStatus.PROPOSED,
        "apartments.com",
        "0-proposed",
    ),
    SourceSeed(
        "renthop",
        "RentHop",
        SourceType.LISTING,
        AccessMethod.BROWSER,
        SourceApprovalStatus.PROPOSED,
        "renthop.com",
        "0-proposed",
    ),
    SourceSeed(
        "realtor_rentals",
        "Realtor.com Rentals",
        SourceType.LISTING,
        AccessMethod.BROWSER,
        SourceApprovalStatus.PROPOSED,
        "realtor.com",
        "0-proposed",
    ),
    SourceSeed(
        "property_sites",
        "Direct property/building sites",
        SourceType.LISTING,
        AccessMethod.BROWSER,
        SourceApprovalStatus.PROPOSED,
        None,
        "0-proposed",
    ),
    SourceSeed(
        "manual_import",
        "Manual approved import",
        SourceType.LISTING,
        AccessMethod.MANUAL_IMPORT,
        SourceApprovalStatus.PROPOSED,
        None,
        "0-proposed",
    ),
    # Non-listing providers (Phase 0 decisions, still disabled until integrated)
    SourceSeed(
        "google_maps_platform",
        "Google Maps Platform",
        SourceType.ROUTING,
        AccessMethod.API,
        SourceApprovalStatus.UNDER_REVIEW,
        "googleapis.com",
        "0-proposed",
    ),
    SourceSeed(
        "mta_gtfs",
        "MTA GTFS static feeds",
        SourceType.TRANSIT_DATA,
        AccessMethod.FEED,
        SourceApprovalStatus.UNDER_REVIEW,
        "mta.info",
        "0-proposed",
    ),
    SourceSeed(
        "path_gtfs",
        "PATH schedule data",
        SourceType.TRANSIT_DATA,
        AccessMethod.FEED,
        SourceApprovalStatus.UNDER_REVIEW,
        "panynj.gov",
        "0-proposed",
    ),
    SourceSeed(
        "njt_gtfs",
        "NJ Transit schedule data",
        SourceType.TRANSIT_DATA,
        AccessMethod.FEED,
        SourceApprovalStatus.UNDER_REVIEW,
        "njtransit.com",
        "0-proposed",
    ),
)


def seed_sources(session) -> int:
    """Insert missing candidate sources; existing codes are left untouched."""
    from sqlalchemy import select

    from rental_agent.db.models import Source

    existing = set(session.execute(select(Source.source_code)).scalars())
    added = 0
    for seed in CANDIDATE_SOURCES:
        if seed.source_code in existing:
            continue
        session.add(
            Source(
                source_code=seed.source_code,
                display_name=seed.display_name,
                source_type=seed.source_type.value,
                access_method=seed.access_method.value,
                approval_status=seed.approval_status.value,
                enabled=False,
                base_domain=seed.base_domain,
                policy_version=seed.policy_version,
            )
        )
        added += 1
    return added
