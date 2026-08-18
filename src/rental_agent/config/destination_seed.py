"""Campus and major-destination registry seed (04 §18.2, §18.4).

Registry version ``v1-reviewed-2026-08-17``: all 20 anchors were reviewed and
approved by the owner on 2026-08-17 via the anchor review map. Codes are
immutable; any future anchor change creates a new registry version and
invalidates affected commute results (04 §18.1).
"""

from dataclasses import dataclass

from rental_agent.contracts.enums import DestinationType

REGISTRY_VERSION = "v1-reviewed-2026-08-17"


@dataclass(frozen=True)
class DestinationSeed:
    code: str
    destination_type: DestinationType
    display_name: str
    institution_name: str | None
    anchor_name: str
    longitude: float
    latitude: float


CAMPUSES: tuple[DestinationSeed, ...] = (
    DestinationSeed(
        "NYU_WASHINGTON_SQUARE",
        DestinationType.UNIVERSITY_CAMPUS,
        "NYU Washington Square",
        "New York University",
        "Bobst Library / 70 Washington Square South",
        -73.9970,
        40.7295,
    ),
    DestinationSeed(
        "NYU_TANDON",
        DestinationType.UNIVERSITY_CAMPUS,
        "NYU Tandon School of Engineering",
        "New York University",
        "6 MetroTech Center, Brooklyn",
        -73.9862,
        40.6942,
    ),
    DestinationSeed(
        "COLUMBIA_MORNINGSIDE",
        DestinationType.UNIVERSITY_CAMPUS,
        "Columbia University — Morningside",
        "Columbia University",
        "116th Street and Broadway",
        -73.9626,
        40.8075,
    ),
    DestinationSeed(
        "PRATT_BROOKLYN",
        DestinationType.UNIVERSITY_CAMPUS,
        "Pratt Institute — Brooklyn",
        "Pratt Institute",
        "200 Willoughby Avenue, Brooklyn",
        -73.9640,
        40.6913,
    ),
    DestinationSeed(
        "NEW_SCHOOL_UNIVERSITY_CENTER",
        DestinationType.UNIVERSITY_CAMPUS,
        "Parsons / The New School",
        "The New School",
        "University Center, 63 Fifth Avenue",
        -73.9936,
        40.7353,
    ),
    DestinationSeed(
        "FIT_MAIN",
        DestinationType.UNIVERSITY_CAMPUS,
        "Fashion Institute of Technology",
        "FIT",
        "227 West 27th Street",
        -73.9937,
        40.7466,
    ),
    DestinationSeed(
        "SVA_MAIN",
        DestinationType.UNIVERSITY_CAMPUS,
        "School of Visual Arts",
        "SVA",
        "209 East 23rd Street",
        -73.9840,
        40.7387,
    ),
    DestinationSeed(
        "BARUCH_MAIN",
        DestinationType.UNIVERSITY_CAMPUS,
        "Baruch College",
        "CUNY Baruch",
        "55 Lexington Avenue",
        -73.9832,
        40.7402,
    ),
    DestinationSeed(
        "HUNTER_MAIN",
        DestinationType.UNIVERSITY_CAMPUS,
        "Hunter College",
        "CUNY Hunter",
        "695 Park Avenue",
        -73.9647,
        40.7686,
    ),
    DestinationSeed(
        "FORDHAM_ROSE_HILL",
        DestinationType.UNIVERSITY_CAMPUS,
        "Fordham University — Rose Hill",
        "Fordham University",
        "441 East Fordham Road, Bronx",
        -73.8859,
        40.8614,
    ),
    DestinationSeed(
        "FORDHAM_LINCOLN_CENTER",
        DestinationType.UNIVERSITY_CAMPUS,
        "Fordham University — Lincoln Center",
        "Fordham University",
        "113 West 60th Street",
        -73.9840,
        40.7712,
    ),
    DestinationSeed(
        "STEVENS_MAIN",
        DestinationType.UNIVERSITY_CAMPUS,
        "Stevens Institute of Technology",
        "Stevens",
        "1 Castle Point Terrace, Hoboken",
        -74.0247,
        40.7440,
    ),
)

MAJOR_DESTINATIONS: tuple[DestinationSeed, ...] = (
    DestinationSeed(
        "WEST_VILLAGE",
        DestinationType.MAJOR_DESTINATION,
        "West Village",
        None,
        "Christopher Street and Seventh Avenue South",
        -74.0027,
        40.7336,
    ),
    DestinationSeed(
        "CENTRAL_PARK_SOUTHWEST",
        DestinationType.MAJOR_DESTINATION,
        "Central Park",
        None,
        "Columbus Circle / southwest park entrance",
        -73.9819,
        40.7681,
    ),
    DestinationSeed(
        "UNION_SQUARE",
        DestinationType.MAJOR_DESTINATION,
        "Union Square",
        None,
        "Union Square transit hub / 14th Street",
        -73.9904,
        40.7359,
    ),
    DestinationSeed(
        "TIMES_SQUARE",
        DestinationType.MAJOR_DESTINATION,
        "Times Square",
        None,
        "Times Square–42nd Street transit hub",
        -73.9869,
        40.7557,
    ),
    DestinationSeed(
        "WTC_FINANCIAL_DISTRICT",
        DestinationType.MAJOR_DESTINATION,
        "World Trade Center / Financial District",
        None,
        "World Trade Center Transportation Hub",
        -74.0119,
        40.7115,
    ),
    DestinationSeed(
        "GRAND_CENTRAL",
        DestinationType.MAJOR_DESTINATION,
        "Grand Central",
        None,
        "Grand Central Terminal",
        -73.9772,
        40.7527,
    ),
    DestinationSeed(
        "WILLIAMSBURG_BEDFORD",
        DestinationType.MAJOR_DESTINATION,
        "Williamsburg",
        None,
        "Bedford Avenue and North 7th Street, Brooklyn",
        -73.9566,
        40.7171,
    ),
    DestinationSeed(
        "DOWNTOWN_BROOKLYN",
        DestinationType.MAJOR_DESTINATION,
        "Downtown Brooklyn",
        None,
        "Borough Hall / Court Street transit area",
        -73.9903,
        40.6933,
    ),
)

ALL_DESTINATIONS = CAMPUSES + MAJOR_DESTINATIONS


def seed_destinations(session) -> int:
    """Insert missing registry entries; existing codes are never mutated here."""
    from sqlalchemy import select

    from rental_agent.db.models import Destination

    existing = set(session.execute(select(Destination.destination_code)).scalars())
    added = 0
    for seed in ALL_DESTINATIONS:
        if seed.code in existing:
            continue
        session.add(
            Destination(
                destination_code=seed.code,
                destination_type=seed.destination_type.value,
                institution_name=seed.institution_name,
                display_name=seed.display_name,
                routing_anchor_name=seed.anchor_name,
                routing_anchor_point=f"SRID=4326;POINT({seed.longitude} {seed.latitude})",
                registry_version=REGISTRY_VERSION,
            )
        )
        added += 1
    return added
