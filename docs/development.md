# Development

## Prerequisites

- Python 3.11 (or [uv](https://docs.astral.sh/uv/))
- A PostgreSQL server that is reachable locally:
  - for running the service: the crop sown registry database, with its reporting views
  - for running the tests: any server where the test user can create a schema
- Docker, optionally, to run the service as a container

## Set up

```bash
cp .env.example .env                 # set DATABASE_URL and PGPASSWORD
python -m venv .venv && . .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

With uv instead:

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv -r requirements-dev.txt
```

## A registry database to run against

The crop sown registry repository runs the whole registry locally with Docker Compose and can build
the reporting views in it:

```bash
# in cropsown-registry
docker compose --env-file local/.env up -d
docker compose --env-file local/.env --profile reporting up reporting-views
```

Its Postgres is published on the host (port `POSTGRES_PORT` in `local/.env`), so set:

```ini
DATABASE_URL=postgresql://<REGISTRY_DB_USER>@localhost:<POSTGRES_PORT>/<REGISTRY_DB>   # make dev
DATABASE_URL=postgresql://<REGISTRY_DB_USER>@host.docker.internal:<POSTGRES_PORT>/<REGISTRY_DB>   # docker compose
PGPASSWORD=<REGISTRY_DB_PASSWORD>
```

The views are materialized: run the `reporting-views` service again to pick up records added since.

## Run

```bash
make dev                         # uvicorn with reload on http://localhost:8007
docker compose up -d --build     # production-like container on http://localhost:8007
```

The compose file requires `DATABASE_URL` and publishes the port on `127.0.0.1` only (`API_PORT`
changes it).

## Tests

```bash
make test        # pytest -q
```

The database tests need a PostgreSQL server, given as `TEST_DATABASE_URL` (a role that may create
schemas), but **not** registry data. Without `TEST_DATABASE_URL` they are skipped and only the unit
tests run. A throw-away server is enough:

```bash
docker run -d --rm --name dash-test-db -e POSTGRES_PASSWORD=test -p 127.0.0.1:55499:5432 postgres:16
TEST_DATABASE_URL=postgresql://postgres:test@127.0.0.1:55499/postgres make test
```

For each database test, a fixture in `tests/conftest.py`:

1. creates a uniquely named schema (`test_dash_<random>`)
2. creates `cs_rpt_crop_sown` and `cs_rpt_sowing` tables in it, with the reporting views' columns,
   and loads a fixed dataset of five registrations and seven sowing lines
3. opens a pool whose `search_path` is that schema, and swaps it in for the app's pool through
   FastAPI dependency overrides
4. drops the schema afterwards

| File | Covers |
| --- | --- |
| `tests/test_charts.py` | The **contract** (exact response keys per chart), requests with no filters and with every filter set, and behaviour: the `ACTIVE` default on both views, geo code forms, lookup key/label filters, distinct farmers, unknown ownership and address, the commodity filter on registrations, `/health` |
| `tests/test_filters.py` | `build_where_clause`: placeholder numbering, `all` handling, `extra`, `alias`, view-specific columns, and that values never appear in the SQL text |
| `tests/test_geo.py` | P-code normalisation |

## Lint and format

```bash
make lint        # ruff check + ruff format --check
make format      # apply fixes
```

The rules are in `pyproject.toml`: line length 120, rule sets E, F, I, B and UP. B008 is ignored,
because FastAPI's `Depends()` defaults trigger it.

## Adding a chart endpoint

1. **Pick the view.** `cs_rpt_sowing` for area, crops, ownership, seasons and farmers;
   `cs_rpt_crop_sown` for counting registrations (`view="crop_sown"`).
2. **Write the handler** in `app/api/routes/charts.py`:

   ```python
   @router.get("/cropAreaByPestStatus", response_model=Rows)
   async def get_area_by_pest_status(
       filters: ChartFilters = Depends(), pool: asyncpg.Pool = Depends(get_db_pool)
   ):
       where = build_where_clause(filters)
       query = f"""
           SELECT COALESCE(has_pest_disease, false) AS has_pest_disease,
                  COALESCE(SUM(area_sown_ha), 0)::float8 AS area
           FROM cs_rpt_sowing
           {where.sql}
           GROUP BY 1
           ORDER BY area DESC
       """
       return await fetch(pool, query, where)
   ```

   Rules:
   - interpolate only `where.sql`; every value comes from `where.values`
   - pass fixed predicates as `extra=(...)`, and never append `AND …` to `where.sql`, because with
     no filters it is empty
   - pass the right `view=` so the view's own columns are used for the filters
   - cast every aggregate (`::bigint`, `::float8`)
3. **Add the response keys** to `CONTRACT` in `tests/test_charts.py`, and add behaviour tests for
   anything non-obvious.
4. **Document it** in [api-reference.md](api-reference.md) and add it to the Postman collection.
5. **Register it in the dashboards.** Add the chart ID to the `cropsown-registry` entry of
   `DASHBOARD_SERVICES` in the dashboards' `server/dashboard-services.ts`, so the BFF routes it
   here.

## Changing the reporting views

The views are owned by the crop sown registry (`docker/db-seed/reporting_views.sql` in that
repository), not by this one. A new column has to be added there, and the views re-created, before
a query here can use it. Update the test fixture tables in `tests/conftest.py` to match.
