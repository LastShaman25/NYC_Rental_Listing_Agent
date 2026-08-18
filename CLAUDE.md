# NYC Rental Listing Agent — session guidance

## UI & styling
- Strictly follow the design tokens, typography, and spacing defined in
  `md/DESIGN.md` ("Kinetic Mapview System"). No arbitrary hex colors or
  spacing values outside it.
- The design system is implemented in `src/rental_agent/ui/theme.py`
  (palette tokens in `COLORS`, injected CSS, `dense_table()`, `filter_chips()`,
  `marker_accent()`). Extend that module rather than inlining styles in pages.
- Read-only tables use `theme.dense_table()`, not `st.dataframe`
  (st.dataframe is canvas-drawn and cannot be styled).
- Never set `font-family` with `!important` on selectors that reach
  Streamlit's Material Symbols icons — icon ligatures render as raw text.

## Project conventions
- Specs live in `md/00`–`08`; session state in `PROJECT_EXECUTION_STATE.md`
  (update it after every working round).
- Local-only, single user: no cloud, no auth, no contact data, no scores.
  CSV is the only export. Windows Task Scheduler owns scheduling.
- Run tooling with `uv run --no-sync` (OneDrive locks .venv during sync).
- Batch files must be written with CRLF line endings.
- Validation gate before reporting done: `uv run --no-sync pytest -q`,
  `uv run --no-sync ruff check src tests`, `uv run --no-sync mypy src`.
