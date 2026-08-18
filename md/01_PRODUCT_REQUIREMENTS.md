# NYC/NJ Rental Listing Agent — Product Requirements

## 1. Document Control

| Field | Value |
| --- | --- |
| Status | Draft specification |
| Owner | CJ |
| Product type | Internal work tool |
| Controlling overview | `00_PROJECT_OVERVIEW.md` |
| Downstream dependents | `02_LISTING_DATA_SCHEMA.md` through `08_IMPLEMENTATION_PLAN.md` |

This document converts the governing decisions in `00_PROJECT_OVERVIEW.md` into stable, testable product requirements. Requirement IDs are permanent references. If a requirement changes, its text and acceptance criteria must be revised without reusing its ID for a different concept.

Normative terms **must**, **must not**, **should**, and **may** are used deliberately.

## 2. Product Objective

Create a reliable internal system that discovers, reconciles, enriches, and presents available Studio, 1BR, and 2BR rental listings in NYC, Jersey City, Hoboken, and Fort Lee so the user can manually review and select apartments for a later marketing workflow.

The product is successful when it reduces repetitive listing research while keeping source evidence, freshness, conflicts, and uncertainty visible enough for human review.

## 3. Users and System Actors

### 3.1 Primary user

The sole required human role for the initial version is the internal operator/reviewer. The operator:

- Reviews canonical listings and source evidence
- Filters inventory for current work needs
- Reviews photos, floor plans, amenities, transit, and commute details
- Resolves or flags data-quality issues
- Manually selects apartments for later marketing
- Exports inventory or selected subsets to CSV
- Reviews scheduled-run and source-health failures

### 3.2 System actors

- **Scheduler:** starts the fixed weekday refresh.
- **Source adapter:** acquires observations from one approved listing source.
- **Normalizer:** maps source-specific observations into the normalized contract.
- **Identity resolver:** matches observations to canonical buildings, units, and listings.
- **Reconciler:** determines new, changed, unchanged, missing, reappeared, and inactive states.
- **Enrichment workers:** perform address/geographic, transit, commute, laundry, photo, and floor-plan enrichment.
- **Export service:** generates point-in-time CSV output from authoritative database records.
- **Internal UI:** presents data and records human actions without becoming the source of hidden business logic.

## 4. In-Scope Geography and Inventory

### PR-GEO-001 — Supported geography

The system must admit canonical marketing inventory only for addresses within New York City, Jersey City, Hoboken, or Fort Lee.

**Acceptance criteria**

- A listing with a validated address inside the supported boundary is eligible for further scope checks.
- A listing with a validated address outside the boundary is excluded with a machine-readable reason.
- A listing whose geography cannot be established is held for review or excluded as unresolved; it is not silently assigned to a supported city.
- Boundary logic is based on geographic or administrative data defined in `04_LOCATION_AND_TRANSIT_INTELLIGENCE.md`, not source-provided neighborhood text alone.

### PR-GEO-002 — Supported layouts

The system must support Studio, 1BR, and 2BR listings and must normalize source terminology into these layout classes.

**Acceptance criteria**

- Common studio, alcove-studio, one-bedroom, and two-bedroom source labels can be mapped under explicit rules.
- Listings clearly representing 3BR or larger layouts are excluded from canonical marketing inventory.
- Ambiguous layouts are classified as unknown and flagged rather than guessed.
- Convertible, flex, railroad, home-office, and similar cases follow documented normalization rules and retain their raw description.

### PR-GEO-003 — Rental availability scope

The system must maintain rental listings that sources represent as currently available or recently observed available.

**Acceptance criteria**

- Sale listings and non-residential properties are excluded.
- Availability status retains both normalized state and source evidence.
- Disappearance from a source is handled through lifecycle rules rather than immediate deletion.

## 5. Acquisition and Canonical Inventory Requirements

### PR-ACQ-001 — Approved source registry

Every acquisition adapter must correspond to an approved source-registry entry defining its access method, enabled state, coverage, schedule, rate constraints, and operational owner.

**Acceptance criteria**

- An unregistered or disabled source cannot run in a production refresh.
- Each acquired observation records its source and retrieval time.
- Source-specific compliance, access, and retention constraints can be configured and audited.

### PR-ACQ-002 — Source observations

The system must preserve source observations separately from canonical normalized records.

**Acceptance criteria**

- Reprocessing an identical observation is idempotent.
- Raw or minimally transformed source evidence needed for audit is retained subject to the approved source policy.
- Parsing or normalization failures do not destroy the acquired observation.

### PR-ACQ-003 — Canonical inventory

The system must reconcile one or more source observations into a canonical inventory without erasing their provenance.

**Acceptance criteria**

- A canonical listing can reference multiple source records.
- The UI can expose the sources supporting a canonical fact.
- Conflicting values are not resolved by undocumented last-write-wins behavior.
- Identity decisions and confidence/status are auditable.

### PR-ACQ-004 — Deduplication safety

The system must prefer reviewable duplicate candidates over unsafe automatic merges when identity evidence is insufficient.

**Acceptance criteria**

- Exact and probabilistic match rules are separately defined.
- Automatic merge thresholds and non-merge conditions are testable.
- A human can review unresolved duplicate candidates.
- Manual split/merge corrections persist across later refreshes unless explicitly reversed.

### PR-ACQ-005 — Contact-data exclusion

The system must not intentionally collect or enrich broker, agent, landlord, leasing-office, phone, email, or other contact information.

**Acceptance criteria**

- No canonical contact entity or contact field is defined for the product.
- Source parsers ignore contact sections when they are not needed to identify the listing.
- Contact text incidentally present in retained raw source material is not surfaced, extracted, exported, indexed for use, or passed to downstream marketing workflows.

### PR-ACQ-006 — Material change detection

The system must distinguish material listing changes from unchanged re-observations.

Material changes include, at minimum, changes to price, availability, unit/layout identity, move-in date when available, laundry classification evidence, description-derived amenities, source URLs, and media set.

**Acceptance criteria**

- Material changes create timestamped history.
- Unchanged observations update freshness without generating duplicate history events.
- A field change triggers only the enrichments whose inputs or outputs may be affected.

## 6. Listing Data Requirements

### PR-DATA-001 — Core listing facts

For every canonical listing, the system must support the following facts where available:

- Canonical listing identifier
- Building and unit association
- Normalized and source address representations
- Geography and coordinates
- Supported layout class and raw layout description
- Bedrooms and bathrooms
- Monthly asking rent and currency
- Availability and listing lifecycle status
- Available-from or move-in date
- Unit/building description and non-contact amenity evidence
- Source observation references and timestamps
- First-seen, last-seen, changed, and inactive timestamps
- Manual review and marketing-selection state

Exact field definitions and null semantics belong to `02_LISTING_DATA_SCHEMA.md`.

### PR-DATA-002 — Evidence and provenance

Important normalized or derived facts must retain sufficient evidence to explain their origin.

**Acceptance criteria**

- The system can identify whether a value is source-stated, derived, inferred, manually corrected, or unknown.
- Source-stated and derived timestamps are distinguishable.
- Conflicting evidence can coexist pending resolution.

### PR-DATA-003 — Human overrides

The system must preserve approved human corrections and prevent routine refreshes from silently overwriting them.

**Acceptance criteria**

- The original machine/source value remains auditable.
- An override records value, field, time, reason, and actor.
- Override precedence and invalidation rules are explicit.
- New conflicting source evidence is surfaced for review without automatically discarding the override.

### PR-DATA-004 — Unknown and conflict handling

The system must distinguish missing, unknown, not applicable, conflicting, and explicitly negative values where the distinction affects review or downstream use.

**Acceptance criteria**

- Null is not used as an undocumented catch-all for semantically different states.
- The CSV export renders these states predictably.
- Later marketing inputs cannot treat unknown as affirmative.

## 7. Laundry Requirements

### PR-LAUNDRY-001 — Laundry classification

The system must classify laundry evidence without conflating in-unit equipment with building/shared laundry.

The normalized model must support at least:

- In-unit washer and dryer
- In-unit washer only
- In-unit dryer only
- In-unit hookup only
- Shared/building laundry
- No laundry stated
- Conflicting evidence
- Unknown

### PR-LAUNDRY-002 — Laundry evidence

Laundry classification must retain the source text, structured amenity, image-derived evidence if later approved, manual evidence, or combination that produced the result.

**Acceptance criteria**

- “Laundry in building” cannot result in an in-unit classification.
- “Washer/dryer hookup” cannot result in an installed in-unit washer-and-dryer classification.
- Conflicting source statements produce a conflict or review state.
- The affirmative `室内洗烘` eligibility flag is derived only from a confirmed in-unit washer-and-dryer state.

## 8. Media and Floor-Plan Requirements

### PR-MEDIA-001 — Apartment photos

The system must collect available apartment photos for eligible listings with source, retrieval time, source URL or asset reference, order, and association metadata.

**Acceptance criteria**

- Duplicate images within or across source observations can be detected or flagged.
- Photo failures do not prevent the text listing from entering inventory.
- The UI distinguishes apartment/unit photos from building, amenity, neighborhood, map, logo, and floor-plan images where determinable.
- Asset handling follows source-specific retention and usage rules.

### PR-MEDIA-002 — Floor-plan availability

The system must collect a floor plan when one is available for the relevant Studio, 1BR, or 2BR layout.

**Acceptance criteria**

- A floor plan may be associated with a building and layout class rather than an exact unit.
- The association level is explicit: exact unit, source-asserted unit type, building-plus-layout, or uncertain candidate.
- A building-plus-layout floor plan is not presented as an exact-unit plan.
- Floor plans retain provenance, confidence/status, and review state.
- An exact-unit floor plan may be identified only when supported by explicit source evidence.

### PR-MEDIA-003 — Media quality and selection readiness

The system should store enough technical metadata to support later review and composition, including dimensions, format, checksum/perceptual signature where appropriate, and detected media type.

This requirement does not authorize image generation, image composition, or ad generation.

## 9. Location and Transit Requirements

### PR-LOC-001 — Address normalization and geocoding

The system must normalize and geocode listing locations with provenance and precision status.

**Acceptance criteria**

- Exact, interpolated, building-level, approximate, and unresolved results are distinguishable.
- Low-precision coordinates cannot silently support high-precision walking claims.
- Geocoding changes trigger relevant transit and commute re-enrichment.

### PR-TRANSIT-001 — NYC subway access

For NYC listings, the system must identify nearby useful MTA subway access, including station, served line(s), walking time, and walking distance.

**Acceptance criteria**

- Station-complex identity is handled consistently.
- Lines are tied to the relevant station/complex and data version.
- Walking time and distance identify their calculation source.
- Closed, inaccessible, or non-serving entrances/stations are not treated as valid without appropriate status handling.

### PR-TRANSIT-002 — PATH access

For Jersey City and Hoboken listings, the system must identify PATH access where relevant, including station/service information, walking time, and walking distance.

**Acceptance criteria**

- Lack of relevant PATH access is represented honestly rather than populated with an implausible distant station.
- PATH information remains distinct from MTA subway data while supporting a unified review display.

### PR-TRANSIT-003 — Useful bus access

For every supported area, the system must collect useful nearby bus stops, routes, walking time, walking distance, and meaningful connections.

**Acceptance criteria**

- Bus enrichment is not limited to Fort Lee.
- “Useful” is based on documented factors such as service direction, frequency data when available, direct connections, destination access, stop accessibility, and walking burden.
- The closest stop is not automatically labeled the most useful.
- Stop, route, operator, direction, and connection information are represented separately where the source data allows.

### PR-TRANSIT-004 — Fort Lee transit representation

Fort Lee results must emphasize useful bus routes and connections and must not imply nearby walkable subway access where none exists.

**Acceptance criteria**

- Fort Lee records can prominently show bus access to meaningful connections or destinations.
- A subway reached only after a bus or other transfer is represented as a connection, not as the listing’s nearby subway station.

### PR-TRANSIT-005 — Nearest versus useful options

The system must preserve the distinction between geographic proximity and practical usefulness.

**Acceptance criteria**

- Candidate options can store straight-line distance, routed walking distance/time, and usefulness attributes separately.
- The UI can present more than one relevant transit option.
- No hidden composite transit or commute score is used to select or rank listings.

## 10. Commute Requirements

### PR-COMMUTE-001 — Web-researched commute estimates (revised 2026-08-17)

The system must obtain public-transit commute information as **web-researched
estimates** produced by the default hosted model using approved web-search/browser
tools. Paid navigation/routing APIs (Google Geocoding, Routes, Places, Map Tiles)
are not used. Commute research is **on-demand**: it runs only for shortlisted,
selected, or explicitly requested listings, never as bulk enrichment.

**Acceptance criteria**

- Each result is stored as a `RESEARCHED_ESTIMATE` with duration range, likely
  routes/transfers, cited sources, research timestamp, confidence, and validation
  status — never as an authoritative provider route.
- Commute times are never generated from model memory; a result without web-tool
  source citations is rejected.
- Cached research results are reused for 14 days unless origin, destination, or
  registry version changes.
- Research failure produces an explicit unavailable/error state, not a fabricated
  estimate.
- The UI labels results as web-researched estimates and offers manual verification
  through the free Google Maps Embed directions view.

### PR-COMMUTE-002 — Internal validation

Commute research results must be cross-checked by an internal transit/geographic validation algorithm, including cross-checking named routes and stations against local MTA, PATH, and NJ Transit data.

**Acceptance criteria**

- Validation checks geographic plausibility, access and egress plausibility, mode appropriateness, route topology where data permits, and anomalous duration/distance relationships.
- Validation preserves the provider result and records pass, warning, fail, or unable-to-validate status with reasons.
- A failed validation is surfaced for review and does not automatically become a replacement duration.
- The algorithm does not create a commute score.

### PR-COMMUTE-003 — Campus registry

The system must calculate commute information to the following initial campus registry:

- NYU Washington Square
- NYU Tandon
- Columbia University
- Pratt Institute
- Parsons School of Design / The New School
- Fashion Institute of Technology (FIT)
- School of Visual Arts (SVA)
- Baruch College
- Hunter College
- Fordham campuses, represented separately where relevant
- Stevens Institute of Technology
- Other major relevant colleges added through the controlled registry

**Acceptance criteria**

- Separate campuses have separate stable identifiers and routing anchors.
- Institution display names can change without invalidating historical route results.
- New destinations can be added without schema changes.

### PR-COMMUTE-004 — Major destination registry

The system must calculate commute information to:

- West Village
- Central Park
- Union Square
- Times Square
- World Trade Center / Financial District
- Grand Central
- Williamsburg
- Downtown Brooklyn

**Acceptance criteria**

- Each destination has an approved, stable routing anchor and human-readable label.
- Broad areas such as Central Park, West Village, Williamsburg, and the Financial District use documented representative anchors rather than unstable free-text geocoding.

### PR-COMMUTE-005 — No commute score

The system must not calculate, persist, display, or export a commute score or aggregate destination score.

Individual duration, distance, route, transfer, and validation facts may be filtered or displayed without being collapsed into a score.

## 11. Refresh and Lifecycle Requirements

### PR-REFRESH-001 — Fixed weekday schedule

The system must automatically refresh inventory every weekday on a fixed configured schedule.

**Acceptance criteria**

- Schedule time and time zone are explicit configuration.
- The initial planning time zone is `America/New_York` unless superseded in `06_DATABASE_AND_REFRESH_PIPELINE.md`.
- Manual runs can be distinguished from scheduled runs.
- A missed or failed scheduled run is visible to the operator.

### PR-REFRESH-002 — Incremental enrichment

New and materially changed listings must receive required enrichment. Unchanged listings should reuse valid enrichment until freshness or dependency rules require recomputation.

**Acceptance criteria**

- Enrichment dependencies are defined by input field and data version.
- Retryable enrichment failures enter a retry state.
- Partial enrichment does not make an otherwise valid listing disappear.

### PR-REFRESH-003 — Disappearance and inactivity

A listing not observed during a refresh must not be hard-deleted and must not necessarily become inactive after one miss.

**Acceptance criteria**

- Inactivity uses documented grace/consecutive-miss rules.
- Source health gates disappearance processing.
- A failed, blocked, or suspiciously incomplete source run cannot mass-inactivate inventory from that source.
- Inactive listings retain history and may later transition to reappeared/active.

### PR-REFRESH-004 — Run auditability

Every refresh and enrichment job must be auditable.

**Acceptance criteria**

- Run start/end, trigger, status, source counts, new/changed/unchanged/missing/inactive counts, errors, and retries are persisted.
- The operator can identify which stage failed.
- Re-running a safely retryable stage does not duplicate canonical effects.

## 12. Internal UI and Review Requirements

### PR-UI-001 — Internal interface

The initial frontend should be implemented as an internal Streamlit application unless `07_INTERNAL_UI.md` documents a justified change.

### PR-UI-002 — Inventory review

The UI must allow the operator to browse and filter canonical inventory.

Required filter categories include:

- City/area and normalized neighborhood where available
- Active/inactive and lifecycle state
- Studio/1BR/2BR
- Rent range
- Laundry classification
- Transit mode/access facts
- Source freshness
- Enrichment completeness or warnings
- Manual marketing-selection state

### PR-UI-003 — Listing detail review

The UI must show, for one canonical listing:

- Core facts and freshness
- Source observations and relevant provenance
- Price and status history
- Laundry classification and evidence
- Photos grouped or typed where possible
- Floor plans with association level and disclaimer
- Nearby subway/PATH/bus options as geographically appropriate
- Campus and major-destination commute results with validation status
- Data conflicts, warnings, and enrichment failures

### PR-UI-004 — Manual marketing selection

The operator must manually select and deselect listings for later marketing work.

**Acceptance criteria**

- Selection is stored in Postgres/Supabase, not only in browser/session state.
- Selection changes record time and actor.
- Automatic refresh does not silently select a listing.
- Inactivation does not erase historical selection, but the UI warns when a selected listing is no longer active.

### PR-UI-005 — Review actions and corrections

The UI must support review status, issue flagging, and approved manual corrections under the precedence rules defined in `02_LISTING_DATA_SCHEMA.md`.

### PR-UI-006 — Operational visibility

The UI must expose enough run and source-health information for the operator to detect stale or incomplete inventory.

It need not replace a full infrastructure monitoring system.

## 13. Export Requirements

### PR-EXPORT-001 — CSV as export

CSV must be generated from Postgres/Supabase as a point-in-time export and must not act as the primary store or a bidirectional synchronization mechanism in the initial version.

### PR-EXPORT-002 — Export scope

The operator must be able to export at least:

- The currently filtered inventory
- Manually selected listings
- A defined operational review view containing key enrichment and warning fields

**Acceptance criteria**

- Export time and filter scope are identifiable.
- Canonical listing IDs are included.
- Contact data is absent.
- Unknown, conflicting, and not-applicable states are encoded consistently.
- Multi-valued transit and commute data use a documented flattened or companion-file convention.

## 14. Cost-Control and LLM Requirements

### PR-COST-001 — Deterministic-first processing

The system must not use an LLM for work that deterministic parsing, structured source fields, database rules, geospatial computation, image hashing, or routing APIs can perform reliably.

### PR-COST-002 — Optional LLM boundary

An LLM may be used for bounded normalization or evidence extraction from unstructured listing text, such as amenity/laundry extraction or ambiguous layout interpretation, only when:

- The input and output contract is schema-constrained.
- The model returns evidence spans or source references.
- Unknown/conflict outcomes are supported.
- Results are validated before changing canonical facts.
- The task can be disabled or escalated without breaking acquisition.

### PR-COST-003 — Tiered model routing

If LLM processing is used, the implementation should route routine high-volume extraction to the least expensive model that passes the task evaluation set and escalate only low-confidence, conflicting, or failed cases to a stronger model.

### PR-COST-004 — Reuse and budget controls

LLM work must be cached by normalized input plus prompt/schema/model version. Unchanged text must not be reprocessed solely because another weekday refresh ran.

The pipeline must support per-run usage counts, token/cost accounting where available, concurrency limits, and a configurable budget guard.

## 15. Security, Reliability, and Maintainability

### PR-NFR-001 — Internal access

The application and database must require authenticated internal access appropriate to the deployment environment.

### PR-NFR-002 — Secrets

Source credentials, routing-provider keys, database credentials, and model API keys must not be stored in source code, exported CSV files, logs, or listing records.

### PR-NFR-003 — Fault isolation

A failure in one source or enrichment type must not corrupt successfully processed sources or erase previously valid canonical data.

### PR-NFR-004 — Idempotency and replay

Acquisition, reconciliation, and enrichment stages must be safely retryable under documented idempotency keys and transaction boundaries.

### PR-NFR-005 — Observability

The system must provide structured logs, persisted job states, error categories, and enough metrics/counts to diagnose incomplete refreshes.

### PR-NFR-006 — Testability

Business rules must be expressed outside UI code and covered by deterministic unit or integration tests using saved fixtures where source policy permits.

### PR-NFR-007 — Source change tolerance

Source-specific parsing must be isolated behind adapters with contract tests and failure thresholds so a source-page change does not silently produce mass bad data.

### PR-NFR-008 — Performance target

The weekday refresh must complete within its defined operating window under expected inventory volume. Exact volume, latency, and concurrency targets will be set after source selection and baseline measurement in `06_DATABASE_AND_REFRESH_PIPELINE.md`.

## 16. Explicitly Out of Scope

The following are not authorized by this specification:

- Ad copy or social-post generation
- Image generation or composition
- Adding rent, `室内洗烘`, location, or other text to images
- Automated marketing publication
- Automated marketing selection
- Broker/contact collection or outreach
- Client profiles or client-to-listing matching
- Commute, neighborhood, listing-quality, or recommendation scores
- Public accounts, public search, or commercial SaaS functionality

Later image composition may use monthly rent and the confirmed `室内洗烘` eligibility fact. Location must not be added to the generated marketing image. That workflow requires a separate future specification.

## 17. Product Acceptance Gate

The product requirements are satisfied for an initial production-ready internal release only when:

1. Approved sources can complete a weekday refresh into Postgres/Supabase.
2. Canonical identity and history work across repeated and changed observations.
3. A source failure cannot cause uncontrolled mass inactivation.
4. Supported listings expose photos and available layout-appropriate floor plans with honest association metadata.
5. Laundry evidence correctly distinguishes in-unit washer/dryer from shared/building laundry in the evaluation set.
6. NYC subway, relevant PATH, and universal useful-bus enrichment meet the geography-specific rules.
7. Required campus and major-destination commute results are provider-backed and internally validated without scores.
8. The Streamlit UI supports review, conflict visibility, manual selection, and CSV export.
9. The operator can identify stale sources, failed runs, and incomplete enrichments.
10. No ad generation or contact-data workflow has been introduced.

## 18. Open Decisions Assigned to Later Specifications

| Open decision | Owner document |
| --- | --- |
| Canonical entities, identifiers, enum values, null semantics, overrides | `02_LISTING_DATA_SCHEMA.md` |
| Exact source list, approved access methods, adapter inputs/outputs | `03_LISTING_ACQUISITION.md` |
| Geocoder, routing provider, transit datasets, validation algorithm, destination anchors | `04_LOCATION_AND_TRANSIT_INTELLIGENCE.md` |
| Media storage/retention and floor-plan matching thresholds | `05_MEDIA_AND_FLOORPLANS.md` |
| Database physical model, weekday run time, retries, health gates, inactivity thresholds | `06_DATABASE_AND_REFRESH_PIPELINE.md` |
| Authentication, page design, review actions, correction UX, export UX | `07_INTERNAL_UI.md` |
| Delivery phases and test/deployment gates | `08_IMPLEMENTATION_PLAN.md` |

## 19. Traceability Convention

Downstream documents must cite applicable requirement IDs in their design sections and acceptance tests. If one design satisfies several requirements, all relevant IDs should be listed. A downstream document may make a requirement more precise but may not weaken or silently reinterpret it.

## 20. Change Log

| Date | Change |
| --- | --- |
| 2026-08-16 | Initial product requirements created from `00_PROJECT_OVERVIEW.md` and current Project decisions. |
| 2026-08-17 | Owner decision B7: PR-COMMUTE-001 revised from navigation-provider routes to on-demand web-researched estimates (`RESEARCHED_ESTIMATE`); PR-COMMUTE-002 extended to cross-check named routes/stations against local transit data. No paid Google APIs. |
