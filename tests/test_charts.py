import pytest

# The keys each oan_dashboards component reads. A chart whose keys drift from
# these renders empty in the UI without any error, so pin them here.
CONTRACT = {
    "cropKpis": {
        "total_area",
        "owned_area",
        "farmers",
        "registrations",
        "crop_types",
        "woredas_reporting",
        "avg_plot_size",
    },
    "cropAreaByCrop": {"crop", "crop_code", "area", "farmers"},
    "cropAreaByRegion": {"region", "region_code", "farmers", "farmer_count"},
    "cropAreaByZone": {"zone", "zone_code", "farmers", "farmer_count"},
    "cropAreaByWoreda": {"woreda", "woreda_code", "farmers", "farmer_count"},
    "cropAreaByKebele": {"kebele", "kebele_code", "farmers", "farmer_count"},
    "cropTopWoredas": {"woreda", "woreda_code", "area", "farmers"},
    "cropLandTenureSplit": {"ownership_type", "ownership_type_code", "parcels", "area"},
    "cropBySeason": {"season", "season_code", "area", "farmers"},
    "cropTrendByMonth": {"period", "farmers", "total_area", "owned_area"},
    "cropByStatus": {"status", "registrations"},
    "cropByLifecycleStage": {"lifecycle_stage", "registrations"},
    "cropByRecordState": {"record_state", "registrations"},
}

ALL_FILTERS = {
    "region": "ET04",
    "zone": "ET0407",
    "woreda": "ET040706",
    "kebele": "ET040706888019",
    "recordState": "ACTIVE",
    "status": "APPROVED",
    "season": "MEHER",
    "cropYear": "2026",
    "commodity": "WHEAT",
}


async def get(client, chart, **params):
    response = await client.get(f"/api/v1/charts/{chart}", params=params)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("chart", sorted(CONTRACT))
async def test_contract_without_filters(client, chart):
    rows = await get(client, chart)
    assert rows, f"{chart} returned no rows"
    for row in rows:
        assert set(row) == CONTRACT[chart]


@pytest.mark.parametrize("chart", sorted(CONTRACT))
async def test_every_filter_at_once(client, chart):
    rows = await get(client, chart, **ALL_FILTERS)
    for row in rows:
        assert set(row) == CONTRACT[chart]


async def test_kpis_count_active_lines_of_active_registrations(client):
    [kpis] = await get(client, "cropKpis")
    # s5 is retired and s6 belongs to a retired registration; f1 has two plots.
    assert kpis == {
        "total_area": pytest.approx(7.0),
        "owned_area": pytest.approx(3.5),
        "farmers": 3,
        "registrations": 4,
        "crop_types": 4,
        "woredas_reporting": 3,
        "avg_plot_size": pytest.approx(1.75),
    }


@pytest.mark.parametrize("region", ["ET04", "region-ET04", "REGION_ET04"])
async def test_geography_accepts_any_code_form(client, region):
    [kpis] = await get(client, "cropKpis", region=region)
    assert (kpis["total_area"], kpis["registrations"]) == (pytest.approx(4.0), 2)


@pytest.mark.parametrize("commodity", ["CROP_COMMODITY_WHEAT", "WHEAT", "wheat"])
async def test_commodity_filter(client, commodity):
    [kpis] = await get(client, "cropKpis", commodity=commodity)
    assert (kpis["total_area"], kpis["crop_types"]) == (pytest.approx(5.0), 1)


async def test_commodity_filter_on_registrations(client):
    rows = await get(client, "cropByStatus", commodity="WHEAT")
    assert {r["status"]: r["registrations"] for r in rows} == {
        "APPROVAL_STATUS_APPROVED": 1,
        "APPROVAL_STATUS_SUBMITTED": 1,
    }


@pytest.mark.parametrize("season", ["CROP_SEASON_BELG", "BELG", "belg"])
async def test_season_filter(client, season):
    [kpis] = await get(client, "cropKpis", season=season)
    assert (kpis["total_area"], kpis["registrations"]) == (pytest.approx(1.5), 1)


async def test_status_filter(client):
    [kpis] = await get(client, "cropKpis", status="DRAFT")
    assert (kpis["total_area"], kpis["registrations"]) == (pytest.approx(1.5), 2)


async def test_crop_year_filter(client):
    [kpis] = await get(client, "cropKpis", cropYear="2025")
    assert (kpis["total_area"], kpis["registrations"], kpis["avg_plot_size"]) == (0, 1, 0)


async def test_area_by_crop(client):
    rows = await get(client, "cropAreaByCrop")
    assert [(r["crop"], r["area"], r["farmers"]) for r in rows] == [
        ("Wheat", pytest.approx(5.0), 2),
        ("Maize", pytest.approx(1.5), 1),
        ("Teff", pytest.approx(0.5), 1),
        ("Sorghum", 0, 1),
    ]


async def test_area_by_region_puts_hectares_under_farmers(client):
    rows = await get(client, "cropAreaByRegion")
    assert [(r["region"], r["region_code"], r["farmers"], r["farmer_count"]) for r in rows] == [
        ("Oromia", "ET04", pytest.approx(4.0), 1),
        ("Afar", "ET02", pytest.approx(3.0), 1),
        ("Unknown", "Unknown", 0, 1),
    ]


async def test_top_woredas(client):
    rows = await get(client, "cropTopWoredas")
    assert [(r["woreda"], r["area"]) for r in rows] == [
        ("Afdera", pytest.approx(3.0)),
        ("Ada'a", pytest.approx(2.5)),
        ("Adama", pytest.approx(1.5)),
    ]


async def test_tenure_reports_unknown_ownership(client):
    rows = await get(client, "cropLandTenureSplit")
    assert [(r["ownership_type"], r["parcels"], r["area"]) for r in rows] == [
        ("Owner", 2, pytest.approx(3.5)),
        ("Unknown", 2, pytest.approx(3.0)),
        ("Tenant", 1, pytest.approx(0.5)),
    ]


async def test_by_season(client):
    rows = await get(client, "cropBySeason")
    assert [(r["season"], r["area"], r["farmers"]) for r in rows] == [
        ("Meher", pytest.approx(5.5), 3),
        ("Belg", pytest.approx(1.5), 1),
    ]


async def test_trend_by_month(client):
    rows = await get(client, "cropTrendByMonth")
    assert rows == [
        {"period": "2026-04", "farmers": 1, "total_area": pytest.approx(1.5), "owned_area": pytest.approx(1.5)},
        {"period": "2026-06", "farmers": 2, "total_area": pytest.approx(2.5), "owned_area": pytest.approx(2.0)},
        {"period": "2026-07", "farmers": 1, "total_area": pytest.approx(3.0), "owned_area": 0},
    ]


async def test_status_breakdown(client):
    rows = await get(client, "cropByStatus")
    assert {r["status"]: r["registrations"] for r in rows} == {
        "APPROVAL_STATUS_DRAFT": 2,
        "APPROVAL_STATUS_APPROVED": 1,
        "APPROVAL_STATUS_SUBMITTED": 1,
    }


async def test_lifecycle_breakdown(client):
    rows = await get(client, "cropByLifecycleStage")
    assert {r["lifecycle_stage"]: r["registrations"] for r in rows} == {
        "SOWING_APPROVED": 2,
        "PENDING_PLANNING": 1,
        "DRAFT": 1,
    }


async def test_record_state_breakdown_sees_every_status(client):
    rows = await get(client, "cropByRecordState")
    assert {r["record_state"]: r["registrations"] for r in rows} == {"ACTIVE": 4, "INACTIVE": 1}


async def test_unknown_chart_is_404(client):
    response = await client.get("/api/v1/charts/farmerKpis")
    assert response.status_code == 404


async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
