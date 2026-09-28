# AGENTS.md

Guidance for contributors and coding agents working in this repository. Read the
[README](README.md) and [docs/](docs/) first. This file lists the rules that are easy to get wrong.

## What this service is

A read-only FastAPI service that returns aggregate statistics about the crop sown registry, one
endpoint per dashboard chart. Its only client is the OAN dashboards BFF, which caches the responses.

## Layout

```
app/main.py               app, lifespan (asyncpg pool), CORS, /health
app/core/config.py        settings (DATABASE_URL, ALLOWED_ORIGINS, …)
app/core/geo.py           dashboard geography levels, P-code normalisation
app/api/filters.py        ChartFilters + build_where_clause: the only place input becomes SQL
app/api/routes/charts.py  chart handlers
tests/                    pytest suite against a throw-away schema
docs/                     architecture, API reference, configuration, development, deployment, security
```

The reporting views themselves are defined in the crop sown registry repository
(`docker/db-seed/reporting_views.sql`), which owns the register's schema.

## Rules

### Data access
- Query **only** `cs_rpt_crop_sown` and `cs_rpt_sowing`. Never query the `g2p_register_*` tables: a
  change the registry makes to its schema is absorbed by its reporting views, not by this service.
- Aggregate area from `area_sown_ha` only: it is normalised to hectares from the recorded unit.
- Count farmers with `COUNT(DISTINCT farmer_key)`: one farmer may register several plots.
- Area, crops, ownership and seasons are sowing-line facts: read them from `cs_rpt_sowing`.
  Registration counts by status or lifecycle stage come from `cs_rpt_crop_sown`.
- Filter and group geography by `<level>_code`; label with `<level>_name`. Use `geo.code_column()` /
  `geo.name_column()` rather than writing the column names.
- `build_where_clause` counts `ACTIVE` records unless `recordState` is given (on the sowing view,
  active lines of active registrations). Pass `default_active=False` only for a breakdown by status.
- Crops, seasons and ownership types come from the registry's lookup table, so they are returned
  with both their label and their lookup key (`crop`, `crop_code`). Workflow values (`status`,
  `lifecycle_stage`) are returned as codes.

### SQL safety
- Interpolate only `where.sql` and literal column names. Every input value is bound through
  `where.values`.
- Pass fixed predicates as `build_where_clause(extra=…)`. Never write `{where.sql} AND …`: with no
  filters the clause is empty.
- Never take a column name, table name or sort order from input without an allow-list.

### Contract
- The response keys are a contract with the dashboards. Adding a key is fine. Renaming or removing
  one is a breaking change.
- Chart IDs are unique across all dashboard services (the dashboards route a chart to exactly one
  service), so every chart ID here starts with `crop`.
- Every chart's keys are listed in `CONTRACT` in `tests/test_charts.py`. Keep that list,
  `docs/api-reference.md` and the Postman collection in step with the code.
- Cast aggregates in SQL (`::bigint`, `::float8`) so they serialise as numbers.

### Privacy
- Aggregates only: no names, IDs, contact details, GPS points or coordinates in any response.

## Before handing off

```bash
make lint
make test
```

Both must pass. For a new or changed endpoint, also run it against a real registry database with no
filters and with every filter set.

## Conventions

- Python 3.11, async throughout, and one pool per worker. Do not open ad-hoc connections.
- Chart IDs and query parameters are camelCase (they are the dashboard's names). Python
  identifiers are snake_case.
- Conventional Commits (`feat(charts): …`, `fix: …`, `docs: …`).
- Never commit `.env`, virtual environments, or one-off patch scripts.
