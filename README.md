# NYC/NJ Rental Listing Agent

Internal, local, single-user system that acquires NYC/NJ rental listings
(Studio/1BR/2BR), maintains a canonical PostgreSQL/PostGIS inventory with full
provenance, enriches listings with media, transit, and commute intelligence, and
presents them in a map-first Streamlit review UI.

Specifications live in [md/](md/) and are the source of truth. Session-to-session
build state lives in [PROJECT_EXECUTION_STATE.md](PROJECT_EXECUTION_STATE.md).

## Prerequisites

- Windows 11 with Docker Desktop
- Python 3.12 and [uv](https://docs.astral.sh/uv/)

## Setup

1. Start the database (PostgreSQL 17 + PostGIS 3.5 in Docker, port **5433**;
   creates `rental_dev` and `rental_test` with postgis/pg_trgm/pgcrypto):

```bash
docker compose up -d
```

2. Install dependencies:

```bash
uv sync
```

3. Create local configuration (no real credentials required yet):

```bash
cp .env.example .env
```

4. Apply migrations to the development database:

```bash
uv run alembic upgrade head
```

## Development commands

Run all tests (integration tests use the real `rental_test` PostGIS database and
recreate its schema from migrations at session start — never SQLite):

```bash
uv run pytest
```

Lint, format, and type-check:

```bash
uv run ruff check src tests migrations
```

```bash
uv run ruff format src tests migrations
```

```bash
uv run mypy
```

Autogenerate a migration after model changes (review before committing; Alembic
cannot see everything — verify constraints):

```bash
uv run alembic revision --autogenerate -m "describe change"
```

Seed reference data (candidate sources + destination registry) into the dev DB:

```bash
uv run python -c "from sqlalchemy.orm import Session; from rental_agent.config.settings import load_settings; from rental_agent.db.engine import build_engine; from rental_agent.config.source_seed import seed_sources; from rental_agent.config.destination_seed import seed_destinations; e=build_engine(load_settings()); s=Session(e); print(seed_sources(s), seed_destinations(s)); s.commit()"
```

Run the map-first UI (Leaflet via streamlit-folium):

```bash
uv run streamlit run src/rental_agent/ui/app.py --server.address 127.0.0.1
```

Run one full inventory refresh manually (idempotent per local day):

```bash
uv run --no-sync python -m rental_agent.jobs.weekday_refresh --manual
```

Install the automated weekday 6:00 AM refresh (one-time; runs-when-available if
the desktop was off):

```bash
powershell -ExecutionPolicy Bypass -File scripts/schedule/install_task.ps1
```

Pause / resume / remove the schedule with
`schtasks /Change /TN "RentalAgent Weekday Refresh" /DISABLE` (`/ENABLE`), or
`schtasks /Delete /TN "RentalAgent Weekday Refresh" /F`.

## Repository layout (per md/08 §5)

| Path | Responsibility |
| --- | --- |
| `src/rental_agent/config/` | Typed settings (development/production), logging, source seed |
| `src/rental_agent/contracts/` | Enums, ParsedSourceObservation envelope, provider interfaces, fakes |
| `src/rental_agent/db/` | Declarative base, engine, ORM models (5 schemas: app/ops/raw/config/audit), repositories |
| `src/rental_agent/acquisition/` | Source adapters (Phase 2+) |
| `src/rental_agent/canonical/` | Identity/reconciliation services; selection & shortlist services |
| `src/rental_agent/enrichment/` | llm / location / transit / commute / media workers (Phase 4+) |
| `src/rental_agent/validation/` | Deterministic business rules (e.g. laundry badge invariant) |
| `src/rental_agent/jobs/` | PostgreSQL-backed leased job queue |
| `src/rental_agent/exports/` | CSV export pipeline (Phase 7) |
| `src/rental_agent/ui/` | Streamlit app (Phase 8) |
| `migrations/` | Alembic; baseline creates all 43 tables |
| `local_data/` | media / raw / exports / logs / backups (gitignored) |

## Non-negotiable invariants (enforced by schema + services + tests)

- No broker/agent/landlord contact data anywhere (columns are structurally
  forbidden; `tests/unit/test_schema_purity.py` guards this).
- No commute/transit/listing quality scores.
- `indoor_laundry_badge_eligible` (室内洗烘) only via confirmed in-unit
  washer+dryer — DB CHECK plus `validation/laundry.py`.
- Marketing selection and client-shortlist membership are independent, human-only
  states; automatic jobs cannot write them (`HumanActionRequired`).
- Live filter matches are never persisted as shortlist entries.
- CSV is export-only; PostgreSQL is the system of record.
- Windows Task Scheduler owns recurring scheduling; no in-process cron.

## Notes

- The Postgres data lives in a named Docker volume (`rental_agent_pgdata`), not
  in this OneDrive-synced folder — syncing live database files corrupts them.
- OneDrive can transiently lock `.venv` files during `uv sync`; retry or use
  `uv run --no-sync` when the environment is already up to date.
