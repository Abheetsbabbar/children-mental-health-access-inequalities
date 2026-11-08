"""Data-contract tests on the committed processed outputs.

These encode what we *know must be true* of the data (grain, ranges, totals),
so a future refresh that breaks an assumption fails CI instead of silently
producing a wrong chart. The same idea as automated regression testing, applied to data.
"""

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pandera.pandas as pa
import pytest
from pandera import Check, Column

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"

SUB_ICB_SCHEMA = pa.DataFrameSchema(
    {
        "sub_icb_code": Column(str, unique=True, nullable=False, checks=Check.str_matches(r"^[0-9A-Z]{3,5}$")),
        "icb_code": Column(str, nullable=False),
        "region_name": Column(str, Check.isin([
            "North East and Yorkshire", "North West", "Midlands", "East of England",
            "London", "South East", "South West"])),
        "pop_u18_est": Column(float, Check.in_range(5_000, 1_000_000)),
        "imd_score": Column(float, Check.in_range(0, 100)),
        "idaci_score": Column(float, Check.in_range(0, 1)),
        "pct_children_core20": Column(float, Check.in_range(0, 1)),
        "pct_pop_rural": Column(float, Check.in_range(0, 1)),
        "cyp_accessed_12m": Column(float, Check.ge(0)),
        # plausibility: between 1% and 30% of under-18s seen in a year
        "access_rate_per_100k": Column(float, Check.in_range(1_000, 30_000)),
        "median_wait_first_contact_days": Column(float, Check.in_range(0, 3_650), nullable=True),
        "median_wait_still_waiting_days": Column(float, Check.in_range(0, 3_650), nullable=True),
        "pct_clock_stops_within_4w": Column(float, Check.in_range(0, 100), nullable=True),
        "idaci_quintile": Column(int, Check.isin([1, 2, 3, 4, 5])),
    },
    checks=[
        # median <= 90th percentile wherever both are published
        Check(lambda d: (d.median_wait_still_waiting_days <= d.p90_wait_still_waiting_days).all(),
              name="median_le_p90"),
        Check(lambda d: (d.clock_stops_within_4w_3m.fillna(0) <= d.clock_stops_3m).all(),
              name="numerator_le_denominator"),
    ],
    coerce=True,
)


@pytest.fixture(scope="module")
def sub():
    return pd.read_parquet(PROCESSED / "mart_sub_icb_scored.parquet")


@pytest.fixture(scope="module")
def results():
    return json.loads((ROOT / "reports" / "results.json").read_text())


def test_sub_icb_schema(sub):
    SUB_ICB_SCHEMA.validate(sub, lazy=True)


def test_complete_national_coverage(sub):
    # England has 106 Sub-ICB locations from April 2026 (ONS SICBL26)
    assert len(sub) == 106
    assert sub.icb_code.nunique() == 36


def test_population_reconciles_to_england(sub):
    # IoD 2025 0-15 mid-2022 population for England is ~10.4m; all LSOAs must be allocated
    assert sub.pop_0_15.sum() == pytest.approx(10.4e6, rel=0.03)


def test_sub_icb_totals_reconcile_with_england(results):
    # Sub-ICB counts are rounded to the nearest 5 for disclosure control and some
    # children have no recorded residence, so allow +/-2%.
    assert results["reconciliation"]["coverage_pct"] == pytest.approx(100, abs=2)


def test_boundaries_match_data(sub):
    geo = gpd.read_file(PROCESSED / "sub_icb_2026.geojson")
    assert set(geo.sub_icb_code) == set(sub.sub_icb_code)
    assert geo.geometry.is_valid.all()
    assert geo.crs.to_epsg() == 4326


def test_england_equity_has_expected_breakdowns():
    eng = pd.read_parquet(PROCESSED / "mart_england_equity.parquet")
    expected = {"England", "England; IMD Quintile", "England; Upper Ethnicity", "England; IMD Core20",
                "England; Pathway"}
    assert expected <= set(eng.breakdown)
    # one value per (breakdown, group, measure): the period-window de-duplication worked
    assert not eng.duplicated(["breakdown", "group_name", "measure_id"]).any()
