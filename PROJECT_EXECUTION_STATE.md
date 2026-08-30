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

## Session 4 (2026-08-18) — BACKLOG FINISHED; OWNER COMMITTED REPO

- Owner made the initial git commit themselves (d3c477e). Commits now allowed
  going forward (owner committed voluntarily); still prefer explicit owner
  instruction before agent-authored commits.
- 29-hour "running task" investigated: only rental_agent_db Docker container
  (normal, healthy); no stray processes; all monitors previously stopped.
- `start_app.bat` created: one-click DB + UI launcher.
- **Backlog completed, all tested:**
  1. CSV companion exports (`exports/csv_export.py`): listings/sources/transit/
     commutes/history.csv, formula-safe, unknown states verbatim; wired into
     Selected page. 2 tests.
  2. Walking routes (`enrichment/transit/walking.py`): FOSSGIS OSRM foot server
     (keyless, fair-use paced), plausibility validation per 04 §12.2
     (speed band 0.5–2.2 m/s, routed>=straight-line-tolerance), provider failure
     leaves fields NULL (straight-line never promoted). **Live: 131/131 rank-1
     candidates routed, 0 failures, 0 warnings.** 4 tests.
  3. Strong multi-field matching in normalization (hierarchy step 3): same
     building + same layout + IDENTICAL rent + cross-source only (same-source
     identical pairs = distinct units!) + exactly one match → attach as
     STRONG_MULTI_FIELD/MEDIUM; ambiguity refuses. The cross-source-only
     refinement was caught by the ambiguity test. 2 new tests.
  4. Disappearance service (`canonical/disappearance.py`): gate-refusal
     (health_gate required — search runs structurally never inactivate),
     ACTIVE→MISSING (1 healthy miss), MISSING→REMOVED (≥2 healthy misses +
     ≥36h), canonical INACTIVE only when unsupported + no lifecycle override,
     in-source reappearance flips MISSING→ACTIVE, mass-inactivation circuit
     breaker (min(50, 25% of active), BLOCKING issue, nothing applied when
     tripped). 5 tests. NOT yet called by the weekday pipeline — activates only
     when a directly-verifiable (non-search) source exists.
  5. Media pipeline core (`enrichment/media/pipeline.py`, Pillow added):
     https-only + domain allowlist + private-host block, size cap, signature-
     based typing (JPEG/PNG/WebP), safe decode, metadata-stripped thumbnails,
     sha256 exact-dup grouping without byte re-storage, per-asset failure
     isolation. 3 tests. Classification/association = later Phase 5.

## Session 4, second round (2026-08-18) — KINETIC MAPVIEW DESIGN APPLIED

- Owner supplied `md/DESIGN.md` ("Kinetic Mapview System"); recorded as
  controlling visual design in 07 changelog. Implemented:
  - `.streamlit/config.toml` theme (palette) + `ui/theme.py` (`apply_theme()`
    CSS: Inter with high-specificity override of Streamlit's Source Sans,
    glass panels/sidebar with blur(12px), 4px radii, 32px compact inputs,
    label-caps headers/metric labels, dense tables, active-nav accent,
    `filter_chips()` renderer, `marker_accent()` status colors).
  - Map redesign (`ui/map_adapter.py`): CartoDB Positron desaturated basemap;
    markers are DESIGN.md rectangular badges — DivIcon, 4px radius, 3px
    left-accent bar (blue=selected, green=ACTIVE, amber=warning, slate=other),
    10px Inter bold label like "1BR $3,400".
  - Inventory page: compact filter chips row (match count + each active filter);
    marker labels use dense layout-short format; lifecycle passed to markers.
  - **use_container_width deprecation fixed everywhere** (→ width="stretch";
    st_folium keeps its own parameter). Server logs verified clean.
  - Robustness found during verification: app used to HANG when the DB
    container was down (owner had closed Docker Desktop). Fixed: engine
    connect_timeout=5 + startup connectivity check with clear
    "Database is not running" error (07 §26). Docker restarted; DB healthy.
- Browser-verified live: Inter active, glass sidebar, 4px metric cards,
  147 badge markers with accent bars on Positron tiles, chips render
  ("145 MATCHES"). Tests **141 passing**; ruff/mypy clean.

## Session 4, third round (2026-08-18) — LAUNCHER FIXED

- Owner reported start_app.bat broken. Root causes found: (1) the .bat had
  LF-only line endings (cmd.exe misparses those, especially the `if (...)`
  block it contained — the Write tool emits LF, so .bat files must be written
  with explicit CRLF); (2) it gave up when Docker Desktop was closed instead of
  starting it.
- Rebuilt: `scripts/start_app.ps1` does the real work (auto-starts Docker
  Desktop via CLI or exe fallback, waits ≤120s for the engine, compose up,
  waits ≤60s for pg_isready, then launches Streamlit; STARTAPP_TEST=1 skips the
  UI launch for testability); `start_app.bat` is now a 4-line CRLF wrapper that
  pauses on failure so errors stay visible.
- **Verified both paths live**: warm start (engine already up) → READY; cold
  start (Docker Desktop fully stopped) → auto-started Desktop → engine ready →
  container started → DB ready → READY, exit 0.

## Exact next step

Owner actions unchanged (scheduler install, NJT registration, second source).
Coding backlog: optional polish only. Suggest commit of design + launcher work.

Design-regression fix (2026-08-18): the Inter `!important` override was breaking
Streamlit's Material Symbols icons (raw ligature text like "keyboard_double_…");
theme.py now re-asserts 'Material Symbols Rounded' on `[data-testid=
"stIconMaterial"]` / `[class*="material-symbols"]`. Read-only st.dataframe
tables (canvas-drawn, unstylable) were replaced with `theme.dense_table()` —
escaped HTML tables with 6px/12px cells, label-caps headers, tonal status
pills, clickable truncated URLs — on Dashboard, Operations, Selected, and
Listing Detail. Streamlit toolbar/deploy chrome hidden; block padding 16px.
Verified live in browser (icon font computed correct, all four pages render).
Gate: 141 tests, ruff, mypy all clean.

Stitch integration + screen implementation (2026-08-18): connected to Google
Stitch's official MCP endpoint (https://stitch.googleapis.com/mcp). Auth truth,
established empirically: the API rejects classic Google API keys AND Bearer
tokens — a Stitch-settings key works ONLY via the `X-Goog-Api-Key` header
(dummy keys get a misleading "API keys are not supported" error; a real Stitch
key succeeds). `.mcp.json` registers the server with header
`X-Goog-Api-Key: ${STITCH_API_KEY}` (user env var, set via setx; native MCP
tools appear next session). `scripts/connect_stitch.ps1` is the diagnostic /
re-registration helper. The owner's Stitch project is "Metro Rental Command
Center" (projects/8071777848628563239), 5 screens; design system = Kinetic
Mapview (same as md/DESIGN.md). Screens' HTML + screenshots cached in the
session scratchpad.

Chinese posts + NJ official sites + NJ no-fee (2026-08-18, owner feedback):
(1) webui/zh.py — deterministic Chinese for facts: LAUNDRY_ZH (enum→中文),
amenity + cuisine substring translation tables (untranslatable items DROPPED,
never shown in English), TRANSIT_MODE_ZH; facts block now fully Chinese
(store/brand names + station names + transit lines stay English per owner
prompt rule 11); trailer adds a no-English rule. Owner prompt file verified:
verbatim + my Chinese-only addendum. (2) OWNER RULE: NJ (JC/Hoboken/Fort
Lee) listings always get 中介费:无中介费 fact line. (3) OFFICIAL-BUILDING-
WEBSITE fallback in listing_content service: when the aggregator page blocks
extraction (apartments.com), Tavily-search "<address> apartments official
website leasing", skip aggregator+.gov/.org domains, extract the candidate,
and REQUIRE the building's street address to appear in the page before
trusting it (wrong-building guard). Live test: hudsonterrace.com found+
enriched for 2175 Hudson Ter. Wired into jobs/detail_enrichment
(search_provider param). (4) New fact-check chip: 🎓/分钟 lines with NO
verified commute facts flagged as fabricated (Fort Lee live draft invented
"Yeshiva University 6分钟"). Live Fort Lee draft otherwise compliant:
中文品类 (咖啡店/韩餐/多米尼加菜), brands kept, 无中介费, price masked.
CAUTION FOR FUTURE SESSIONS: never round-trip source files through PS5.1
Get-Content/WriteAllText without -Encoding — it GBK-mangles UTF-8 (had to
repair service.py mojibake). Gate: 159 tests, ruff, mypy clean.
PENDING: owner asked for all-in-one shutdown — stop_app.bat +
scripts/stop_app.ps1 are WRITTEN (kills 8600/8601 listeners, docker compose
stop, -IncludeDocker switch) but the live shutdown test was interrupted by
the owner; untested end-to-end.

One-click workspace (2026-08-18, owner request): start_app.ps1 now hosts the
FULL environment — [1-3] Docker engine + DB container + readiness, [4/5]
local Qwen GPU server (probes 127.0.0.1:8601; if down, spawns
start_local_llm.ps1 in a minimized PowerShell window — non-blocking, model
ready in ~30-60s), [5/5] uvicorn webui on 8600 + browser open.
STARTAPP_TEST=1 still skips model+UI. Verified live: parse-clean, test mode
passes, and the exact Qwen-launch block restored the (session-orphaned)
model server to GPU-ready. start_app.bat unchanged (CRLF wrapper).

NJ GEOCODING BUG fixed (2026-08-18, owner report: "one in Massachusetts,
none in NJ"): TWO root causes — (1) NYC GeoSearch force-matches ANY input
into the five boroughs, so Fort Lee addresses landed in Queens/Bronx (and
passed boundary checks because the wrong points sit inside NYC polygons!);
(2) normalization stamped administrative_area='NY' for NJ towns (its NJ
check looked for "NJ" in the locality string, but labels are bare "Fort
Lee"), so Census was queried with the wrong state (→ the New-Hampshire-
border point). FIXES in location/service.py: NJ localities skip
nyc_geosearch entirely; query uses admin area NJ; and a NEW post-geocode
verification gate — result must fall inside its claimed locality's boundary
polygon (config.geographic_boundary, all 8 regions) or it is REJECTED (next
provider / honest FAILED; PR-LOC-001 never-place-at-a-guess). normalization
now maps the three NJ towns to 'NJ'. Data repaired: 29 NJ addresses reset +
re-geocoded → Fort Lee 15/17 mapped, JC 9/11, Hoboken 0/1 (fails honestly),
all IN_SCOPE at true NJ coordinates (~40.85,-73.96); 18 transit rows added.
Guard also protects NYC borough labels from cross-borough mismatches. Gate:
159 tests, ruff, mypy clean.

Chained re-acquisition VERIFIED end-to-end (2026-08-18): the owner's 12:36
click ran discard → 3-source discovery (160 discovered, 133 persisted) →
geocode 113 → activate 85 → AUTO-ENRICH 109, in one button. 32 floor plans,
JC 10/10 laundry facts (rent.com extraction confirmed working). Extraction
prompt v3: multi-unit pages now report the LOWEST advertised gross rent
(owner posting rule 4; "THIS unit" made complexes return null). Residual
honest gap: 7 JC + 1 Hoboken complex pages state no extractable price even
at v3 (dynamic pricing widgets) — they stay rent-unknown/hidden from the
map; source links available. NOTE: mid-flight my earlier enrichment task was
wiped by that discard (74 NO_LINK from deleted ids) — harmless, superseded.
NOTE: discard's ops.job TRUNCATE CASCADE also clears ops.model_execution
audit (FK) — accepted under "completely discard".

"No change after re-acquisition" diagnosed (2026-08-18, owner report): the
discard-runs WORKED (owner clicked twice: 12:25+12:30; inventory rebuilt to
133 incl rent_com's 14) but looked unchanged because (a) the persisted map
view never re-fits, so Fort Lee (17 geocoded w/ rent!) sat off-screen;
(b) most rent_com JC/Hoboken snippets lack prices (2/12) and the map hides
rent-unknown listings; (c) acquisition uses ZERO OpenAI — enrichment is the
OpenAI step and each discard wiped it without re-running. FIXES: manual full
re-acquisition now CHAINS detail enrichment automatically (detail_enrichment
refactored to run_detail_enrichment(limit, force) callable; enriched count in
run summary); map gained a "Fit all" button (clears ka-map-view, refits);
enrichment sweep launched for the current fresh inventory. Gate: 159 tests,
ruff, mypy clean.

Third source + reset semantics (2026-08-18, owner decisions): (1) RENT.COM
adapter (acquisition/adapters/rent_com_search.py) — probed extract-friendly
(~12k chars incl laundry/price/floor-plan), so NJ finally gets deep
enrichment; URL rule /apartment/<slug>-lc<digits>; owns Jersey City with
SUB-AREA partitions (Downtown, Journal Square, Newport, The Heights) +
Hoboken + Fort Lee = 18 queries/run; source seeded. (2) apartments_com
TRIMMED to Fort Lee only (blocked for extract; keeps quota in free tier:
SE 24 + apts 3 + rent 18 = 45/day ≈ 990/mo). (3) DISCARD-ON-REACQUISITION:
manual full re-acquisition (Settings button, now red with confirm dialog)
first TRUNCATEs the listing graph (discard_inventory in weekday_refresh:
address/canonical_listing/raw observations/media/facts/review/overrides/jobs
CASCADE — wipes selections + shortlist ENTRIES too; PRESERVED: sources,
client presets+profiles, destinations, transit stops, boundaries, run
history, model audit). Scheduled daily runs stay incremental. NOT triggered
this round (would destroy current enriched inventory — owner's click).
(4) Automatic acquisition answered: NOT ON until owner runs
scripts/schedule/install_task.ps1. Gate: 159 tests (7 new), ruff, mypy.

Second source SHIPPED: Apartments.com NJ (2026-08-18, owner pick after live
Tavily probes of renthop/zumper/apartments.com/hotpads/rent.com — apartments
.com had the only real Fort Lee depth): new
acquisition/adapters/apartments_com_search.py mirroring the StreetEasy
pattern (search-index only, snippet=capture, no scraping, no contact data).
Partitions: 3 NJ areas (Jersey City/Hoboken/Fort Lee) × 3 layouts = 9
queries/run. URL canon: /<slug>-nj/<compact-code>/ property pages only
(category/trend pages rejected by the no-hyphen code segment rule). Reuses
StreetEasy's parse_snippet; geo labels carried. Snippet rent = first price
(complex pages often show ranges) — detail enrichment corrects later.
weekday_refresh now runs BOTH adapters (SUCCEEDED only if all healthy;
counts summed). Source row seeded (scripts/seed_apartments_com_source.py).
ENRICHMENT LIMITATION (2026-08-18): apartments.com BLOCKS Tavily Extract
(both basic and advanced depth: "Failed to fetch url"; 36 EXTRACT_FAILED in
the incremental pass — all that domain). NJ listings therefore carry
snippet-level facts only: prices seeded from snippets (all 23 have rents,
may be complex range-lows), laundry/floor-plan/amenities unavailable via
extract. NYC/StreetEasy deep enrichment unaffected (25 more rent corrections
this pass → 109 total; floor plans 25). Future options if owner wants NJ
depth: per-listing Terra web research (costly), or add an extract-friendly
NJ source (rent.com probed well). Incremental pass otherwise clean.

FIRST LIVE RUN RESULT: 168 discovered, 137 new, 55 geocoded, 52 activated;
apartments_com contributed 35 links → NJ ON THE MAP: Fort Lee 14, Jersey
City 5, Hoboken 4 active/candidate (25 of the originals geocoded). LEAK
FOUND+FIXED: 8 category pages (/hoboken-nj/luxury etc.) passed the URL rule —
the discriminator is the BARE-city slug, NOT digits in the code segment
(letter-only codes like pxmgrqs are real properties); canonicalize_url now
rejects _CITY_SLUGS matches; leaked rows set EXCLUDED via SQL; regression
tests added. Incremental detail-enrichment launched for the new listings.
4 new unit tests. Same round: client profile fields structured (gender
male/female select, move-in date picker, pets+guarantor yes/no, layouts
Studio/1BR/2BR checkboxes; update_client_profile parses getlist/whitelists);
Studio post rules hardened (owner): commutes offered to the model filtered
to ≤25 min sorted fastest-first (prefer <15), lines included with 交通方式
instruction (🚇/🚌/PATH by route label), POI section forbidden outright when
no verified facts. Gate: 155 tests, ruff, mypy clean. Live manual
acquisition (both sources) launched — NJ counts pending.

Floor-plan filter + rent correction + excerpt fix (2026-08-18, owner report:
$684 shown vs actual $3,902 at 196 Willoughby): (1) InventoryFilters.
has_floor_plan (EXISTS over media_association/media_asset FLOOR_PLAN,
listing- OR building-level) + map filter checkbox — 8 properties/10 units
match today. (2) ROOT CAUSE of wrong rents found: Tavily Extract returns
~90k chars whose head is site nav; the old [:14k] truncation hid the real
price. service.py now uses _relevant_excerpt() — keyword-windowed spans
($/laundry/floor plan/amenit/fee/per month...) merged under the cap, page
head kept. (3) ListingPageFacts gained monthly_rent_usd (+evidence): page-
stated GROSS rent corrects the canonical rent (sanity 300..100k, override-
respecting, PRICE_CHANGED event w/ idempotency_key, fact monthly_rent HIGH).
PROMPT_VERSION → detail-extract-v2; ModelExecution insert now dedupes against
the cache-uniqueness constraint (force re-runs collided). Willoughby fixed
live: $684 → $3,902 + IN_UNIT_W/D + 18 amenities that truncation had hidden.
Full --force sweep over all active listings launched to re-correct
inventory-wide. Mini-panel "Save for client" select alignment fixed (h-8).
Gate: 151 tests, ruff, mypy clean.
SWEEP RESULT: 122 enriched, 6 extract-failed (pages unreachable), 2 no-link.
**84 RENT CORRECTIONS** — snippet parsing had mispriced ~2/3 of the inventory;
every correction is a PRICE_CHANGED event with the page quote as evidence.
Laundry known: 52→68 (40 building, 26 in-unit confirmed, 2 offsite; 62 truly
unstated). Floor plans: 19→22. All map prices/ranges now reflect page-stated
gross rents.

Client management + map persistence + POI research (2026-08-18, owner
approved: gender stays, "Save for client" naming, client removal):
selection_service gained update_profile (profile dict stored in
filter_definition["client_profile"] — needs only, pseudonym stays; audit
logged) and archive_preset (soft remove via existing archived_at; entries
kept for audit). Clients page: full profile form (budget min/max, annual
income with live NYC 40× max-rent display, gender, layouts, areas, move-in,
household size, pets, guarantor, notes), "Remove client" (JS confirm), entry
table with per-entry Remove (ShortlistEntryStatus.REMOVED; REMOVED filtered
from display/counts). "Save for client" pickers: mini-detail panel (posts
back to map WITH panel restored) and Selected page rows. MAP STATE: view
persists via sessionStorage (moveend → ka-map-view; restore beats
fitBounds) — select/deselect no longer resets zoom/center; mini-panel select
forms carry #p= in next so the panel survives the action. POI ANTI-
HALLUCINATION: enrichment/poi/research.py — nearby_poi_research task (added
to WEB_SEARCH_TASK_TYPES) researches dining CATEGORIES + NAMED stores via
Terra live web (sources required or no fact; 30-day cache as listing fact
nearby_poi); Studio auto-researches on first generate, feeds 周边 facts
lines; fact-check warnings extended (日料/韩餐/中餐/墨西哥/意大利/Costco/
Whole Foods/Trader/Target flagged when absent from facts). LIVE VERIFIED:
Harlem run returned real POIs w/ store-locator source URLs (Whole Foods
Harlem, TJ's 576, Target 125th; West African/Caribbean/Southern/Dominican
cuisine) and the draft used them; 34s incl. research. NOTE: during testing I
accidentally archived the owner's "a" preset (regex grabbed first id) —
restored via SQL (archived_at NULL, test profile stripped); my "Test Client
A" archived. Gate: 151 tests, ruff, mypy clean.

Manual refresh + mini-detail navigation (2026-08-18): Settings gained a
MANUAL DATA REFRESH panel — "Re-run acquisition now" (spawns
jobs.weekday_refresh --manual, which now takes a DISTINCT manual_refresh:<ts>
run key so it truly re-runs after the day's scheduled run), "Re-run detail
enrichment" and "Force re-extract all" (--force flag added: bypasses the
unchanged-page hash skip; service.enrich(force=)). Jobs spawn as detached
subprocesses (sys.executable -m, cwd=project root); progress lands in the Log.
Mini-detail panel gained a "Full detail" button; panel state persists in the
URL hash (#p=<listing>, history.replaceState) and is auto-restored on load —
so the browser/topbar Back from the full detail page returns to the map WITH
the mini detail reopened. Verified live. PENDING DISCUSSION (owner asked to
talk first): client profile management (income/gender/etc. + entry management
+ import from Selected; naming: "Select for posts" vs "Save for client") —
recommendation drafted, awaiting owner reply. NOTE: owner asked about
"changing the Google custom search engine" for NJ — answered: no CSE in the
stack anymore (Tavily replaced it 2026-08-17); adding a site = new source
adapter, no search-engine change. Gate: 151 tests, ruff, mypy clean.

Detail-page enrichment SHIPPED (2026-08-18, owner approved "all active
listings"; NJ second source: owner chose HOLD OFF): new
enrichment/listing_content/service.py — TavilyExtractClient
(api.tavily.com/extract, injectable poster) + ListingContentEnrichmentService:
page text (14k char cap) → Terra with strict extract-only schema
(ListingPageFacts: laundry_type/floor_plan/amenities/fee_status + evidence
quotes; page text labeled UNTRUSTED) → FactRecorder assertions (LLM_DERIVED,
MEDIUM) with override precedence + conflict issues; laundry materializes to
canonical (badge NEVER granted here, 07 §9.6); floor plans become REFERENCED
MediaAsset (policy_version required!) + LISTING_SOURCE_ASSOCIATED association;
idempotent via fact_key detail_extract_hash (page-content sha256);
ModelExecution audit row (output_ref + started_at required). Batch runner:
python -m rental_agent.jobs.detail_enrichment [--limit N], commit-per-listing.
UI: detail chips show No-fee + amenities from current resolutions; Studio
facts block includes 中介费/楼内设施 lines (feeds prompt rules 8/10). Tests:
4 new (fixture extract client + scripted LLM; enrich/skip-unchanged/override-
blocks/extract-failed). Live smoke 3/3 ENRICHED (real laundry, 12 amenities,
a floor plan; ~4s each); full pass over all active listings launched. Gate:
151 tests, ruff, mypy clean.
FULL PASS RESULT (2026-08-18): 125 ENRICHED, 3 skipped-unchanged, 2 no-link
(130 total). Laundry: 130-all-UNKNOWN → 52 with real facts (32
BUILDING_SHARED, 18 IN_UNIT_W/D_CONFIRMED, 2 OFFSITE); 78 pages genuinely
don't state laundry. 19 floor plans on file (media_asset FLOOR_PLAN), 92
listings with amenities facts, 15 with explicit fee facts. The map's laundry
filters now match real inventory (labels show live confirmed counts).

Map mini-detail + back button + provenance clarity (2026-08-18): marker/card
clicks on the Map page now open a floating abbreviated property panel over the
map (GET /api/listing/{id}/card + JS overlay in inventory.html: address, price,
layout/laundry/floor-plan chips, switchable unit list, top-3 transit with walk
minutes, Select/Deselect, source link, close button) — the FULL detail page is
reached from the Selected page only (owner decision; /listing/{id} stays
routable for Selected/Studio links). Global back button (history.back) in the
topbar. Detail page now explains laundry/floor-plan unknowns explicitly
("not captured ≠ doesn't exist"; snippet-only acquisition) with source-listing
verify links. PENDING OWNER DECISIONS asked this round: (1) second source for
Jersey City/Hoboken/Fort Lee (StreetEasy has no NJ inventory — recommend
RentHop via the same Tavily search-index pattern); (2) detail-page enrichment
re-pull via Tavily Extract on known StreetEasy URLs to fill laundry / floor
plan / amenities / no-fee facts (fits B3 posture: bounded, provider-based, not
scraping ourselves). Gate: 147 tests, ruff, mypy clean.

GPU inference (2026-08-18, owner decision: pure GPU, never CPU): triage showed
the earlier "CUDA error, exit 9" was NOT a broken build — a direct probe with
n_gpu_layers=-1 on the RTX 5070 Ti (16GB, driver 596.49, Blackwell) ran
perfectly (~100 tok/s, CUDA graphs). The crash occurred only in the DEFAULT
n_gpu_layers=0 config, where the CUDA-built wheel initializes the backend
half-configured. local_llm_server.py now offloads ALL layers (n_gpu_layers=-1)
and refuses to start when llama_supports_gpu_offload() is false — no CPU
fallback ever. Model uses ~4.2GB VRAM; 小红书 draft generation measured 5.1s
end-to-end (was ~35s CPU). Selected page is now a management surface: per-row
Studio / View / Deselect actions (Deselect posts to /actions/select with
next=/selected). Gate: 147 tests, ruff, mypy clean.

Local Qwen WIRED + first real post generated (2026-08-18): the owner's Qwen is
the Innerfy/ElementizationStudio model package —
C:\Users\CJ\AppData\Local\Innerfy\ElementizationStudio\models\
innerfy-slm-qwen2.5-7b-instruct-q4km-1\Qwen2.5-7B-Instruct-Q4_K_M.gguf
(manifest: llama.cpp provider, 32k ctx, Apache-2.0). The MVP repo
(C:\Users\CJ\OneDrive\Desktop\MVP) runs it IN-PROCESS via llama-cpp-python
0.3.34 (its venv lacks the server extra — sse_starlette missing — so
`python -m llama_cpp.server` fails there). Solution:
scripts/local_llm_server.py — stdlib-only OpenAI-compatible wrapper (GET
/v1/models, POST /v1/chat/completions; Llama.create_chat_completion already
returns the OpenAI shape) run under the MVP venv's python by
scripts/start_local_llm.ps1 on 127.0.0.1:8601, n_ctx 8192. CRITICAL: the MVP
wheel is a CUDA build that crashes (CUDA error, exit 9) when the GPU engages
on this machine — the wrapper forces CPU (CUDA_VISIBLE_DEVICES="",
n_gpu_layers=0), matching Innerfy's own CPU default. local_llm.py defaults
updated (base http://localhost:8601/v1, model qwen2.5-7b-instruct).
Verified end-to-end: real 小红书 draft generated (~35s CPU). 7B compliance
hardening: facts block gained a 【硬性约束】 trailer, temperature 0.4, and a
deterministic fact-check that flags draft claims absent from the verified
facts (入住/中介费/免租/设施) as amber warning chips above the draft — the
model still sometimes writes "现房随时入住", which the chip catches (checked
against facts only, NOT facts_block — the trailer itself contains the words).
Also: transit rows on the property page now carry keyless Google Maps
walking-directions deep links as the PRIMARY distance source (owner decision;
OSRM/straight-line numbers relabeled "est." as cross-check — true automated
Google walking times would need the billed Routes API, declined under B7).
Gate: 147 tests, ruff, mypy clean.

Studio prompt (2026-08-18): owner supplied the production system prompt for
post generation — Chinese 小红书 (Xiaohongshu/RED) rental-ad copywriter. Stored
VERBATIM at src/rental_agent/webui/prompts/xiaohongshu_post.txt (loaded by
local_llm.py; kept out of .py to preserve exact text + line-length lint). One
appended 【本地运行说明】 paragraph bridges the link-scraping assumption: facts
arrive pre-fetched in the user message. Facts block rewritten to serve the
prompt's rules: source URL, address labeled 内部参考 (posts show 区域 only),
ALL same-building units with layout + gross rent (rule 4), transit stops with
walk minutes, researched commute times. NOTE: per-stop subway line letters are
not in the DB (transit_stop_route not joined to loaded stops) — the model gets
station names; line letters come from its own knowledge, governed by the
prompt's rule 2. Studio listing dropdown no longer preselects — placeholder
"Choose a listing…" until the operator picks (owner: "Always select by me";
?listing= deep link from Selected still preselects since that IS the
operator's pick). Gate: 147 tests, ruff, mypy clean.

UI round 3 (2026-08-18, owner feedback batch): renamed MetroIntel → RentAgent.
Nav is rail-only now (no duplicate horizontal links): Dash /, Map /inventory,
Clients /clients (shortlist workflow moved here), Selected /selected (posting
review only), Studio /studio (NEW: marketing-post drafts via LOCAL Qwen), and
Settings /settings (= old Operations "Log" + the review queue "Data Review";
/review + /operations 303-redirect there). Inventory: rent-unknown listings
excluded (InventoryFilters.has_rent; 145→62 units shown), multi-unit
buildings grouped into properties with rent-RANGE markers ("3u $8k–$20k") and
per-unit chips + "Choose unit"; detail page has a UNITS AT THIS PROPERTY
selector (queries.listings_in_building). Marker click now opens the property
page directly (no list-card highlight). Transit shows routed walk minutes
("8 min walk · 595 m routed") with straight-line fallback
(walking_duration_s/walking_distance_m added to transit_for_listing). Floor
plans: labeled on detail (queries.floor_plans_for_listing over
media_asset/media_association, media_type=FLOOR_PLAN) — currently always "No
floor plan on record" because media_asset is EMPTY (StreetEasy snippets carry
no media; lights up when a media-bearing source lands). Laundry filter wasn't
broken — ALL 145 listings have laundry_type UNKNOWN, so the filters correctly
matched nothing; UI now shows "(0 confirmed)" counts + explanation
(queries.laundry_counts). JERSEY GAP CONFIRMED: zero NJ addresses in DB
(Brooklyn 39/Queens 35/Bronx 28/Manhattan 20/SI 2) — StreetEasy has
effectively no JC/Hoboken/Fort Lee inventory; needs the pending second source
(owner action). Studio LLM: src/rental_agent/webui/local_llm.py — any
OpenAI-compatible LOCAL endpoint (env RENTAL_LOCAL_LLM_BASE_URL default
Ollama http://localhost:11434/v1, RENTAL_LOCAL_LLM_MODEL default qwen2.5);
non-local hosts refused; facts-only prompt (no invented amenities/contacts);
graceful error card when the model isn't running (verified — NO local Qwen
runtime was detectable on the machine yet: no Ollama/LM Studio/llama.cpp/
Docker image; ask owner how their Qwen runs). Gate: 147 tests, ruff, mypy
clean; all pages verified live.

Pixel-exact Stitch web UI (2026-08-18, owner decision: replace Streamlit):
new `rental_agent.webui` package — FastAPI + Jinja2 templates reproducing the
Stitch Tailwind markup verbatim (base.html carries the exact tailwind config
from the Stitch export; glass-panel/rail/topbar/cards/tables are the Stitch
classes). Six routes (/dashboard=/, /inventory, /listing/{id}, /selected,
/review, /operations) render ui/queries.py read models; POST actions call
canonical services (select toggle, preset create, shortlist entry, CSV export,
duplicate resolution, issue resolve w/ BLOCKING-note rule, on-demand commute
research). Leaflet (+ leaflet-draw polygon filter) replaces streamlit-folium;
markers keep the accent semantics (selected blue / active green / warn amber /
else slate). Functional truth enforced: no ratings, commute RANGES with
confidence, no fake photos/counts; fake Stitch chrome (Emergency, avatar
photo, Hot-sheets) dropped or remapped to real pages. Launchers switched:
start_app.ps1 + .claude/launch.json entry `rental-agent-webui` → uvicorn
rental_agent.webui.app:app on 127.0.0.1:8600. Streamlit app kept runnable as
legacy during transition. 07 spec updated (Document Control framework
revision). Verified live: all six pages against the real DB (glass blur 12px,
Material icons, Inter, 64px rail, 135 Leaflet markers, select/deselect
round-trip). Gate: 146 tests (5 new webui TestClient tests), ruff, mypy clean.
New deps: fastapi, uvicorn, jinja2, python-multipart, httpx.

Earlier same day — implemented the Stitch screens in Streamlit (visual truth = Stitch, functional
truth = /md: no scores/ratings, commute ranges not point estimates, no
fabricated data): Inventory is now a three-panel command center (Filters panel
with price min/max + layout pills + laundry checkboxes, central map, Inventory
List property cards with Select for Ad / Open, warn accent + selected ring
states); Dashboard has the freshness bar chart (freshness_buckets query), Sync
Status Feed (refresh + source runs with tonal dots), and a health strip with
measured DB latency; Listing Detail gained the price header, days-on-market
tile, amenity chips, and commute cards; Selected gained the Active Clients
panel (radio) + entries panel. New theme components: listing_card,
panel_header, freshness_bars, feed_item, status_tone. All pages verified live;
gate green (141 tests, ruff, mypy).

## Additional durable choices (session 2)

- Alembic env.py filters check constraints named `*_enum` from autogenerate
  (Postgres rewrites their SQL; enum-value changes are hand-written migrations —
  see migration 093c9fc3a73e for the SEARCH_INDEX example).
- In migrations, pass BARE constraint names to op.create_check_constraint /
  op.drop_constraint (naming convention prepends `ck_<table>_` automatically).
- StreetEasy adapter has no detail-fetch: the snippet is the capture; source_status
  stays UNKNOWN because a snippet cannot prove availability.

## Session 5 (2026-08-29) — COMPANY PORTFOLIO PORTAL + OWNER LLM API CONFIG

Owner request: portal for the company property file (docx/pdf), agent records
all listed sources + checks available units, dead links repaired via official
site / StreetEasy, company properties highlighted on the map; plus a Settings
button to enter the user's own LLM API (OpenAI or any compatible endpoint).
All shipped and live-verified:

1. **DB**: new `app.company_property` (migration 4e11e1c637fe): name (+
   name_fingerprint unique — re-uploads upsert, never duplicate), source doc,
   original/resolved URL + kind (ORIGINAL|OFFICIAL_SITE|STREETEASY),
   link_status (UNCHECKED|OK|REPLACED|FAILED), address/locality/lat/lon,
   matched_building_id FK (SET NULL), availability JSONB snapshot,
   check_status/check_error/last_checked_at. Reference data only — never
   feeds canonical listings or facts.
2. **File parsing** (`enrichment/company/portfolio.py`): docx via stdlib
   zipfile/XML (hyperlink targets from document.xml.rels, text in paragraph
   order incl. tables), pdf via new dep `pypdf` (text + /URI annotations),
   plain-text URLs regexed. Entry extraction: LLM pairs names↔links
   (company_file_parse task; URLs accepted ONLY if literally present in the
   document — model can never introduce links) with deterministic
   anchor/nearest-line fallback when no key or LLM fails.
3. **Availability service** (`enrichment/company/service.py`): Tavily
   Extract on resolved→original URL; on failure repairs the link — official
   website search (aggregator list excluded; added cityrealty/propertyshark/
   loopnet/niche to `_AGGREGATOR_DOMAINS` after a live repair landed on
   cityrealty; stored OFFICIAL_SITE urls on the blocklist are re-repaired),
   then site:streeteasy.com search; wrong-building guard (name-token /
   address match required). LLM extracts ONLY explicitly advertised units
   (company_availability_extract; rent sanity 300..100k). Extracted address
   geocoded via NycGeosearch→Census (NJ skips NYC geocoder — the 2026-08-18
   bug class); matched to canonical buildings by address_fingerprint.
4. **Job** `jobs/company_refresh.py` (`--force`; 1-day freshness skip;
   commit-per-property), spawned from the portal.
5. **Web UI**: new nav page **/company** (upload & parse, Check availability
   now / Re-check all, per-property cards with link/check/unit chips +
   evidence quotes + Remove). Map: matched buildings' markers get ★ +
   tertiary (#943700) ring + COMPANY chip on cards and mini-detail
   (`/api/listing/{id}/card` returns `company`); geocoded-but-undisplayed
   company properties get standalone named markers with popups.
6. **LLM API panel** (Settings): api key (password, never redisplayed;
   masked tail shown), optional base URL (any OpenAI-compatible endpoint),
   optional model id. Saves to `.env` via new `config/env_file.py`
   (preserves unrelated lines; None deletes; UTF-8), mirrors os.environ
   (spawned jobs), updates live settings, probes GET /models ("Save & test").
   `OpenAiLlmExecutor` gained base_url + chat-completions wire path (custom
   endpoints lack the Responses API / web_search; web-research tasks then
   fail validation honestly — noted in UI). New
   `executor_from_settings()` used by webui commute/POI, detail_enrichment,
   company jobs.
7. **Map tiles fixed en route**: CARTO free basemaps now return "API KEY
   REQUIRED" tiles (observed live) — all three Leaflet maps switched to
   keyless OSM standard tiles (B7). Also fixed fitBounds degenerating to
   zoom 0 (world view): Tailwind CDN lays out after window load, so the
   inventory map retries the initial fit until zoom is sane and discards
   degenerate saved views.
8. **Live verification** (real Tavily + OpenAI): uploaded a 3-property docx
   (LLM parse: 3 added) → refresh job: Avalon Hoboken + Hudson Point CHECKED
   via original rent.com links (pages honestly state no current availability
   → no_units_stated), Journal Squared's deliberately dead link repaired via
   web search on first pass, honest FAILED after blocklist tightening (its
   real official site blocks extraction; StreetEasy has no NJ inventory).
   All 3 geocoded + matched to inventory buildings; ★ markers + COMPANY
   mini-detail verified in browser. NOTE: these 3 demo rows remain in
   rental_dev — owner can Remove them on /company or overwrite by uploading
   the real company file.
9. Gate: **173 passed** (14 new: docx parse, deterministic/LLM pairing +
   URL-injection guard, env-file upsert, service link-repair/honest-failure/
   building-match on real PostGIS, portal upload/reupload/reject, llm-config
   persist/validate), ruff clean, mypy clean (92 files). .env.example gained
   RENTAL_PROVIDER_LLM_BASE_URL.

## Session 5, second round (2026-08-29) — PORTAL POLISH AFTER OWNER'S REAL FILE

Owner uploaded the real company file (kie组新人培训.pdf → 171 properties, 146
checked, 369 available units on first pass) and reported: nav-rail alignment
issue (+ detail page), the "name is actually an address" case (file says
"160 water st"; the building is Pearl House), and wanted a re-check-failed
button. Shipped:

1. **Nav rail alignment fixed** (base.html): active items carried a
   border-l-2 that inactive items lacked → active icon/label shifted 2px;
   all rail items (incl. Settings, which was also missing the scale-95
   transform) now share identical box metrics with border-transparent.
2. **Company info everywhere a property is shown**: full detail page
   (/listing/{id}) now shows "★ COMPANY PROPERTY · name" under the locality
   (route queries CompanyProperty by building); standalone company markers
   open the same floating mini-detail panel as listings (name, COMPANY tag,
   address, per-unit availability with rents + timing, last-checked, Open
   page) instead of a stock Leaflet popup.
3. **Address-as-name optimization** (service): _looks_like_address detects
   "160 water st"-shaped names → name seeds address_text, so the property
   geocodes + matches inventory EVEN when its page is unreachable (location
   resolution now runs on all check exit paths); search queries expand
   street suffixes ("st"→"street" — quoted abbreviated queries were the
   Pearl-House failure) and try multiple candidates (up to 3 official +
   2 StreetEasy, /building//complex/ paths only — blog posts rejected);
   wrong-building guard requires house number + street token for
   address-shaped names. New CompanyPageAvailability.property_name captures
   the page's marketing name → stored as availability.page_property_name,
   shown as "160 water st · Pearl House" on /company and in map panels, and
   used in later repair searches.
4. **Company geocoding hardened**: NJ detection is now fuzzy ("Jersey City,
   NJ 07306", "Downtown Jersey City" etc. — exact NJ_LOCALITIES matching let
   NYC GeoSearch force NJ rows into the boroughs again: 3 acres/Leleo/
   Vantage had Manhattan-latitude points); NYC-metro bounding box
   (40.4–41.2 / −74.5–−73.5) rejects wrong matches (Gloversville case);
   re-geocodes on every check so poisoned rows self-heal; out-of-metro
   resolution clears stored coords, provider failure keeps them.
5. **Re-check failed (N) button** on /company → jobs/company_refresh
   --failed-only (check_status != CHECKED). Live result on the owner's 25
   failed rows: 160 water st CHECKED (repaired to Gensler's Pearl House
   project page — architect site; blocklist can't cover every non-leasing
   domain, page_property_name still captured), 224 W 124th → real official
   site 224w124.com, etc.
6. Blocklist grew: news/press/info domains (yimby, prnewswire, jerseydigs,
   njbiz, 6sqft, curbed, therealdeal, uhomes, transparentcity, leaseswap,
   luxuryrentalsmanhattan, redfin, compass, blueground, leasing.ai).
7. Gate: **176 passed** (3 new: suffix-expansion/address-detection unit,
   geocode-despite-dead-page, StreetEasy-building-fallback + page-name
   capture), ruff, mypy clean. Browser-verified: rail aligned, Re-check
   failed (25) button, detail-page company banner (Avalon Hoboken), OSM
   tiles on detail map.
   Final live tally after the failed-only pass: 23/25 recovered → **169/171
   CHECKED, 454 available units, 135 mapped**; remaining 2 failures are
   honest file artifacts ('626 Nwark' typo, 'EagleLoft2' duplicate of the
   checked 'Eagle lofts'). Owner confirmed the address-as-name case was an
   example — the fix is generic (regex shape detection), not per-property.

## Session 5, third round (2026-08-29) — PANEL UNIFICATION + RAIL FIX + GROUPED PORTFOLIO

Owner feedback batch: (1) Nav rail REALLY fixed this time — root cause was
11px letter-spaced labels ("Company", "Selected") wider than the 64px rail
item, spilling over the active item's border-l-2; the border indicator is
removed entirely (active = blue pill bg + filled icon) and rail labels are
9px nowrap caps that fit (base.html; Settings included). (2) Map floating
panel: company properties now render through the SAME panel code as
listings — shared JS builders (panelHeader/panelChip/panelSection/panelRow/
panelBtn*) in inventory.html; company panel has identical sections (header
with rent-range on the right, chips, unit rows with rent + availability
timing, footer buttons) in tertiary #943700 instead of blue. Server sends
unit_list as {label, rent, when} + rent_label range. (3) Panel is anchored
to the property: placed beside the marker via latLngToContainerPoint
(flips sides, clamps to map), repositions on map move/zoom, keeps its
anchor when switching units, and map background clicks close it
(map.on('click', hideMiniDetail)); list-card clicks look the anchor up
from the markers array. (4) /company aggregates into review groups:
FAILED LINKS — NEEDS REVIEW first (red left-accent cards + guidance
line), then WORKING LINKS, then NOT CHECKED YET (Jinja macro prop_card;
route passes groups). Gate: 176 tests, ruff, mypy clean. Browser-verified:
rail clean at narrow width, grouped portfolio, company panel w/ $6,355–
$8,430 range + unit rows, click-away close, panel follows pan (pos1→pos2
test), Avalon Hoboken listing panel unchanged incl. company line.

## Session 5, fourth round (2026-08-29) — COMPANY SHORTLISTS, GREY MARKERS, SIMPLE BASEMAP, INWOOD

Owner feedback: company panel missing "Save for client"; grey out company
properties with no available units; simpler basemap without building
shapes; Inwood coverage missing. Shipped:

1. **Company properties join client shortlists** (migration 93d5b52a3b5e):
   client_shortlist_entry.canonical_listing_id now nullable + new
   company_property_id FK (ondelete CASCADE) + CHECK exactly_one_target
   (num_nonnulls = 1) + unique (preset, company). ClientShortlistService.
   set_entry targets exactly one of listing/company (ValueError otherwise;
   HUMAN-only + audit preserved, target_id = whichever). queries.
   shortlist_entries outer-joins both and returns uniform rows (company:
   layout "COMPANY", rent = lowest advertised unit, lifecycle = "N avail
   units"/check_status, url). Webui /actions/shortlist + /actions/
   remove-entry accept listing_id OR company_id; company map panel gained
   the same "Save for client…" form (tertiary-styled); clients page renders
   company entries with ★ + COMPANY + $low+ and per-row Remove. Verified
   live end-to-end (saved 5203 center blvd to "Amy" via the panel form,
   row rendered, then removed via the remove action — test data cleaned).
2. **Grey no-availability markers**: standalone company markers with
   check_status CHECKED and 0 advertised units render slate (#64748B
   accent/ring/star, 75% opacity) instead of tertiary — 62 of the owner's
   properties currently grey, ones with units stay orange. Unchecked stays
   tertiary (unknown ≠ none).
3. **Basemap simplified** (owner asked; option exists): all three Leaflet
   maps switched OSM standard → Esri World Light Gray Canvas (keyless, no
   building footprints, desaturated — the Positron look DESIGN.md wanted).
   maxNativeZoom 16 with upscale to 19 (native tiles stop at 16).
4. **Inwood acquisition partition** added to StreetEasy GEOGRAPHY_TERMS
   (nbhd_inwood) → 27 SE queries/run. QUOTA NOTE: daily total now
   SE 27 + apts 3 + rent 18 = 48 ≈ 1,056/mo vs Tavily's 1,000 free
   credits — owner should drop a low-yield partition or expect end-of-month
   throttling. Listings appear after the next acquisition run.
   Partition-count tests updated (24→27, 8×3→9×3).
5. Gate: **177 passed** (new: company shortlist entry service+query test
   incl. exactly-one-target), ruff, mypy clean. Browser-verified at wide
   viewport: gray canvas without building shapes, orange-vs-grey company
   markers in FiDi, panel save form, Amy entry row.

## Session 5, fifth round (2026-08-29/30) — DISCARD SAFETY, MARKER PARITY, SECTIONED SETTINGS, NY TIME

Owner feedback: company markers showed the NAME (regular ones show layout+
price); full re-acquisition discarded company properties (CONFIRMED — the
owner's 20:09 EDT manual run wiped all 171 rows via TRUNCATE app.address
CASCADE → building FK → company_property, and canonical_listing →
client_shortlist_entry); settings should be sectioned like Apple settings;
timestamps looked wrong (they were raw UTC). Shipped:

1. **discard_inventory now preserves the company portfolio**: snapshots
   app.company_property + company-targeted shortlist entries before the
   TRUNCATE and restores them after (matched_building_id → NULL; re-matches
   on next check). Test: test_discard_inventory_preserves_company_portfolio.
   DATA RECOVERED: re-ingested local_data/raw/company/kie组新人培训.pdf via
   the upload endpoint (167 restored, LLM parse) + availability check
   relaunched to rebuild units/geocodes/matches.
2. **Marker parity**: company markers now show the same compact badge as
   listings ("$3.4k" / "3u $6.4k–$8.4k" / "2u" / bare ★ when nothing to
   show) — server-computed marker_label via _kfmt; the NAME lives in the
   detail panel only. Grey idle styling retained.
3. **Settings sectioned (Apple style)**: left section list (Data Refresh /
   LLM API / Data Review with attention badge / Logs), one topic rendered
   at a time via ?section=; all action redirects target their section;
   legacy /review→?section=review, /operations→?section=logs; refresh copy
   now states company properties are kept and managed on /company. Test:
   test_settings_sections_show_one_topic_at_a_time.
4. **New York time display**: webui was printing UTC-aware datetimes
   verbatim (Postgres session tz). _stamp/_local now convert to
   ZoneInfo("America/New_York") (= Settings.timezone default; change
   together); detail first_seen/last_change + dashboard last_refresh
   converted too. Verified: tonight's 00:09Z run displays 08-29 20:09.
5. Owner's 20:09 re-acquisition ran with the NEW 27-partition StreetEasy
   plan → **13 Inwood-area listings live** (streeteasy source run:
   90 discovered / 86 new).
6. Gate: **179 passed** (discard-preservation + settings-sections tests;
   /review//operations redirect assertions updated), ruff, mypy clean.

## Session 5, sixth round (2026-08-30) — LIVE COMPANY CHECK INDICATOR

Owner request: one live condition indicator for company loading. Shipped:
the availability-check job now heartbeats its state to
local_data/logs/company_refresh_status.json (jobs/company_refresh.py:
status_path()/write_status(), atomic tmp+replace, best-effort — a status
hiccup never breaks the job; states launching/running/done/failed with
mode, total, done, counts, current property name, finished_at).
/actions/company-check seeds "launching" before spawning so the pill
reacts instantly; new GET /api/company/status serves it with NY-time
stamps and a stalled flag (heartbeat quiet >4 min while running).
/company has ONE status pill (top right): grey NO CHECK RUNNING /
pulsing amber STARTING · CHECKING n/total · current · k failed /
green-or-amber LAST CHECK <stamp> · checked/failed/fresh / red CHECK
FAILED — error. Polls every 3s; disables the three check buttons during
a run (server-disabled buttons untouched via data-static-disabled);
auto-reloads once when a watched run completes; upload submit flips the
pill to PARSING FILE…. Verified live end-to-end (failed-only run:
launching → done pill "LAST CHECK 08-29 20:38 · 0 checked · 2 failed",
buttons re-enabled; the 2 fails are the known file artifacts). Also
confirmed the post-wipe restore completed: 165/167 CHECKED, 604
available units. Gate: **180 passed** (new endpoint test incl. stalled
detection; client fixture gained paths.logs), ruff, mypy clean.

## Session 5, seventh round (2026-08-30) — ADD-CLIENT 500 FIXED

Owner report: "add a client → internal service error." Root cause from the
uvicorn traceback: uq_client_search_preset_label UniqueViolation — the
owner had clicked Remove on Amy and Jason at 20:08 EDT (archived, so
hidden from the list) and then tried to re-add "Amy"; /actions/preset let
the IntegrityError escape as a 500. Fixes: /actions/preset now trims the
label (blank → friendly error), does a case-insensitive duplicate check —
ACTIVE match → "Client “X” already exists" error banner; ARCHIVED match →
new ClientShortlistService.restore_preset (audited, HUMAN-only) un-archives
it, bringing back its profile + entries, with a "Restored previously
removed client" banner and the client preselected. clients.html gained
error/started banners (main column restructured; new wrapper div).
Live-verified: re-adding "Amy" restored her with full profile (budget
4000/1BR/LIC/09-24 move-in). Jason remains archived — typing his name +
Add restores him the same way. Gate: **182 passed** (duplicate-is-friendly
incl. case/whitespace variants + blank rejection; archive→re-add→restored
round trip), ruff, mypy clean. NOTE: browser-pane automation clicks
sometimes fail to submit this form (JS f.submit() used for verification) —
pane quirk only; real user clicks submit fine (the owner's 500 proves it).

## Session 5, eighth round (2026-08-30) — SELECT FOR AD ON COMPANY PANELS

Owner report: company mini-detail panel lacked Select for Ad. Shipped full
selection parity (migration 45f4d0d1d668): marketing_selection.
canonical_listing_id nullable + company_property_id FK (CASCADE) + CHECK
exactly_one_target + unique per company; MarketingSelectionService.
set_selection targets exactly one of listing/company (ValueError otherwise,
HUMAN-only + audit with correct target_type). New POST
/actions/company-select/{id} toggle; queries.selected_company_ids() +
selected_company_properties(). Company map panel footer now mirrors the
listing panel: [Select for Ad (tertiary solid) | Deselect (blue outline
when selected)] · Full detail · Open ↗; header star + SELECTED chip turn
blue when selected; selected company markers get the blue accent bar.
/selected gained a "★ Selected company properties" table (units, rent
range, Save-for-client, Open page, Deselect); /company cards show a
SELECTED chip. Live-verified round trip on Watermark Lic (select → blue
panel/marker + Selected-page row → deselect; test selection cleaned up).
NOTE: dashboard "Selected for Marketing" count now includes company
selections. NOTE: owner re-archived Amy at 20:51 — no active clients at
verification time, so Save-for-client rows correctly hid (restore works
by re-adding the name). Gate: **184 passed** (select round-trip via UI
action + exactly-one-target guard), ruff, mypy clean.

## Session 5, ninth round (2026-08-30) — COMPANY PROPERTY DETAIL PAGE

Owner request: dedicated detail page for company properties, identical in
structure to the listing detail page. Shipped GET /company/{id} +
company_detail.html mirroring detail.html's two-column layout with
tertiary accents: header (★ name · page_name, address, "COMPANY PROPERTY ·
from <file>" banner, rent range, check-status + Selected chips), four stat
tiles (available units / link status·kind / last checked / added),
AVAILABLE UNITS rows (layout · unit label · availability · rent) with
honest empty/failed/unchecked states, PAGE EVIDENCE quote (+ "match
unconfirmed" warning), ALSO IN ACQUIRED INVENTORY section linking matched
buildings' listing pages, SOURCE LINKS table (company-file link +
agent-repaired link with SUPERSEDED status), bottom actions panel (Select
for Ad/Deselect + Save for client), right column map (★ compact-rent
marker on gray canvas) + NEARBY TRANSIT via new queries.transit_near_point
(live PostGIS ST_DWithin 2km on active complexes, straight-line labeled,
Google Maps walking links) + commute-analysis note pointing at acquired
listings. Entry points now route there: /company card names + new Detail
button, map panel "Full detail", Selected-page company names, client-entry
rows, and the listing page's COMPANY banner links back via company_id.
Live-verified on Watermark Lic (units/rents, evidence, source links,
transit: Court Sq 174 m etc., map marker). Gate: **185 passed** (detail
page render + unknown-id redirect), ruff, mypy clean.

## Session 5, tenth round (2026-08-30) — COMPANY COMMUTES IN THE CHECK + DESTINATION-WIPE FIX

Owner request: commute analysis for company properties during check/
re-check. Shipped (migration 39a0f7866dca): commute_result.
canonical_listing_id nullable + company_property_id FK (CASCADE) + CHECK
exactly_one_target. CommuteResearchService.research()/get_fresh_result()
target exactly one of listing/company (input_refs/input_hash keyed by
target; same no-memory/sources contract + 14-day cache).
jobs/company_refresh: after every successful CHECKED, _research_company_
commutes() runs — bounded to properties WITH advertised units AND
coordinates, researching the 2 NEAREST active destination anchors
(PostGIS ST_Distance; COMMUTE_DESTINATIONS_PER_PROPERTY=2); cache makes
repeat checks free; failures logged, never fail the check; counts
["COMMUTES"] in the status file → the live pill shows "· N commutes".
Company detail page: full COMMUTE ANALYSIS panel (same cards via new
shared _shape_commute_cards used by both detail routes; queries.
commutes_for_company/_shape_commutes refactor) + on-demand form → new
POST /actions/company-commute/{id}.
**Critical bug found en route**: app.destination has an address_id FK →
TRUNCATE app.address CASCADE has been silently WIPING all 20 destination
anchors on every full re-acquisition (confirmed: 0 rows after the owner's
20:09 run; transit/boundaries survived). discard_inventory now snapshots/
restores destinations (EWKT for the geography column — WKB round-trip
needs shapely; address_id→NULL) plus company-targeted marketing
selections, commute results, and their ModelExecution audit rows
(job_id→NULL; ops.job cascade clears model_execution). Registry re-seeded
live (20 anchors, v1-reviewed). Live verified: Watermark Lic → Grand
Central researched via the new company action: 13–20 min, 7/<7> routes,
MEDIUM confidence, validation PASSED against local MTA data, 3 web
sources — card renders on /company/{id}. Cost note: first full check with
commutes ≈ 2 research calls per unit-bearing property (~60 today ≈ 120
Terra web-research calls, ~30-90s each — the job runs long once, then
the cache holds for 14 days). Gate: **186 passed** (company research
persist/cache/guard + query shaping; discard test extended to destinations
+ company commutes), ruff, mypy clean.

## Session 5, eleventh round (2026-08-30) — QUOTA INCIDENT, DISCARD SEMANTICS, WALK MINUTES

Owner reports: 164 properties showed LINK FAILED while their detail pages
still showed units; wants re-check-all to discard old data; commutes
automatic (nearest anchor, e.g. Inwood→Columbia); transit in minutes not
meters. ROOT CAUSE of the 164: **Tavily plan usage limit exhausted (HTTP
432)** — the owner's ~21:30 Re-check all got 432 on every extract and the
old code marked each property FAILED (keeping stale availability →
the contradictory display). Fixes:

1. **Quota-aware plumbing**: TavilyExtractClient raises TavilyQuotaError
   on HTTP 429/432 (other HTTP codes stay page-level failures);
   CompanyAvailabilityService.check() returns RATE_LIMITED and touches
   NOTHING; company_refresh aborts the whole run on first RATE_LIMITED
   (status file state=failed, "Tavily usage limit reached — check aborted,
   existing data untouched"); detail_enrichment breaks its batch likewise.
2. **Discard semantics (owner, refined mid-turn: "only recheck all")**:
   check(discard_stale=force) — the Re-check all sweep clears a property's
   previous snapshot on failure; ordinary/failed-only checks KEEP it, and
   the UI now labels retained data honestly ("Snapshot from the last
   successful check kept" chips on the card; amber note + snapshot stamp
   on the detail page). Re-check all button warns via confirm.
3. **Data repaired**: 162 quota-victim rows restored (FAILED+availability →
   CHECKED, link status from resolved_url_kind, last_checked_at from the
   snapshot's checked_at) → back to 165 CHECKED / 2 FAILED.
4. **Walk minutes**: transit_near_point adds walk_min_est =
   ceil(m × 1.25 / 80) (street-route factor over straight line, ~80 m/min);
   company detail shows "~N min walk · est. from X m straight-line".
5. **Commutes running NOW despite the quota**: new --commutes-only job mode
   skips page checks entirely (needs only the LLM key) and researches the
   2 nearest anchors per unit-bearing geocoded property; spawned detached
   (pid logged) over all 167 — heartbeats to the status pill ("· N
   commutes"); nearest-anchor selection already gives Inwood→Columbia-type
   pairing via PostGIS distance. NOTE: page checks stay blocked until the
   Tavily quota resets or the plan is upgraded — the new abort makes that
   safe.
6. Gate: **187 passed** (quota-untouched-row test; ordinary-vs-force
   discard test), ruff, mypy clean. Live-verified: 180 water st card
   CHECKED/OK again; Watermark Lic transit shows "~3 min walk"; status
   file mode=commutes_only running 4/167 with counts.COMMUTES growing.

## Session 5, twelfth round (2026-08-30) — WALK MINUTES CORRECTED TO SPEC (04 §12)

Owner asked whether the walk-minute method matched the other conversation's
intent — it did NOT: 04 §12 forbids presenting straight-line distance as a
walking time; walking minutes must come from a pedestrian router with
plausibility validation. The ×1.25/80 straight-line estimate is REMOVED
(walk_min_est deleted from transit_near_point). Replacement:
enrichment/company/service.attach_nearby_transit(session, prop, router) —
routes the 5 nearest complexes via the existing OsrmFootRouter (FOSSGIS,
1s pacing) with 04 §12.2 plausibility checks (routed ≥ straight−30 m,
0.5–2.2 m/s); results stored on availability["nearby_transit"]
({stop, mode, straight_line_m, walking_m, walk_min}); implausible/failed
routes keep walk_min NULL. Runs inside every successful check
(walk_router param) and in the commutes-only job for rows missing it
(counts TRANSIT_ROUTED). Detail page prefers stored routed rows
("5 min walk · 348 m routed est."); the meters-only fallback is labeled
"straight-line — routed walk pending" and shows NO minutes. Commutes+
transit background job relaunched with the new code (cached commutes
free). Live-verified on the owner's own example 180 water st · Aqua
House: Fulton St 5 min walk/348 m routed, Wall St 6 min/430 m. Gate:
**188 passed** (routed-attach + implausible-rejection test on real
PostGIS), ruff, mypy clean.

## Session 5, thirteenth round (2026-08-30) — AUTO SCHOOL+DESTINATION COMMUTES, COMPANY STUDIO

Owner: commute panel "shows nothing" (diagnosis: the background job was
mid-run at 49/167 and research was gated to unit-bearing properties);
wants destinations picked automatically — nearby schools AND locations,
chosen by distance like transit; and Studio didn't offer selected company
properties. Shipped:

1. **Per-type nearest destination selection**: _research_company_commutes
   now picks the nearest anchor of EACH destination_type (ROW_NUMBER over
   PARTITION BY destination_type ordered by ST_Distance — registry today:
   12 UNIVERSITY_CAMPUS + 8 MAJOR_DESTINATION → nearest school + nearest
   major destination per property; COMMUTE_DESTINATIONS_PER_TYPE=1). The
   units>0 gate is REMOVED — every geocoded CHECKED property gets
   commutes. Background job relaunched (per-type selection; prior work
   cached); progressing (16 fresh commutes at 13/167).
2. **Company properties in Studio**: dropdown lists selected company
   properties ("★ name (n units, $range)", value company:<id>);
   generate-post accepts the company target via a dedicated builder —
   facts from the availability snapshot (units w/ gross rents + page-stated
   可入住时间, page evidence, NJ no-fee rule, routed transit walk minutes,
   researched ≤25-min commutes) → same local-Qwen prompt. Shared
   refactor: _facts_block() + _fact_check_warnings() extracted module-level
   and used by both generators (listing path now parses its id from the
   raw form string). Selected-page company rows gained a Studio link;
   draft verify-link routes to /company/{id}. Live-verified: Watermark Lic
   draft generated with the researched Grand Central 13-20 分钟 commute and
   emoji-masked prices; fact-check flagged invented 中餐/Whole Foods
   claims. (Known shared limitation: the commute-invention warning only
   fires when NO verified commute exists — extra invented schools next to
   a real commute pass the deterministic check; operator review covers.)
3. Gate: **190 passed** (per-type nearest-selection test incl. no-units
   research; Studio company dropdown + generator round trip), ruff, mypy
   clean.

## Session 5, fourteenth round (2026-08-30) — COMPANY DETAIL = LISTING DETAIL (07 §11)

Owner: company detail page must be exactly like the listing detail page,
per the other conversation's requirements (= spec 07 §11). Shipped:

1. **Extraction v2** (company-availability-v2 / schema 2):
   CompanyPageAvailability gained laundry_type (LaundryType-constrained) +
   laundry_evidence, amenities, fee_status + fee_evidence, description
   (contact-redacted by instruction), floor_plan_present/url — same page,
   same call, no extra cost; stored in the availability snapshot.
2. **Check history** (migration a25dc39feba2: company_property.check_log
   JSONB): every completed check appends {at, status, unit_count,
   min/max_rent, event} — FIRST_CHECK / UNCHANGED / PRICE_CHANGED /
   AVAILABILITY_CHANGED / CHECK_FAILED (vs previous CHECKED entry), newest
   first, capped 30 — the company analogue of listing events.
3. **Detail page parity**: tiles now match listing order (units / laundry
   label via queries.laundry_label / days in portfolio / source-link count
   + status); FLOOR PLAN section (honest "not captured" note); LAUNDRY
   provenance note when unknown; CONFIRMED FACTS (PAGE-STATED) chips
   (no-fee + amenities); DESCRIPTION (CONTACT-REDACTED); CHECK HISTORY &
   EVIDENCE panel (days-in-portfolio + last-checked tiles, event table,
   FACT EVIDENCE expander with quotes + "page-stated (LLM extract)"
   derivation per 07 §11.4). Studio company facts gained 洗衣设施 /
   楼内设施 (amenities_zh) / page-stated no-fee / description lines.
4. NOTE: existing 165 rows carry v1 snapshots — new page facts + history
   populate automatically on the next successful Tavily check (currently
   quota-blocked); until then the new sections show honest unknown/
   not-captured states. Live-verified on 180 water st · Aqua House: full
   section stack renders, and the per-type commute job has already
   delivered 3 researched cards there (Downtown Brooklyn 15–22m, WTC/FiDi
   15–25m PASSED, NYU Tandon 15–25m PASSED).
5. Gate: **191 passed** (check_log event-sequence test: FIRST_CHECK →
   UNCHANGED → PRICE_CHANGED → CHECK_FAILED; detail-page parity asserts),
   ruff, mypy clean.

## Session 5, fifteenth round (2026-08-30) — AMENITIES FOR ALL PROPERTIES

Owner: amenity information for all properties (company + regular).
Coverage at start: listings 82/109 with a current amenities fact; company
0/165 (v1 snapshots); Tavily still quota-blocked → filled via hosted WEB
RESEARCH (04 §19A posture, same as commute/POI: sources required, memory
forbidden). Shipped:

1. **enrichment/amenities/research.py**: AmenityResearchService — task
   "amenity_research" (added to WEB_SEARCH_TASK_TYPES), output {amenities,
   laundry_type (LaundryType-constrained), fee_status, sources REQUIRED,
   summary}; refuses no-source or empty results. record_listing_fact()
   writes a normal amenities FactAssertion (LLM_DERIVED, MEDIUM, sources as
   evidence) so listing chips/Studio pick it up through the standard
   pipeline; apply_to_company() merges into the availability snapshot and
   NEVER overwrites page-stated values (fills UNKNOWN laundry/fee only),
   storing amenities_sources (surfaced in the detail page's FACT EVIDENCE
   expander as "amenities (web-researched)").
2. **jobs/amenity_backfill.py**: sweeps company rows lacking amenities +
   active listings lacking a current amenities resolution; commit-per-
   property; heartbeats to amenity_backfill_status.json. Launched detached
   over 192 targets (165 company + 27 listings). Early results excellent —
   "160 water st"/Pearl House: 24 amenities + IN_UNIT_W/D sourced from
   pearlhousenyc.com (the REAL official site, which Tavily search had
   never surfaced) + StreetEasy.
3. Ops notes: owner clicked Re-check all at 22:19 → the round-11 quota
   circuit breaker fired correctly (aborted, 0 damage, honest pill error).
   Portfolio grew to 173 rows (owner re-upload; new rows PENDING until
   Tavily resets). The commutes-only job had died mid-run (38/173 covered)
   — relaunched (cached work skips), running alongside the backfill.
4. Gate: **192 passed** (research sources-required refusal; company merge
   fills-gaps-only; listing fact recording), ruff, mypy clean.
