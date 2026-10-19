from dataclasses import dataclass, field
from typing import Literal

from fastapi import Query

from app.core import geo

# The reporting view a chart reads: one row per registration, or per sowing line.
View = Literal["crop_sown", "sowing"]


def _given(value: str | None) -> bool:
    return bool(value) and value != "all"


class ChartFilters:
    """Query parameters shared by every chart endpoint."""

    def __init__(
        self,
        region: str | None = Query(None),
        zone: str | None = Query(None),
        woreda: str | None = Query(None),
        kebele: str | None = Query(None),
        recordState: str | None = Query(None),
        status: str | None = Query(None),
        season: str | None = Query(None),
        cropYear: str | None = Query(None),
        commodity: str | None = Query(None),
    ):
        self.region = region
        self.zone = zone
        self.woreda = woreda
        self.kebele = kebele
        self.recordState = recordState
        self.status = status
        self.season = season
        self.cropYear = cropYear
        self.commodity = commodity


@dataclass
class Where:
    """A WHERE clause and its bind values. `sql` is empty when nothing applies."""

    sql: str
    values: list = field(default_factory=list)


def _lookup_match(column: str, key_prefix: str, placeholder: str, label: str | None = None) -> str:
    """A lookup value asked for by its key (CROP_SEASON_MEHER), the key's last
    part (MEHER) or, when the view carries one, its label (Meher)."""
    match = (
        f"(UPPER({column}) = UPPER({placeholder})"
        f" OR UPPER(regexp_replace({column}, '^{key_prefix}', '')) = UPPER({placeholder})"
    )
    if label:
        match += f" OR UPPER({label}) = UPPER({placeholder})"
    return match + ")"


def build_where_clause(
    filters: ChartFilters,
    view: View = "sowing",
    extra: tuple[str, ...] = (),
    default_active: bool = True,
    alias: str = "",
) -> Where:
    """Build a parameterised WHERE clause for a reporting view.

    Only literal column names are interpolated; every filter value is bound as
    $n. `extra` holds fixed predicates (no user input) that must be ANDed in, so
    callers never concatenate onto the clause themselves: an empty clause plus
    "AND ..." is invalid SQL.

    Without an explicit recordState, only ACTIVE records are counted (on the
    sowing view, ACTIVE lines of ACTIVE registrations). Pass default_active=False
    for charts that break down by status.
    """
    prefix = f"{alias}." if alias else ""
    conditions: list[str] = []
    values: list = []

    def bind(value) -> str:
        values.append(value)
        return f"${len(values)}"

    for level in geo.LEVELS:
        value = getattr(filters, level)
        if _given(value):
            conditions.append(f"{prefix}{geo.code_column(level)} = {bind(geo.code(value))}")

    if _given(filters.status):
        conditions.append(_lookup_match(f"{prefix}status", "APPROVAL_STATUS_", bind(filters.status)))

    if _given(filters.season):
        conditions.append(_lookup_match(f"{prefix}production_season", "CROP_SEASON_", bind(filters.season)))

    if _given(filters.cropYear):
        conditions.append(f"{prefix}crop_year = {bind(filters.cropYear)}")

    if _given(filters.commodity):
        p = bind(filters.commodity)
        if view == "sowing":
            conditions.append(_lookup_match(f"{prefix}commodity", "CROP_COMMODITY_", p, f"{prefix}commodity_name"))
        else:
            # A registration matches when one of its live sowing lines is of the crop.
            conditions.append(
                f"{prefix}crop_sown_id IN (SELECT ss.crop_sown_id FROM cs_rpt_sowing ss"
                f" WHERE ss.record_status = 'ACTIVE'"
                f" AND {_lookup_match('ss.commodity', 'CROP_COMMODITY_', p, 'ss.commodity_name')})"
            )

    if _given(filters.recordState):
        conditions.append(f"LOWER({prefix}record_status) = LOWER({bind(filters.recordState)})")
    elif default_active:
        conditions.append(f"{prefix}record_status = 'ACTIVE'")
        if view == "sowing":
            conditions.append(f"{prefix}crop_sown_record_status = 'ACTIVE'")

    conditions.extend(extra)

    if not conditions:
        return Where("")
    return Where("WHERE " + " AND ".join(conditions), values)
