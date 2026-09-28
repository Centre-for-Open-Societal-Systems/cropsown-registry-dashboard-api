# Crop Sown Registry Dashboard API

The **dashboard service** of the OpenG2P crop sown registry: a read-only HTTP service that serves
aggregate statistics about the registry to the OAN dashboards. It exposes one endpoint per dashboard
chart and computes each response from the registry's materialized reporting views
(`cs_rpt_crop_sown`, `cs_rpt_sowing`).

Each registry (farmer, livestock, crop sown, …) publishes its statistics through its own dashboard
service, and all of them share one HTTP contract. This service is the only component that holds
credentials for the crop sown registry database: the dashboards call the service and never the
database.

- **Stack:** Python 3.11, FastAPI, asyncpg, gunicorn with Uvicorn workers
- **Consumer:** the OAN dashboards backend-for-frontend (BFF), which caches responses
- **Data:** aggregates only. The service never returns names, identifiers, contact details, GPS
  points or coordinates

## Quick start

The reporting views are created by the crop sown registry itself (its db-seed image ships
`reporting_views.sql`; its Helm chart and local compose stack apply it). Against a local registry
stack:

```bash
# in the cropsown-registry repository: build the cs_rpt_* views
docker compose --env-file local/.env --profile reporting up reporting-views

# here
cp .env.example .env              # point DATABASE_URL at the crop sown registry database
docker compose up -d --build      # serves on http://localhost:8007
curl http://localhost:8007/health
curl "http://localhost:8007/api/v1/charts/cropKpis?region=ET04"
```

Interactive OpenAPI docs are served at `http://localhost:8007/docs`.

A Postman collection with every endpoint is in `postman/`. Each request has contract tests, and the
filters are included but disabled. Import it and set the `baseUrl` variable to the service's address
(default `http://localhost:8007`), or run it from the command line:

```bash
npx newman run "postman/Crop Sown Registry Dashboard Service.postman_collection.json" \
  --env-var baseUrl=http://localhost:8007
```

## Endpoints at a glance

| Endpoint | Returns |
| --- | --- |
| `GET /health` | Liveness and database connectivity |
| `GET /api/v1/charts/cropKpis` | Headline totals: area sown, owned area, farmers, registrations, crops, woredas, average plot |
| `GET /api/v1/charts/cropAreaByCrop` | Hectares and farmers per crop |
| `GET /api/v1/charts/cropAreaByRegion` | Hectares and farmers per region |
| `GET /api/v1/charts/cropAreaByZone`, `…ByWoreda`, `…ByKebele` | The same per zone, woreda and kebele, for map drill-down |
| `GET /api/v1/charts/cropTopWoredas` | The eight woredas with the most area sown |
| `GET /api/v1/charts/cropLandTenureSplit` | Plots and hectares per ownership type |
| `GET /api/v1/charts/cropBySeason` | Hectares and farmers per sowing season |
| `GET /api/v1/charts/cropTrendByMonth` | Farmers, area and owned area per sowing month |
| `GET /api/v1/charts/cropByStatus` | Registrations per approval-workflow status |
| `GET /api/v1/charts/cropByLifecycleStage` | Registrations per lifecycle stage |
| `GET /api/v1/charts/cropByRecordState` | Registrations per record status |

All chart endpoints accept the same filters: `region`, `zone`, `woreda`, `kebele`, `recordState`,
`status`, `season`, `cropYear` and `commodity`. See the [API reference](docs/api-reference.md) for
the full contract.

## Documentation

| Document | Contents |
| --- | --- |
| [Architecture](docs/architecture.md) | Where the service sits, data flow, data sources, design decisions |
| [API reference](docs/api-reference.md) | Every endpoint, parameter and response field, with examples |
| [Configuration](docs/configuration.md) | Environment variables |
| [Development](docs/development.md) | Local setup, tests, linting, adding an endpoint |
| [Deployment and operations](docs/deployment.md) | Container image, Helm, sizing, health checks, troubleshooting |
| [Security](docs/security.md) | Threat model, SQL-injection controls, network exposure, data protection |
| [AGENTS.md](AGENTS.md) | Rules for contributors and coding agents working in this repository |

## License

See [LICENSE](LICENSE).
