from app.api.filters import ChartFilters, build_where_clause

FILTERS = ("region", "zone", "woreda", "kebele", "recordState", "status", "season", "cropYear", "commodity")


def filters(**kwargs) -> ChartFilters:
    params = dict.fromkeys(FILTERS)
    params.update(kwargs)
    return ChartFilters(**params)


def test_no_filters_defaults_to_active_lines_of_active_registrations():
    where = build_where_clause(filters())
    assert where.sql == "WHERE record_status = 'ACTIVE' AND crop_sown_record_status = 'ACTIVE'"
    assert where.values == []


def test_registration_view_defaults_to_active():
    assert build_where_clause(filters(), view="crop_sown").sql == "WHERE record_status = 'ACTIVE'"


def test_no_filters_and_no_default_is_empty():
    assert build_where_clause(filters(), default_active=False).sql == ""


def test_all_is_ignored():
    where = build_where_clause(filters(region="all", commodity="all", season="all"), default_active=False)
    assert where.sql == ""


def test_geography_binds_the_bare_code():
    where = build_where_clause(filters(region="REGION_ET04", kebele="kebele-ET040706888019"))
    assert where.values == ["ET04", "ET040706888019"]
    assert "region_code = $1" in where.sql
    assert "kebele_code = $2" in where.sql


def test_placeholders_are_numbered_in_bind_order():
    where = build_where_clause(
        filters(region="ET04", status="DRAFT", season="MEHER", cropYear="2026", commodity="WHEAT", recordState="x")
    )
    assert where.values == ["ET04", "DRAFT", "MEHER", "2026", "WHEAT", "x"]
    for n in range(1, 7):
        assert f"${n}" in where.sql
    assert "$7" not in where.sql


def test_commodity_on_registrations_is_a_subquery_on_sowings():
    sql = build_where_clause(filters(commodity="WHEAT"), view="crop_sown").sql
    assert "crop_sown_id IN (SELECT ss.crop_sown_id FROM cs_rpt_sowing ss" in sql
    assert "crop_sown_id IN" not in build_where_clause(filters(commodity="WHEAT")).sql


def test_extra_predicates_are_anded_even_without_filters():
    where = build_where_clause(filters(), default_active=False, extra=("x IS NOT NULL",))
    assert where.sql == "WHERE x IS NOT NULL"


def test_alias_prefixes_every_column():
    where = build_where_clause(filters(region="ET04", season="MEHER"), alias="s")
    assert "s.region_code" in where.sql
    assert "s.production_season" in where.sql
    assert "s.record_status = 'ACTIVE'" in where.sql
    assert "s.crop_sown_record_status = 'ACTIVE'" in where.sql


def test_values_never_reach_the_sql_text():
    evil = "ET04' OR 1=1 --"
    where = build_where_clause(
        filters(region=evil, status=evil, season=evil, cropYear=evil, commodity=evil, recordState=evil)
    )
    assert evil not in where.sql
    assert "OR 1=1" not in where.sql
