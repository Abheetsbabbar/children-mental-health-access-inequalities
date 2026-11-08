-- =====================================================================
-- STAGING LAYER: clean, typed, de-duplicated copies of each raw source.
-- Placeholders in curly braces are filled in by build.py (str.format).
-- =====================================================================

-- MHSDS monthly + four-week-wait files share one long ("tidy") schema:
-- one row per (period, breakdown, area, sub-group, measure).
-- Data-quality issues handled here:
--   * STATUS / BREAKDOWN carry trailing whitespace in the 4WW file  -> trim()
--   * small numbers are suppressed as '*' for disclosure control     -> NULL + is_suppressed flag
--   * some measures are published for BOTH a 12-month and a 3-month
--     window in the same file (e.g. MRS08). The true grain therefore
--     includes period_start; we keep the most recent window per measure.
create or replace table stg_mhsds as
with unioned as (
    select 'main' as source_file, * from read_csv('{mhsds_main_csv}', all_varchar = true)
    union all by name
    select '4ww' as source_file, * from read_csv('{mhsds_4ww_csv}', all_varchar = true)
),
typed as (
    select
        source_file,
        strptime(trim(REPORTING_PERIOD_START), '%d/%m/%Y')::date as period_start,
        strptime(trim(REPORTING_PERIOD_END), '%d/%m/%Y')::date   as period_end,
        trim(STATUS)                       as status,
        trim(BREAKDOWN)                    as breakdown,
        trim(PRIMARY_LEVEL)                as area_code,
        trim(PRIMARY_LEVEL_DESCRIPTION)    as area_name,
        trim(SECONDARY_LEVEL)              as sub_group_code,
        trim(SECONDARY_LEVEL_DESCRIPTION)  as sub_group,
        trim(MEASURE_ID)                   as measure_id,
        trim(MEASURE_NAME)                 as measure_name,
        trim(MEASURE_VALUE) = '*'          as is_suppressed,
        try_cast(trim(MEASURE_VALUE) as double) as value
    from unioned
    where trim(MEASURE_ID) in ({measure_ids})
)
select *
from typed
qualify period_start = max(period_start) over (partition by measure_id);


-- Indices of Deprivation 2025 at LSOA (neighbourhood, ~1,500 people) level
create or replace table stg_iod as
select
    "LSOA code (2021)"                                                   as lsoa21cd,
    "Index of Multiple Deprivation (IMD) Score"::double                  as imd_score,
    "Index of Multiple Deprivation (IMD) Decile (where 1 is most deprived 10% of LSOAs)"::int as imd_decile,
    "Income Deprivation Affecting Children Index (IDACI) Score (rate)"::double as idaci_score,
    "Children and Young People Sub-domain Score"::double                 as cyp_education_score,
    "Total population: mid 2022"::double                                 as pop_total,
    "Dependent Children aged 0-15: mid 2022"::double                     as pop_0_15
from read_csv('{iod_csv}', header = true);


-- ONS LSOA 2021 -> Sub-ICB Location 2026 -> ICB 2026 -> NHS region lookup
create or replace table stg_lsoa_lookup as
select distinct
    LSOA21CD   as lsoa21cd,
    SICBL26CDH as sub_icb_code,     -- ODS code, matches MHSDS PRIMARY_LEVEL
    SICBL26NM  as sub_icb_name,
    ICB26CDH   as icb_code,
    ICB26NM    as icb_name,
    NHSER26NM  as region_name,
    LAD26NM    as local_authority
from read_csv('{lsoa_lookup_csv}', all_varchar = true);


-- Rural-urban classification 2021 per LSOA (from the boundary file attributes)
create or replace table stg_ruc as
select lsoa21cd, ruc21cd, ruc21nm, starts_with(ruc21cd, 'R') as is_rural
from ruc_frame;
