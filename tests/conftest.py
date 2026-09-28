"""Test fixtures.

Tests run against a real Postgres (the query SQL is the thing under test), but
never against the registry's data: each test gets a throw-away schema holding
small cs_rpt_* tables with the reporting views' columns, and the pool's
search_path points at it. The schema is dropped afterwards.

TEST_DATABASE_URL names the server, with a role that may create schemas. It is
never defaulted: without it, the database tests are skipped and only the pure
unit tests run.
"""

import os
import uuid
from datetime import date

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

# The app's settings require DATABASE_URL at import time; the tests replace
# the pool, so the value is never used to connect.
os.environ.setdefault("DATABASE_URL", "postgresql://unused@localhost/unused")

import asyncpg  # noqa: E402
import httpx  # noqa: E402
import pytest  # noqa: E402

from app.api.dependencies import get_db_pool  # noqa: E402
from app.main import app  # noqa: E402

# Unit paths: (name, code) per level. "none" is a registration captured
# without an address.
GEO = {
    "adaa": (("Oromia", "ET04"), ("East Shewa", "ET0407"), ("Ada'a", "ET040706"), ("Dire Arerti", "ET040706888019")),
    "adama": (("Oromia", "ET04"), ("East Shewa", "ET0407"), ("Adama", "ET040703"), ("Bofa", "ET040703888001")),
    "afdera": (("Afar", "ET02"), ("Kilbet Rasu", "ET0202"), ("Afdera", "ET020207"), ("Adkuma", "ET020207888009")),
    "none": ((None, None),) * 4,
}

SCHEMA_SQL = """
CREATE TABLE cs_rpt_crop_sown (
    crop_sown_id varchar PRIMARY KEY,
    record_status varchar,
    status text,
    lifecycle_stage text,
    crop_year text,
    production_season text,
    production_season_name text,
    registration_date date,
    farmer_key text,
    region_name text, zone_name text, woreda_name text, kebele_name text,
    region_code text, zone_code text, woreda_code text, kebele_code text
);
CREATE TABLE cs_rpt_sowing (
    sowing_id varchar PRIMARY KEY,
    crop_sown_id varchar,
    record_status varchar,
    crop_sown_record_status varchar,
    status text,
    lifecycle_stage text,
    crop_year text,
    production_season text,
    farmer_key text,
    commodity text, commodity_name text,
    season text, season_name text,
    area_sown_ha numeric(18, 6),
    sowing_date date,
    recorded_on date,
    has_pest_disease boolean,
    ownership_type text, ownership_type_name text,
    is_owned boolean,
    region_name text, zone_name text, woreda_name text, kebele_name text,
    region_code text, zone_code text, woreda_code text, kebele_code text
);
"""


def _params(n: int) -> str:
    return ",".join(f"${i}" for i in range(1, n + 1))


MEHER, BELG = "CROP_SEASON_MEHER", "CROP_SEASON_BELG"
SEASON_NAME = {MEHER: "Meher", BELG: "Belg"}
CROP_NAME = {
    "CROP_COMMODITY_WHEAT": "Wheat",
    "CROP_COMMODITY_TEFF": "Teff",
    "CROP_COMMODITY_MAIZE": "Maize",
    "CROP_COMMODITY_SORGHUM": "Sorghum",
}
OWNER, TENANT = "OWNERSHIP_TYPE_OWNER", "OWNERSHIP_TYPE_TENANT"
OWNERSHIP_NAME = {OWNER: "Owner", TENANT: "Tenant"}

# registration, status, workflow status, lifecycle stage, year, season, registered, farmer, geo
# f1 registers two plots: farmers are counted once.
CROP_SOWNS = [
    ("c1", "ACTIVE", "APPROVAL_STATUS_APPROVED", "SOWING_APPROVED", "2026", MEHER, "2026-04-01", "f1", "adaa"),
    ("c2", "ACTIVE", "APPROVAL_STATUS_DRAFT", "PENDING_PLANNING", "2026", BELG, "2026-04-01", "f1", "adama"),
    ("c3", "ACTIVE", "APPROVAL_STATUS_SUBMITTED", "SOWING_APPROVED", "2026", MEHER, "2026-05-10", "f2", "afdera"),
    ("c4", "INACTIVE", "APPROVAL_STATUS_APPROVED", "SOWING_APPROVED", "2026", MEHER, "2026-05-11", "f3", "adaa"),
    ("c5", "ACTIVE", "APPROVAL_STATUS_DRAFT", "DRAFT", "2025", MEHER, "2026-06-01", "f4", "none"),
]

# line, registration, status, crop, sowing season, hectares, sown on, ownership
# s3 is not sown yet (dated by its registration); s5 is a retired line; s6
# belongs to a retired registration.
SOWINGS = [
    ("s1", "c1", "ACTIVE", "CROP_COMMODITY_WHEAT", MEHER, 2.0, "2026-06-20", OWNER),
    ("s2", "c1", "ACTIVE", "CROP_COMMODITY_TEFF", MEHER, 0.5, "2026-06-25", TENANT),
    ("s3", "c2", "ACTIVE", "CROP_COMMODITY_MAIZE", BELG, 1.5, None, OWNER),
    ("s4", "c3", "ACTIVE", "CROP_COMMODITY_WHEAT", MEHER, 3.0, "2026-07-02", None),
    ("s5", "c3", "INACTIVE", "CROP_COMMODITY_TEFF", MEHER, 4.0, "2026-07-03", None),
    ("s6", "c4", "ACTIVE", "CROP_COMMODITY_WHEAT", MEHER, 9.0, "2026-07-04", OWNER),
    ("s7", "c5", "ACTIVE", "CROP_COMMODITY_SORGHUM", MEHER, 0.0, "2026-06-05", None),
]


def _date(value: str | None) -> date | None:
    return value and date.fromisoformat(value)


async def _seed(conn: asyncpg.Connection) -> None:
    await conn.execute(SCHEMA_SQL)
    parent = {}
    for cid, rstatus, status, stage, year, season, reg, farmer, place in CROP_SOWNS:
        names = [n for n, _ in GEO[place]]
        codes = [c for _, c in GEO[place]]
        parent[cid] = (rstatus, status, stage, year, season, reg, farmer, names, codes)
        await conn.execute(
            f"INSERT INTO cs_rpt_crop_sown VALUES ({_params(17)})",
            cid,
            rstatus,
            status,
            stage,
            year,
            season,
            SEASON_NAME[season],
            _date(reg),
            farmer,
            *names,
            *codes,
        )
    for sid, cid, rstatus, crop, season, ha, sown, owner in SOWINGS:
        p_rstatus, status, stage, year, p_season, reg, farmer, names, codes = parent[cid]
        await conn.execute(
            f"INSERT INTO cs_rpt_sowing VALUES ({_params(28)})",
            sid,
            cid,
            rstatus,
            p_rstatus,
            status,
            stage,
            year,
            p_season,
            farmer,
            crop,
            CROP_NAME[crop],
            season,
            SEASON_NAME[season],
            ha,
            _date(sown),
            _date(sown or reg),
            False,
            owner,
            OWNERSHIP_NAME.get(owner),
            owner == OWNER,
            *names,
            *codes,
        )


@pytest.fixture
async def pool():
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL is not set")
    dsn = TEST_DATABASE_URL
    schema = f"test_dash_{uuid.uuid4().hex[:10]}"
    admin = await asyncpg.connect(dsn)
    await admin.execute(f"CREATE SCHEMA {schema}")
    try:
        pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2, server_settings={"search_path": schema})
        async with pool.acquire() as conn:
            await _seed(conn)
        yield pool
        await pool.close()
    finally:
        await admin.execute(f"DROP SCHEMA {schema} CASCADE")
        await admin.close()


@pytest.fixture
async def client(pool):
    app.dependency_overrides[get_db_pool] = lambda: pool
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
