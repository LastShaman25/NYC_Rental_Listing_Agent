# PROJECT_EXECUTION_STATE

Machine-readable state for coding-agent sessions. Update after every meaningful step.
Last updated: 2026-08-17 (session 3 — aggregated steps 1–4: acquisition runner,
OpenAI executor/tiering, destinations + map spike, validation gate).

## Current phase

**Phase 1 gate PASSED. Phase 2 vertical slice COMPLETE against fixtures**
(adapter + acquisition runner + observation persistence + NORMALIZE jobs +
canonical creation, end-to-end tested); only the live SearchProvider is missing.
**Phase 3 skeleton in place** (within-source continuity; cross-source matching
pending). Phase 6 commute research implemented with fakes. Phase 0 map spike
DONE (streamlit-folium verified in browser). OpenAI executor + Terra→Sol
tiering ready pending API key.

Phase definitions come from `md/08_IMPLEMENTATION_PLAN.md`.

## Environment facts (verified)

| Item | Status |
| --- | --- |
| Working dir | `C:\Users\CJ\OneDrive\Desktop\NYC_Rental_Listing_Agent` (git repo, branch `main`, **no commits yet**) |
| Python / uv | 3.12 via uv-managed `.venv`; uv 0.9.18 |
| Database | Docker `rental_agent_db` (postgis/postgis:17-3.5) on **port 5433**; databases `rental_dev`, `rental_test`; user `rental` / `rental_local_dev` (local-only credentials, also in `.env.example`) |
| Data volume | Named volume `rental_agent_pgdata` (never bind-mount into OneDrive) |
| Host Postgres | F:\Postgre 17.5 on :5432 — NOT used (no PostGIS, no credentials) |
| OneDrive caveat | Can lock `.venv` during `uv sync`; use `uv run --no-sync` when env unchanged |

## Owner decisions recorded (2026-08-17)

| Decision | Choice |
| --- | --- |
| Spec 08 | Provided by owner; governs phases |
| Dev/test DB | Docker PostGIS in working directory; owner authorized starting Docker |
| **B3** First listing source | **StreetEasy via search-index discovery ONLY** (bounded `site:streeteasy.com` queries through a configurable SearchProvider adapter; snippet extraction; no direct scraping; search absence ≠ inactive; snippet listings marked `discovery_method=SEARCH_INDEX` + PARTIAL). Specs 03 §5.4. Concrete search provider still unconfigured. |
| **B5** LLM tiers | OpenAI: default **gpt-5.6-terra** (reasoning `low`), escalation **gpt-5.6-sol** (reasoning `medium`); Sol only on repeated validation failure / unresolved material conflict; caching + usage/cost tracking preserved. |
| **B7** Maps & commutes | **No paid Google APIs.** Leaflet/streamlit-folium primary map; free Google Maps Embed API on listing detail for manual verification; PostGIS local distance; commutes = **on-demand Terra web-research** stored as `RESEARCHED_ESTIMATE` (sources+timestamp+confidence+validation, cross-checked vs local MTA/PATH/NJT data, never model memory, 14-day cache). Specs 01 PR-COMMUTE-001/002, 04 §19A, 06 §20.3, 07 §15.1. |
| Map tiles | OSM default tiles via folium behind map adapter; final provider deferred to Phase 8 |

Interpretations from session 1 (still controlling): local-only (no Supabase/RLS/cloud),
two profiles (development/production), five Postgres schemas (app/ops/raw/config/audit),
client presets + shortlists per owner kickoff, single-operator id `local_operator`.

## Completed work

1. Read all nine specs; inspected environment (session 1 notes above).
2. Docker PostGIS 17/3.5 up via `docker-compose.yml` + `scripts/db/init/01_create_databases.sh`.
3. Project scaffold: git init, `pyproject.toml` (uv, SQLAlchemy 2.0.44, psycopg3, Alembic,
   GeoAlchemy2, Pydantic v2, structlog; dev: pytest/ruff/mypy), `.gitignore`,
   package layout per 08 §5, `local_data/` conventions.
4. Typed settings (`config/settings.py`): profiles, DB, data paths, provider config
   contracts; `.env.example`; production-profile guard; structlog JSON logging
   (`config/logging.py`).
5. Full Phase 1 schema: **43 tables** in 5 schemas — sources/observations/checkpoints,
   refresh+source runs, addresses (+PostGIS) & assertions, buildings/units/listings/
   links/merges/duplicates, fact assertions/resolutions, amenities, listing events +
   field history, media (asset/variant/association/analysis/dup groups), transit
   (stop/route/stop_route/access/access_route), destinations, commute results,
   provider requests, model executions, jobs (+attempt/dependency, lease fields),
   overrides, review issues, marketing selection, client presets (+map geometry) &
   shortlist entries, audit log. Enums = SQLAlchemy Enum(native_enum=False,
   create_constraint=True) → VARCHAR + named CHECK (92 enum columns).
   Key invariants in DDL: laundry badge CHECK, rent>=0, AVAILABLE-requires-duration,
   observation idempotency partial uniques, single-current fact resolution,
   single-active override, live-job idempotency (NULLS NOT DISTINCT), claimable-job
   partial index, 4 GiST spatial indexes.
6. Alembic baseline `migrations/versions/9bb44a1b5855_baseline_schema.py`
   (auto-generated, patched with schema+extension bootstrap). Note: earlier
   f332e22b9589 was regenerated away after enum-CHECK fix; DBs were reset.
7. Contracts: `contracts/observation.py` (ParsedSourceObservation 1.0.0, extra=forbid),
   `contracts/providers.py` (Geocoder, Router, TransitDatasetLoader, LlmExecutor,
   SourceAdapter, MapAdapter Protocols), `contracts/fakes.py` (deterministic doubles).
8. Repositories/services: ObservationRepository (idempotent insert),
   RefreshRunRepository (create_or_join on logical run key), JobQueue (SKIP LOCKED
   claim, lease/heartbeat/complete/recover, retry exhaustion),
   MarketingSelectionService + ClientShortlistService (human-only, audited),
   `validation/laundry.py` badge derivation, `config/source_seed.py` (candidates
   PROPOSED/disabled incl. streeteasy, google_maps_platform, MTA/PATH/NJT feeds).
9. Tests: 45 passing (unit: badge, schema purity incl. no-contact/no-score/no-cloud,
   settings, contracts; integration: PostGIS, constraints, geography roundtrip,
   spatial indexes, queue semantics incl. concurrent-claim exclusivity + lease
   recovery, selection/shortlist independence + SYSTEM-actor rejection, repository
   idempotency, run join, seed). conftest rebuilds rental_test from migrations
   each session (fresh-setup verification built into CI path).
10. README.md with setup/commands/invariants.

Session 2 (B3/B5/B7 implementation):

11. Spec updates with change-log rows: 00 (§11 closures), 01 (PR-COMMUTE-001/002
    revised), 02 (§16.3 commute fields + discovery_method), 03 (§5.4 search-index
    discovery), 04 (§19A research model, §5.2 stack), 06 (§20.3 on-demand
    COMMUTE_RESEARCH), 07 (§15.1 estimate display + Embed API), 08 (§19.1 model IDs).
12. Migration `093c9fc3a73e`: commute_result += result_type / model_execution_id /
    duration_min_s / duration_max_s / sources / confidence; provider_request_id now
    nullable; CHECKs research_requires_sources, provider_route_requires_request,
    duration_range_ordered; available_requires_duration widened to ranges;
    listing_source_link += discovery_method; SourceType += SEARCH_INDEX.
13. `SearchProvider` interface + `FakeSearchProvider`; `StreetEasySearchAdapter`
    (acquisition/adapters/streeteasy_search.py): 12 bounded borough×layout
    site-queries, URL canonicalization, deterministic snippet parsing (price band
    guard, layout, address/unit regex), contact redaction, PARTIAL observations,
    failed-search ⇒ truncated/degraded page (never "zero listings").
14. `CommuteResearchService` (enrichment/commute/research.py): schema-constrained
    Terra output, rejects memory-only output (no sources), 14-day cache with reuse,
    station/route cross-check vs local transit tables (UNABLE_TO_VALIDATE /
    WARNING / PASSED), persists ModelExecution + RESEARCHED_ESTIMATE rows.
15. Settings: Terra/Sol model IDs + reasoning efforts, search-provider config,
    commute_research_cache_days=14, google_maps_embed_enabled; .env.example synced.
16. Tests expanded to 57 (adapter contract suite + commute research suite +
    DB constraint for sources requirement).
17. **Phase 3 skeleton**: `canonical/normalization.py` NormalizationService —
    within-source identity continuity, NEW → address(fingerprint-dedup)/building/
    listing/SEARCH_INDEX-link/CREATED-event chain, UNCHANGED → freshness-only,
    changed content → PRICE_CHANGED / AVAILABILITY_CHANGED events with
    before/after values, all idempotent under replay via event idempotency keys.
    Address fingerprint normalizes suffix/directional variants so two source
    listings at "225 East 34th Street" and "225 E 34th St." share one building.
    Cross-source matching + duplicate candidates remain future Phase 3 work.
    Tests now **63 passing**.

Session 3 (aggregated steps, owner-directed):

18. **Step 1 — Acquisition runner** (`acquisition/runner.py`): adapter →
    create-or-join refresh run → source run → checkpointed partitions with
    intra-run identity dedup (03 §20) → idempotent observation persistence →
    NORMALIZE job enqueue → `drain_normalize_jobs` worker → health evaluation.
    SEARCH_INDEX runs always have `health_gate_passed = false`. Failed search
    providers degrade the run; canonical data untouched. 6 integration tests.
19. **Step 2 — OpenAI executor** (`enrichment/llm/openai_executor.py`,
    Responses API, config-driven model/effort, untrusted-data prompt posture,
    web_search tool only for commute_research) + **tiering**
    (`enrichment/llm/tiering.py`: 1 Terra call → 1 repair on schema failure →
    1 Sol escalation → human review; hard 3-call bound). `openai` dependency
    added. 8 unit tests with stub clients. Live smoke test pending API key.
20. **Step 3 — Destination seed** (`config/destination_seed.py`: all 20 anchors
    from 04 §18, registry_version `v0-provisional-unreviewed`, coordinates need
    human review before production commute use) + **FoliumMapAdapter**
    (`ui/map_adapter.py`: clustering, polygon/rectangle Draw, approximate-location
    labeling for low precision) + **map-first Streamlit spike** (`ui/app.py`:
    sidebar filters, marker map, synchronized table, honest no-coordinates
    handling). Verified live in browser against rental_dev (2 demo listings,
    map iframe + dataframe render). `.claude/launch.json` added
    (`preview_start` name: rental-agent-ui). Demo rows in rental_dev are
    prefixed `DEMO ` for later cleanup.
21. **Step 4 — Validation gate**: see below; uv.lock updated with
    streamlit/folium/streamlit-folium/openai.

## Validation results (2026-08-17)

Session 3 validation (2026-08-17): **82 passed** (unit + contract + integration
on real PostGIS; conftest rebuilds rental_test from migrations each session, so
fresh-apply is re-verified); ruff clean; mypy clean (50 files); Streamlit spike
verified rendering live (map iframe + dataframe + filters).

Session 2 re-validation (2026-08-17): **57 passed**; ruff clean; mypy clean
(43 files); full `downgrade base → upgrade head` and stepwise `-1 → head` cycles
OK on rental_test with both migrations.

Session 1 results:

| Check | Command | Result |
| --- | --- | --- |
| Tests | `uv run pytest` | **45 passed** (0 failed, integration not skipped) |
| Lint | `uv run ruff check src tests migrations` | All checks passed |
| Format | `uv run ruff format ...` | Applied |
| Types | `uv run mypy` | Success, 41 files, 0 errors |
| Fresh migration | drop schemas → `alembic upgrade head` | OK (43 tables) |
| Reapply | `alembic downgrade base` → `upgrade head` | OK (43 tables) |
| Constraints | pg_constraint contype='c' in app/ops/raw/audit | 101 CHECKs present |
| Spatial | GiST indexes on address/transit_stop/destination/client_search_preset | 4 present |
| No cloud deps | test_no_cloud_dependencies | PASS |
| No contact fields | test_no_contact_columns / contract forbid-extra | PASS |
| Selection⊥shortlist | test_selection_and_shortlist_are_independent | PASS |
| No auto-selection | SYSTEM actor raises HumanActionRequired | PASS |

## Work in progress

None — session 1 milestone complete. Repo has NO git commits yet (awaiting owner
preference on committing).

## Pending tasks (next sessions)

1. Concrete SearchProvider implementation once owner picks/provisions one
   (search API with `site:` support); config key exists; everything else in the
   Phase 2 slice is ready and fixture-tested.
2. Live OpenAI smoke test once RENTAL_PROVIDER_OPENAI_API_KEY is set (executor
   built; wire-tested with stubs only).
3. Phase 3 completion: cross-source identity matching, duplicate candidates,
   fact assertions/resolutions wiring, override precedence enforcement in
   normalization, listing_field_history writes.
4. Destination anchor review: owner confirms/adjusts the 20 provisional
   coordinates, then bump registry_version (invalidates nothing yet — no
   commute results in production).
5. MTA/PATH/NJT feed loaders (Phase 4); transit_service_calendar table then.
6. `config.*` policy tables when acquisition runs live (06 §6.1).
7. Full Phase 8 UI build-out on the spike (listing detail, review queue,
   selection/shortlist pages, exports); Windows Task Scheduler scripts (Phase 7).
8. Clean up `DEMO ` rows from rental_dev before real acquisition.

## Blocking decisions

| # | Decision | Status |
| --- | --- | --- |
| B3 | ~~StreetEasy access method~~ **RESOLVED 2026-08-17**: search-index discovery. Remaining: choose/provision the concrete search provider + API key | PARTIALLY OPEN |
| B5 | ~~Model IDs~~ **RESOLVED 2026-08-17**: gpt-5.6-terra(low)/gpt-5.6-sol(medium). Remaining: OpenAI API key + spend warning values | PARTIALLY OPEN |
| B7 | ~~Routing provider~~ **RESOLVED 2026-08-17**: no paid APIs; research model implemented | CLOSED |

## Important implementation choices (durable)

- Enum storage: `Enum(native_enum=False, create_constraint=True, validate_strings=True)`.
  Alembic autogenerate DOES NOT emit column-level CheckConstraint objects passed to
  mapped_column — that approach was abandoned; do not reintroduce it.
- Alembic env: URL from `ALEMBIC_DB_URL` env var else app settings; geoalchemy2
  alembic_helpers wired (spatial tables render as create_geospatial_table).
- Tests import via pytest `pythonpath=[".", "src"]` — resilient to OneDrive venv locks.
- Job queue: claim = SELECT ... FOR UPDATE SKIP LOCKED + lease token; completion
  requires token; expired leases → FAILED_RETRYABLE; exhausted → FAILED_TERMINAL.
- Selection/shortlist writes require ActorType.HUMAN (service-level, tested).
- Media/raw bytes: relative paths under `local_data/` roots.

## Owner decisions 2026-08-17 (session 3, second round)

- Search provider: **Google Programmable Search Engine** — implemented
  (`acquisition/search_google_pse.py`, wire-tested with injectable fetcher;
  pagination, 429/403→RATE_LIMITED, key never logged). Awaiting owner-created
  engine (restricted to streeteasy.com) + API key + engine id in `.env`
  (`RENTAL_PROVIDER_SEARCH_PROVIDER_API_KEY`, `RENTAL_PROVIDER_GOOGLE_PSE_ENGINE_ID`).
- Anchor review: review map generated and delivered
  (`local_data/exports/destination_anchor_review.html`); awaiting owner feedback,
  then bump registry to v1-reviewed.
- Git: owner said NOT YET — do not commit until instructed.

## Session 3, third round (2026-08-17)

- Owner provided Google PSE credentials in chat; written to gitignored `.env`
  (key AIza…zbY, engine id 85442b4559ef84e3a). **Key was exposed in chat: owner
  should restrict it to Custom Search API and consider rotating.**
- Live smoke test result: **HTTP 403 PERMISSION_DENIED — "This project does not
  have the access to Custom Search JSON API."** The owner must enable the
  Custom Search API for the key's Google Cloud project
  (console.cloud.google.com/apis/library/customsearch.googleapis.com → Enable).
  Provider wire code confirmed working (real round-trip, typed error mapping).
- **Phase 3 increment shipped**: cross-source identity in
  `canonical/normalization.py` (rule version phase3-skeleton-2) —
  `unit_fingerprint` normalization ('APT 12-B' ≡ '12B'); exact building+unit →
  second source attaches to the existing listing (EXACT_ADDRESS_AND_UNIT link,
  one canonical listing, two provenance links); same building+layout+rent
  within RENT_SIMILARITY_TOLERANCE (0.02, calibration input) → PENDING
  duplicate_candidate with evidence, no auto-merge; replay-safe via
  on_conflict_do_nothing. 5 new tests (tests/integration/test_cross_source_identity.py).

## Session 3, fourth round (2026-08-17)

- Owner enabled Custom Search API but 403 persists → background probe retrying
  ~13 min (suspect: API enabled in a different GCP project than the key's).
  Owner told how to verify project match. Owner said keep building meanwhile.
- **Phase 3 merge/split service shipped** (`canonical/merge_service.py`):
  merge_listings (links move with moved_link_ids recorded, source → MERGED,
  MERGED event, audit row, target freshness absorbed; MANUAL merges require
  HUMAN actor; cannot merge into a merged target), reverse_merge (links return,
  source → REVIEW_REQUIRED — never guesses lifecycle), resolve_duplicate_candidate
  (CONFIRMED_DUPLICATE → merge into chosen survivor; CONFIRMED_DISTINCT durable,
  re-resolution rejected; linked review issues auto-resolve).
  Normalization now opens a WARNING DUPLICATE_CANDIDATE review issue whenever it
  creates a PENDING candidate. 6 new tests (test_merge_service.py).

## Session 3, fifth round (2026-08-17)

- **Google PSE dead end CONFIRMED via web sources**: Custom Search JSON API is
  closed to new customers (2025) and shuts down 2027-01-01; new projects always
  get our 403. Probe stopped; google_pse provider module and its tests removed;
  the now-useless Google key removed from .env (owner may delete/rotate it in
  the console; the GCP project can be kept for the free Maps Embed API later).
- **Owner decision: Tavily** as search provider. Implemented
  `acquisition/search_tavily.py`: site: tokens → hard `include_domains`
  restriction, max_results capped at 20, Bearer auth, 429→RATE_LIMITED,
  injectable poster; 6 wire tests. Adapter unchanged (SearchProvider interface).
  Free tier ~1,000 credits/mo vs our ~250-400/mo cadence.
- Awaiting owner: Tavily key (tvly-…) in .env `RENTAL_PROVIDER_SEARCH_PROVIDER_API_KEY`.

## Session 3, sixth round (2026-08-17) — FIRST LIVE ACQUISITION

- **Tavily live: WORKING.** Smoke test returned 10 real StreetEasy results.
- **First bounded live acquisition run completed** into rental_dev
  (logical key `live_bounded:<date>:1`): 12 partitions, 42 discovered,
  **39 canonical listings created** (16 STUDIO $1,190–1,700; 9 ONE_BEDROOM
  $1,750–2,099; 6 TWO_BEDROOM; 5 correctly OUT_OF_SCOPE; 3 UNKNOWN), all links
  discovery_method=SEARCH_INDEX. Run status DEGRADED + health_gate=False —
  correct for search discovery (truncated-looking results; absence never counts).
  Note: many Tavily results are borough landing pages filtered out by URL
  canonicalization; snippet-depth tuning (pagination/query variants) is a
  calibration task.
- streeteasy source row now APPROVED + enabled, policy search-index-1,
  access_method OTHER_APPROVED.
- **OpenAI: key valid but account has NO CREDITS** (`credit_balance_exhausted`).
  Owner must add prepaid credits; then rerun smoke. .env fix applied: owner's
  key was under `OPENAI_KEY`, moved to `RENTAL_PROVIDER_OPENAI_API_KEY`;
  duplicate Tavily line cleaned.
- Anchor review map re-sent to owner; still awaiting feedback.

## Session 3, seventh round (2026-08-17) — ALL PROVIDER GATES CLEARED

- **OpenAI live: WORKING.** Owner added $10 credits. Terra (low) and Sol (medium)
  both passed structured-extraction smoke (Terra 179in/48out tokens; both
  correctly classified "laundry in building" as building scope).
  Note: owner's key was misnamed `OPENAI_KEY` in .env → moved to
  `RENTAL_PROVIDER_OPENAI_API_KEY`.
- **Anchors APPROVED by owner** → registry promoted to `v1-reviewed-2026-08-17`
  (seed module + 20 DB rows + audit row + test updated).
- **First LIVE commute research succeeded end-to-end**: 242-09 Jamaica Avenue
  (Bellerose, live-acquired 1BR) → Columbia Morningside: RESEARCHED_ESTIMATE
  70–95 min, 1 transfer, plausible LIRR→Penn→1-train route, 5 cited web sources
  (MTA schedules, StreetEasy building page), confidence MEDIUM, validation
  honestly UNABLE_TO_VALIDATE (no local transit dataset yet — Phase 4), 14-day
  expiry, model execution linked.
- Fix shipped en route: first live attempt was REJECTED by schema validation
  (system working as designed — Terra invented its own JSON shape because the
  prompt never included the schema). `LlmTaskRequest.output_schema` added;
  executor embeds the JSON Schema + strict output instructions;
  CommuteResearchService passes `CommuteResearchOutput.model_json_schema()`.

## Session 3, eighth round (2026-08-17) — FACT PROVENANCE SHIPPED

- **Fact assertion/resolution wiring complete** (`canonical/facts.py` +
  normalization integration): every rent/layout/laundry/availability value now
  gets a `fact_assertion` (evidence text, source observation, confidence,
  SOURCE_TEXT derivation) and exactly ONE current `fact_resolution`
  (RECENCY method, rule `recency-1`); prior resolutions superseded, never
  deleted. Assertions recorded on create AND on every material re-observation.
- **Override precedence enforced** (02 §18.2): an ACTIVE human_override blocks
  materialized updates for its field; conflicting evidence still recorded as
  assertions and opens ONE deduped OPEN CONFLICT review issue (respecting
  `review_on_new_conflict`). Verified: override survives two conflicting
  refreshes, materialized value untouched, exactly one open issue.
- **Laundry change handling added** to _update_existing: LAUNDRY_CHANGED event,
  materialized laundry_type update, badge recomputed via
  derive_badge_eligibility — snippet evidence is PENDING validation so
  `indoor_laundry_badge_eligible` stays false (室内洗烘 conservative rule held).
- 4 new tests (test_fact_provenance.py).

## Session 3, ninth round (2026-08-17) — SEARCH DEPTH CALIBRATED

- **Live calibration experiment** (9 queries): borough-baseline queries yielded
  ~0% individual listing URLs; adding the keyword **"building"** to the query
  → 26–40% yield; neighborhood-level queries comparable-or-better. Applied:
  query template now ends "rental building"; GEOGRAPHY_TERMS expanded from 4
  boroughs to **8 partitions** (+ Upper East Side, Astoria, Bushwick, Harlem)
  → 24 queries/run ≈ 530/month vs 1,000 Tavily free tier.
- **Verified live**: calibrated run discovered 86 → 75 new canonical listings
  (vs 42 → 39 pre-calibration). Search-discovered links total 101. Inventory:
  39 STUDIO / 34 ONE_BEDROOM / 9 TWO_BEDROOM / 11 OUT_OF_SCOPE / 10 UNKNOWN.
  0 pending duplicate candidates, 0 open review issues (live data too sparse
  yet to collide within tolerance).
- Neighborhood partition list is a calibration knob; revisit after several
  weekday runs (add/remove neighborhoods per measured yield + quota headroom).

## Session 3, tenth round (2026-08-17) — PHASE 4 TRANSIT DATA STARTED

- **GTFS static loader shipped** (`enrichment/transit/gtfs_loader.py`):
  stops.txt+routes.txt → TransitDataset → idempotent ingest into
  app.transit_stop/transit_route with parent-station linking, mode mapping
  (route_type→mode; PATH mode override), never fabricates coordinates.
  3 fixture tests (synthetic GTFS zip; re-ingest inserts 0).
  Trips/stop_times topology + transit_stop_route relations = later increment.
- **Live loads into rental_dev**:
  - MTA subway (`rrgtfsfeeds.s3.amazonaws.com/gtfs_subway.zip`, no key):
    1,488 stops / 29 routes / 992 parent links, version `mta-subway-20260817`.
  - PATH (Trillium mirror `data.trilliumtransit.com/gtfs/path-nj-us`):
    64 stops / 7 routes / 51 parent links, mode=PATH.
  - **NJ Transit: PENDING — requires owner registration** at
    developer.njtransit.com (needed for Fort Lee bus data).
  - Feed zips cached under local_data/raw/. mta_gtfs + path_gtfs source rows
    APPROVED+enabled.
- **Commute cross-check upgraded on live data**: stored Bellerose→Columbia
  estimate went UNABLE_TO_VALIDATE → WARNING with all subway/bus routes
  verified (1, F, Q36, M60-SBS matched real MTA routes) and only
  'Bellerose (LIRR)' unmatched (LIRR deliberately not loaded — honest gap).
  Fix en route: route matcher now extracts route-shaped tokens from prose;
  CommuteResearchOutput.likely_routes schema description now demands short
  labels (guides future Terra outputs).

## Session 3, eleventh round (2026-08-17) — PHASE 8 UI WORKBENCH SHIPPED

- **Multipage Streamlit workbench built and browser-verified live** against the
  103-listing inventory. Structure: `ui/queries.py` (read models; one filter
  contract shared by map/table/export per 08 §16.2) + `ui/app.py`
  (st.navigation entry) + `ui/pages/`:
  - **Dashboard**: lifecycle counts, selected count, open issues, transit-stop
    count, recent runs, change feed.
  - **Inventory**: sidebar filters (layout/lifecycle/locality/max-rent/
    selected-only) + folium map + row table with Select/Deselect buttons
    (MarketingSelectionService, human actor) + client-shortlist controls
    (explicit add only; caption states live matches are never auto-saved).
  - **Listing Detail**: header facts + active-override warnings; tabs =
    Overview (source links, redacted description), Evidence & History (fact
    assertions grouped by key with current flags; event timeline), Commutes
    (researched estimates with sources + validation + on-demand "Run web
    research now" via Terra, spinner-bounded), Map (keyless Google Maps embed
    for manual verification, B7).
  - **Review Queue**: pending duplicate candidates with keep-A/keep-B/distinct
    buttons (MergeService), other issues with resolution notes (blocking
    requires a note per 07 §17.5).
  - **Selected**: selected list with inactive warning, formula-safe CSV export
    to local_data/exports (06 §28.5), client shortlists per preset.
  - **Operations**: refresh runs, source runs (health-gate note), job queue.
- Browser-verified: dashboard counts render; inventory shows 103 matches with
  honest "101 lack validated coordinates" note (live listings not geocoded yet);
  Select click persisted and flipped to Deselect; Selected page showed count 1;
  review/operations render; detail page loaded the Bellerose listing with the
  Columbia commute estimate + research button.
- One selection (first inventory row) was made during verification — real
  MarketingSelection row exists in rental_dev.

## Session 3, twelfth round (2026-08-17) — LIVE INVENTORY GEOCODED

- **Free geocoding shipped** (`enrichment/location/geocoders.py` + `service.py`):
  NYC Planning GeoSearch (keyless, authoritative, Pelias accuracy→precision
  mapping) primary; US Census geocoder (keyless, NY+NJ, always
  INTERPOLATED_ADDRESS — never overstated) fallback. GeocodeService: chain with
  first-success, idempotent ops.provider_request per attempt, address gets
  coordinates+precision+provenance; placeholder "[address unresolved]" rows
  SKIPPED (no fabricated coordinates); total failure → geocode_status=FAILED,
  point stays NULL. 6 tests. Boundary-polygon validation still future work
  (boundary_status stays UNRESOLVED).
- **Live run: 85/85 geocoded, 100% via nyc_geosearch, 0 failures**, all
  BUILDING precision; 7 placeholders skipped. Map coverage: **96/103 listings
  now mappable** (was 2/103). Politeness pacing ~4 req/s.
- Data-quality fixes: adapter now carries partition geography labels into
  observations (`_GEO_LABELS`; future listings get a locality immediately);
  existing rows backfilled locality from geocoded borough (85 rows) →
  Brooklyn 30 / Bronx 23 / Queens 22 / Manhattan 19 / Staten Island 2.
  (Staten Island presence noted: borough queries can bleed; still in-scope NYC.)
- nyc_geosearch + census_geocoder auto-registered as GEOCODER sources.

## Session 3, thirteenth round (2026-08-17) — TRANSIT CANDIDATES, SPATIAL FILTERS, BOUNDARIES

1. **Nearby-transit enrichment shipped** (`enrichment/transit/nearby.py`):
   PostGIS ST_DWithin candidates per mode (SUBWAY 1600m, PATH 2000m radii from
   04 §11.2), station complexes only (platform children excluded), inactive
   stops excluded, top-5 per mode ranked by distance. Honesty: straight-line
   only (walking fields NULL until a walking router exists), CANDIDATE/PENDING
   statuses, input_location_hash reuse (unchanged origin = no-op; moved origin
   invalidates + regenerates). **Live: 96 listings → 441 candidate rows; 91
   listings have subway candidates (avg 689 m, min 74 m), 3 PATH.** Detail page
   gained a Transit tab (labeled straight-line, never walking). 3 tests.
2. **Spatial inventory filters shipped**: InventoryFilters gains `bounds` +
   `geometry_geojson`; SQL via ST_MakeEnvelope / ST_GeomFromGeoJSON; unlocated
   listings NEVER match a spatial filter. Inventory page: draw polygon/rectangle
   → filter persists in session state with active-chip + clear button. 3 tests.
3. **Boundary registry + scope validation shipped**: new
   `config.geographic_boundary` table (migration `35bd168251db`);
   loaders for NYC Borough Boundary ArcGIS FeatureServer (official, keyless)
   and Census TIGERweb Incorporated Places layer 4 (BASENAME + STATE='34' —
   NAME carries legal suffixes; Georgia has a Hoboken too). **Live: all 8
   supported regions loaded** (5 boroughs + Jersey City 54.5 / Hoboken 5.1 /
   Fort Lee 7.4 km²) and **87/87 located addresses IN_SCOPE**; 7 placeholders
   stay UNRESOLVED. Bug caught & fixed en route: validation initially ran
   against an empty registry and marked 85 addresses OUT_OF_SCOPE — statuses
   reverted, and validate_boundaries now REFUSES to run with an empty registry
   (unknown never becomes out-of-scope). 2 tests.

## Session 3, fourteenth round (2026-08-17) — PIPELINE COMPLETE, SCHEDULER READY

- **Admission service shipped** (`canonical/admission.py`, rule admission-v1):
  CANDIDATE/REAPPEARED → ACTIVE only when layout admissible + boundary IN_SCOPE
  + precision acceptable + identity non-blocking + ≥1 ACTIVE source link;
  OUT_OF_SCOPE layout/geography → EXCLUDED with event; all unknowns HELD with
  reason counts (never optimistic). Idempotent (ACTIVATED/EXCLUDED events keyed
  by rule version; ACTIVE rows not re-evaluated). 4 tests.
- **Transit usefulness v1 shipped** (`enrichment/transit/usefulness.py`, rule
  usefulness-straightline-v1): subway/PATH complex ≤800 m straight-line →
  USEFUL with DIRECT_*_ACCESS reason + explicit `distance_basis:
  straight_line_only`; others stay CANDIDATE with SERVICE_UNVERIFIED. Never a
  score. 1 test.
- **Weekday refresh coordinator shipped** (`jobs/weekday_refresh.py`, runnable
  via `python -m`): acquisition → normalize jobs → geocode → boundary scope →
  nearby transit → usefulness → admission → refresh_run finalized honestly
  (PARTIAL_SUCCESS when source degraded). Idempotent per local day via
  `weekday_inventory_refresh:<date>:v1`. Commute research deliberately NOT in
  the pipeline (on-demand per B7); no self-scheduling.
- **Task Scheduler installer** (`scripts/schedule/install_task.ps1`): weekdays
  6:00 AM local, StartWhenAvailable, 5h limit, IgnoreNew instances; NOT
  registered by the agent — owner runs it once (README runbook updated with
  install/pause/resume/remove commands).
- **Full pipeline verified LIVE end-to-end in one command**: discovered=76,
  new=74, normalized=74, geocoded=34, activated=**102**, excluded=15, held=28;
  transit usefulness: 385 USEFUL / 233 CANDIDATE. Inventory now:
  **102 ACTIVE / 28 CANDIDATE / 15 EXCLUDED**.

## Exact next step

Owner actions (see final report): run install_task.ps1 when ready for daily
automation; NJT developer registration for Fort Lee buses; approve second
listing source when wanted; git-commit permission still withheld.
Remaining coding backlog (nothing blocking daily use): strong multi-field
cross-source matching (needs 2nd source), disappearance/inactivation for a
directly-verifiable source (never for search-only), walking-route provider for
true walk times, media/floor-plan pipeline (Phase 5), CSV companion exports.
Tests: **125 passing**; ruff/mypy clean. NO git commits by owner instruction.

## Additional durable choices (session 2)

- Alembic env.py filters check constraints named `*_enum` from autogenerate
  (Postgres rewrites their SQL; enum-value changes are hand-written migrations —
  see migration 093c9fc3a73e for the SEARCH_INDEX example).
- In migrations, pass BARE constraint names to op.create_check_constraint /
  op.drop_constraint (naming convention prepends `ck_<table>_` automatically).
- StreetEasy adapter has no detail-fetch: the snippet is the capture; source_status
  stays UNKNOWN because a snippet cannot prove availability.
