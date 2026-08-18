"""All ORM models. Importing this module registers every table on Base.metadata."""

from rental_agent.db.base import Base
from rental_agent.db.models.addresses import Address, AddressAssertion
from rental_agent.db.models.boundaries import GeographicBoundary
from rental_agent.db.models.canonical import (
    Building,
    CanonicalListing,
    CanonicalMerge,
    DuplicateCandidate,
    ListingSourceLink,
    Unit,
)
from rental_agent.db.models.facts import (
    AmenityAssertion,
    AmenityDefinition,
    FactAssertion,
    FactResolution,
    ListingEvent,
    ListingFieldHistory,
)
from rental_agent.db.models.media import (
    MediaAnalysis,
    MediaAsset,
    MediaAssociation,
    MediaDuplicateGroup,
    MediaDuplicateMember,
    MediaVariant,
)
from rental_agent.db.models.ops import (
    Job,
    JobAttempt,
    JobDependency,
    ModelExecution,
    ProviderRequest,
)
from rental_agent.db.models.review import (
    AuditActionLog,
    ClientSearchPreset,
    ClientShortlistEntry,
    HumanOverride,
    MarketingSelection,
    ReviewIssue,
)
from rental_agent.db.models.sources import (
    AdapterCheckpoint,
    RefreshRun,
    Source,
    SourceObservation,
    SourceRun,
)
from rental_agent.db.models.transit import (
    CommuteResult,
    Destination,
    TransitAccess,
    TransitAccessRoute,
    TransitRoute,
    TransitStop,
    TransitStopRoute,
)

__all__ = [
    "Base",
    "GeographicBoundary",
    "Address",
    "AddressAssertion",
    "Building",
    "CanonicalListing",
    "CanonicalMerge",
    "DuplicateCandidate",
    "ListingSourceLink",
    "Unit",
    "AmenityAssertion",
    "AmenityDefinition",
    "FactAssertion",
    "FactResolution",
    "ListingEvent",
    "ListingFieldHistory",
    "MediaAnalysis",
    "MediaAsset",
    "MediaAssociation",
    "MediaDuplicateGroup",
    "MediaDuplicateMember",
    "MediaVariant",
    "Job",
    "JobAttempt",
    "JobDependency",
    "ModelExecution",
    "ProviderRequest",
    "AuditActionLog",
    "ClientSearchPreset",
    "ClientShortlistEntry",
    "HumanOverride",
    "MarketingSelection",
    "ReviewIssue",
    "AdapterCheckpoint",
    "RefreshRun",
    "Source",
    "SourceObservation",
    "SourceRun",
    "CommuteResult",
    "Destination",
    "TransitAccess",
    "TransitAccessRoute",
    "TransitRoute",
    "TransitStop",
    "TransitStopRoute",
]
