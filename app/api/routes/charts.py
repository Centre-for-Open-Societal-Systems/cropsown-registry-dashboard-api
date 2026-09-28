"""Chart endpoints for the crop sown registry dashboard.

Each endpoint returns a JSON array of row objects whose keys match what the
oan_dashboards components read. Read only from the cs_rpt_* reporting views;
see AGENTS.md for the rules.

  cs_rpt_crop_sown  one row per farmer-plot-season registration
  cs_rpt_sowing     one row per sowing line; area_sown_ha is the area to SUM
"""

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends

from app.api.dependencies import get_db_pool
from app.api.filters import ChartFilters, Where, build_where_clause
from app.core import geo

router = APIRouter()

Rows = list[dict[str, Any]]


async def fetch(pool: asyncpg.Pool, query: str, where: Where) -> Rows:
    async with pool.acquire() as conn:
        records = await conn.fetch(query, *where.values)
    return [dict(r) for r in records]


@router.get("/cropKpis", response_model=Rows)
async def get_crop_kpis(filters: ChartFilters = Depends(), pool: asyncpg.Pool = Depends(get_db_pool)):
    where = build_where_clause(filters)
    query = f"""
        SELECT
            COALESCE(SUM(area_sown_ha), 0)::float8                           AS total_area,
            COALESCE(SUM(area_sown_ha) FILTER (WHERE is_owned), 0)::float8   AS owned_area,
            COUNT(DISTINCT farmer_key)::bigint                               AS farmers,
            COUNT(DISTINCT crop_sown_id)::bigint                             AS registrations,
            COUNT(DISTINCT commodity)::bigint                                AS crop_types,
            COUNT(DISTINCT COALESCE(woreda_code, woreda_name))::bigint       AS woredas_reporting,
            -- Lines with nothing sown yet say nothing about plot size.
            COALESCE(AVG(NULLIF(area_sown_ha, 0)), 0)::float8                AS avg_plot_size
        FROM cs_rpt_sowing
        {where.sql}
    """
    return await fetch(pool, query, where)


@router.get("/cropAreaByCrop", response_model=Rows)
async def get_area_by_crop(filters: ChartFilters = Depends(), pool: asyncpg.Pool = Depends(get_db_pool)):
    where = build_where_clause(filters, extra=("commodity IS NOT NULL",))
    query = f"""
        SELECT
            MAX(commodity_name)                          AS crop,
            commodity                                    AS crop_code,
            COALESCE(SUM(area_sown_ha), 0)::float8       AS area,
            COUNT(DISTINCT farmer_key)::bigint           AS farmers
        FROM cs_rpt_sowing
        {where.sql}
        GROUP BY commodity
        ORDER BY area DESC, crop_code
    """
    return await fetch(pool, query, where)


async def area_by_geo_level(pool: asyncpg.Pool, filters: ChartFilters, level: str) -> Rows:
    """Hectares sown per administrative unit at dashboard level `level`.

    The map reads its value from `farmers` whatever the measure is, so the
    hectares are returned under that key and the farmer count as
    `farmer_count`. `<level>_code` is the P-code map boundaries are keyed on.
    `level` comes from the fixed handlers below, never from the request.
    """
    where = build_where_clause(filters)
    name, code = geo.name_column(level), geo.code_column(level)
    query = f"""
        SELECT
            COALESCE(MAX({name}), 'Unknown')                 AS {level},
            COALESCE({code}, 'Unknown')                      AS {level}_code,
            ROUND(COALESCE(SUM(area_sown_ha), 0), 2)::float8 AS farmers,
            COUNT(DISTINCT farmer_key)::bigint               AS farmer_count
        FROM cs_rpt_sowing
        {where.sql}
        GROUP BY {code}, CASE WHEN {code} IS NULL THEN {name} END
        ORDER BY farmers DESC, {level}_code
    """
    return await fetch(pool, query, where)


@router.get("/cropAreaByRegion", response_model=Rows)
async def get_area_by_region(filters: ChartFilters = Depends(), pool: asyncpg.Pool = Depends(get_db_pool)):
    return await area_by_geo_level(pool, filters, "region")


@router.get("/cropAreaByZone", response_model=Rows)
async def get_area_by_zone(filters: ChartFilters = Depends(), pool: asyncpg.Pool = Depends(get_db_pool)):
    return await area_by_geo_level(pool, filters, "zone")


@router.get("/cropAreaByWoreda", response_model=Rows)
async def get_area_by_woreda(filters: ChartFilters = Depends(), pool: asyncpg.Pool = Depends(get_db_pool)):
    return await area_by_geo_level(pool, filters, "woreda")


@router.get("/cropAreaByKebele", response_model=Rows)
async def get_area_by_kebele(filters: ChartFilters = Depends(), pool: asyncpg.Pool = Depends(get_db_pool)):
    return await area_by_geo_level(pool, filters, "kebele")


@router.get("/cropTopWoredas", response_model=Rows)
async def get_top_woredas(filters: ChartFilters = Depends(), pool: asyncpg.Pool = Depends(get_db_pool)):
    where = build_where_clause(filters, extra=("(woreda_code IS NOT NULL OR woreda_name IS NOT NULL)",))
    query = f"""
        SELECT
            MAX(woreda_name)                             AS woreda,
            COALESCE(woreda_code, 'Unknown')             AS woreda_code,
            COALESCE(SUM(area_sown_ha), 0)::float8       AS area,
            COUNT(DISTINCT farmer_key)::bigint           AS farmers
        FROM cs_rpt_sowing
        {where.sql}
        GROUP BY woreda_code, CASE WHEN woreda_code IS NULL THEN woreda_name END
        HAVING COALESCE(SUM(area_sown_ha), 0) > 0
        ORDER BY area DESC, woreda_code
        LIMIT 8
    """
    return await fetch(pool, query, where)


@router.get("/cropLandTenureSplit", response_model=Rows)
async def get_land_tenure_split(filters: ChartFilters = Depends(), pool: asyncpg.Pool = Depends(get_db_pool)):
    # Ownership is the plot's, taken from its cultivation record; a sowing line
    # without one yet is reported as UNKNOWN.
    where = build_where_clause(filters)
    query = f"""
        SELECT
            COALESCE(MAX(ownership_type_name), 'Unknown')  AS ownership_type,
            COALESCE(ownership_type, 'UNKNOWN')            AS ownership_type_code,
            COUNT(*)::bigint                               AS parcels,
            COALESCE(SUM(area_sown_ha), 0)::float8         AS area
        FROM cs_rpt_sowing
        {where.sql}
        GROUP BY ownership_type
        ORDER BY parcels DESC, ownership_type_code
    """
    return await fetch(pool, query, where)


@router.get("/cropBySeason", response_model=Rows)
async def get_crop_by_season(filters: ChartFilters = Depends(), pool: asyncpg.Pool = Depends(get_db_pool)):
    where = build_where_clause(filters)
    query = f"""
        SELECT
            COALESCE(MAX(season_name), 'Unknown')        AS season,
            COALESCE(season, 'UNKNOWN')                  AS season_code,
            COALESCE(SUM(area_sown_ha), 0)::float8       AS area,
            COUNT(DISTINCT farmer_key)::bigint           AS farmers
        FROM cs_rpt_sowing
        {where.sql}
        GROUP BY season
        ORDER BY area DESC, season_code
    """
    return await fetch(pool, query, where)


@router.get("/cropTrendByMonth", response_model=Rows)
async def get_trend_by_month(filters: ChartFilters = Depends(), pool: asyncpg.Pool = Depends(get_db_pool)):
    # By sowing date; a line not sown yet falls back to its registration date.
    where = build_where_clause(filters, extra=("recorded_on IS NOT NULL",))
    query = f"""
        SELECT
            TO_CHAR(DATE_TRUNC('month', recorded_on), 'YYYY-MM')              AS period,
            COUNT(DISTINCT farmer_key)::bigint                                AS farmers,
            COALESCE(SUM(area_sown_ha), 0)::float8                            AS total_area,
            COALESCE(SUM(area_sown_ha) FILTER (WHERE is_owned), 0)::float8    AS owned_area
        FROM cs_rpt_sowing
        {where.sql}
        GROUP BY 1
        ORDER BY 1
    """
    return await fetch(pool, query, where)


async def registrations_by(
    pool: asyncpg.Pool, filters: ChartFilters, column: str, key: str, default_active: bool = True
) -> Rows:
    """Registrations per value of a crop_sown column. `column` and `key` are fixed literals."""
    where = build_where_clause(filters, view="crop_sown", default_active=default_active)
    query = f"""
        SELECT COALESCE({column}, 'UNKNOWN') AS {key}, COUNT(*)::bigint AS registrations
        FROM cs_rpt_crop_sown
        {where.sql}
        GROUP BY 1
        ORDER BY registrations DESC, 1
    """
    return await fetch(pool, query, where)


@router.get("/cropByStatus", response_model=Rows)
async def get_crop_by_status(filters: ChartFilters = Depends(), pool: asyncpg.Pool = Depends(get_db_pool)):
    # Approval-workflow status (APPROVAL_STATUS_DRAFT .. APPROVAL_STATUS_APPROVED).
    return await registrations_by(pool, filters, "status", "status")


@router.get("/cropByLifecycleStage", response_model=Rows)
async def get_crop_by_lifecycle_stage(filters: ChartFilters = Depends(), pool: asyncpg.Pool = Depends(get_db_pool)):
    # PENDING_PLANNING, PLANNING_APPROVED, ..., HARVESTING_APPROVED.
    return await registrations_by(pool, filters, "lifecycle_stage", "lifecycle_stage")


@router.get("/cropByRecordState", response_model=Rows)
async def get_crop_by_record_state(filters: ChartFilters = Depends(), pool: asyncpg.Pool = Depends(get_db_pool)):
    # A breakdown by status must see every status, so no ACTIVE default here.
    return await registrations_by(pool, filters, "record_status", "record_state", default_active=False)
