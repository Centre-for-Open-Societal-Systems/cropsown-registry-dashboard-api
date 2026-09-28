# API reference

- **Base URL:** `http://<host>:8007` when run with the provided compose file (the container listens
  on `8000`).
- **Route prefix:** `/api/v1` (configurable with `API_V1_STR`).
- **Methods and responses:** every endpoint is `GET` and returns `application/json`.
- **OpenAPI:** the generated schema is at `/openapi.json`, with an interactive UI at `/docs`.

## Conventions

### Response shape

Every chart endpoint returns a **JSON array of row objects**. There is no envelope:

- a chart with no matching data returns `[]`
- a single-figure chart (`cropKpis`) returns an array with one object

Counts are JSON integers; areas are floating-point **hectares**.

Crops, seasons and ownership types come from the registry's lookup table, so they are returned both
as a label (`crop`, `season`, `ownership_type`) and as the lookup key (`crop_code`, `season_code`,
`ownership_type_code`). Workflow values (`status`, `lifecycle_stage`, `record_state`) are codes, and
the client labels them. A missing value is `"Unknown"` (labels) or `"UNKNOWN"` (codes).

A geographic unit is returned with its name and its P-code (`region`, `region_code`). A
registration without an address is reported under `"Unknown"`, so totals are never silently reduced.

### Response keys are a contract

The key names of each chart are relied on by the dashboards, and the test suite pins them. Renaming
or removing a key is a breaking change. Adding a key is not.

## Common filter parameters

Every chart endpoint accepts these optional query parameters. The value `all` behaves the same as
leaving the parameter out.

| Parameter | Matches | Notes |
| --- | --- | --- |
| `region` | the registration's region | A P-code in any of the forms `ET04`, `region-ET04` or `REGION_ET04` |
| `zone` | the registration's zone | as above |
| `woreda` | the registration's woreda | as above |
| `kebele` | the registration's kebele | as above |
| `recordState` | `record_status` | Case-insensitive. **If omitted, only `ACTIVE` records are counted** (on sowing charts: active lines of active registrations), except in `cropByRecordState` |
| `status` | the approval-workflow status | The key (`APPROVAL_STATUS_APPROVED`) or its last part (`APPROVED`), case-insensitive |
| `season` | the registration's production season | The key (`CROP_SEASON_MEHER`) or its last part (`MEHER`), case-insensitive |
| `cropYear` | the registration's crop year | Exact, for example `2026` |
| `commodity` | the crop sown | The key (`CROP_COMMODITY_WHEAT`), its last part (`WHEAT`) or the label (`Wheat`), case-insensitive. On registration charts it selects the registrations with at least one live sowing line of that crop |

The filters combine with AND. Unknown parameters are ignored.

## Endpoints

### `GET /health`

Checks that the process is serving and that the database answers `SELECT 1`.

| Status | Body | Meaning |
| --- | --- | --- |
| 200 | `{"status": "ok"}` | Healthy |
| 500 | error | The database is unreachable or the pool is exhausted |

---

### `GET /api/v1/charts/cropKpis`

Headline figures. Returns one object.

| Field | Type | Meaning |
| --- | --- | --- |
| `total_area` | number | Hectares sown |
| `owned_area` | number | … on plots the farmer owns |
| `farmers` | integer | Distinct farmers |
| `registrations` | integer | Registrations with at least one matching sowing line |
| `crop_types` | integer | Distinct crops sown |
| `woredas_reporting` | integer | Distinct woredas |
| `avg_plot_size` | number | Average hectares per sowing line, over lines with an area |

```json
[{"total_area": 1352.22, "owned_area": 344.61, "farmers": 509, "registrations": 509,
  "crop_types": 153, "woredas_reporting": 312, "avg_plot_size": 2.68}]
```

---

### `GET /api/v1/charts/cropAreaByCrop`

Hectares per crop, largest first.

| Field | Type | Meaning |
| --- | --- | --- |
| `crop` | string | Crop label |
| `crop_code` | string | Crop lookup key, e.g. `CROP_COMMODITY_WHEAT` |
| `area` | number | Hectares sown |
| `farmers` | integer | Distinct farmers who sowed it |

---

### `GET /api/v1/charts/cropAreaByRegion`, `…ByZone`, `…ByWoreda`, `…ByKebele`

Hectares per administrative unit at the given level, largest first. The dashboards draw the
choropleth from these.

| Field | Type | Meaning |
| --- | --- | --- |
| `<level>` | string | Unit name (`region`, `zone`, `woreda` or `kebele`) |
| `<level>_code` | string | P-code, for joining to map boundaries; `"Unknown"` without an address |
| `farmers` | number | **Hectares sown**, rounded to 2 decimals (the map reads its value from this key) |
| `farmer_count` | integer | Distinct farmers |

```json
[{"region": "Oromia", "region_code": "ET04", "farmers": 131.4, "farmer_count": 52}]
```

---

### `GET /api/v1/charts/cropTopWoredas`

The eight woredas with the most hectares sown.

| Field | Type | Meaning |
| --- | --- | --- |
| `woreda` | string | Woreda name |
| `woreda_code` | string | P-code |
| `area` | number | Hectares sown |
| `farmers` | integer | Distinct farmers |

---

### `GET /api/v1/charts/cropLandTenureSplit`

Sowing lines and hectares per plot ownership type. Lines whose registration has no cultivation
record yet are reported as `Unknown`.

| Field | Type | Meaning |
| --- | --- | --- |
| `ownership_type` | string | Label, for example `Owner`, `Tenant`, `Crop Sharing` |
| `ownership_type_code` | string | Lookup key, for example `OWNERSHIP_TYPE_OWNER` |
| `parcels` | integer | Sowing lines |
| `area` | number | Hectares sown |

---

### `GET /api/v1/charts/cropBySeason`

Hectares per sowing season.

| Field | Type | Meaning |
| --- | --- | --- |
| `season` | string | Season label, for example `Meher` |
| `season_code` | string | Lookup key, for example `CROP_SEASON_MEHER` |
| `area` | number | Hectares sown |
| `farmers` | integer | Distinct farmers |

---

### `GET /api/v1/charts/cropTrendByMonth`

Sowing per month, oldest first. A line not sown yet is dated by its registration.

| Field | Type | Meaning |
| --- | --- | --- |
| `period` | string | `YYYY-MM` |
| `farmers` | integer | Distinct farmers |
| `total_area` | number | Hectares sown |
| `owned_area` | number | … on owned plots |

---

### `GET /api/v1/charts/cropByStatus`

Registrations per approval-workflow status.

| Field | Type | Meaning |
| --- | --- | --- |
| `status` | string | For example `APPROVAL_STATUS_DRAFT`, `APPROVAL_STATUS_APPROVED`, or `UNKNOWN` |
| `registrations` | integer | Registrations |

---

### `GET /api/v1/charts/cropByLifecycleStage`

Registrations per lifecycle stage.

| Field | Type | Meaning |
| --- | --- | --- |
| `lifecycle_stage` | string | For example `PENDING_PLANNING`, `SOWING_APPROVED`, `HARVESTING_APPROVED`, or `UNKNOWN` |
| `registrations` | integer | Registrations |

---

### `GET /api/v1/charts/cropByRecordState`

Registrations per record status. This chart ignores the `ACTIVE` default, so it sees every status.

| Field | Type | Meaning |
| --- | --- | --- |
| `record_state` | string | `record_status`, for example `ACTIVE` |
| `registrations` | integer | Registrations |

## Errors

| Status | When |
| --- | --- |
| 404 | Unknown chart ID |
| 422 | A query parameter has the wrong type |
| 500 | Database error, for example the reporting views do not exist yet |
