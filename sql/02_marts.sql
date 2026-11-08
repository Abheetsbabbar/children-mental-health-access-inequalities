-- =====================================================================
-- MART LAYER: analysis-ready tables at Sub-ICB and ICB level.
-- =====================================================================

-- 1) Area profile built bottom-up from ~33,700 LSOAs.
--    Deprivation is population-weighted: IMD by total population,
--    IDACI (child poverty) by the 0-15 population it describes.
create or replace table dim_sub_icb as
select
    l.sub_icb_code,
    any_value(l.sub_icb_name)                                   as sub_icb_name,
    any_value(l.icb_code)                                       as icb_code,
    any_value(l.icb_name)                                       as icb_name,
    any_value(l.region_name)                                    as region_name,
    count(*)                                                    as n_lsoas,
    sum(i.pop_total)                                            as pop_total,
    sum(i.pop_0_15)                                             as pop_0_15,
    sum(i.imd_score * i.pop_total) / sum(i.pop_total)           as imd_score,
    sum(i.idaci_score * i.pop_0_15) / sum(i.pop_0_15)           as idaci_score,
    -- share of children living in England's most deprived 20% of neighbourhoods ("Core20")
    sum(case when i.imd_decile <= 2 then i.pop_0_15 else 0 end) / sum(i.pop_0_15) as pct_children_core20,
    sum(case when r.is_rural then i.pop_total else 0 end) / sum(i.pop_total)        as pct_pop_rural
from stg_lsoa_lookup l
join stg_iod i using (lsoa21cd)
left join stg_ruc r using (lsoa21cd)
group by l.sub_icb_code;


-- 2) Long -> wide pivot of the MHSDS measures we need, per Sub-ICB
create or replace table fct_sub_icb_measures as
pivot (
    select area_code as sub_icb_code, measure_id, value
    from stg_mhsds
    where breakdown = '{sub_icb_breakdown}'
      and area_code <> 'UNKNOWN'
)
on measure_id in ({measure_ids})
using first(value);


-- 3) ICB under-18 population implied by the published crude access rate
--    (MHS95a = MHS95 / population_u18 * 100,000). Used to calibrate a
--    Sub-ICB under-18 population from the LSOA 0-15 population.
create or replace table icb_u18_population as
with icb as (
    pivot (
        select area_code as icb_code, measure_id, value
        from stg_mhsds
        where breakdown = '{icb_breakdown}' and measure_id in ('MHS95', 'MHS95a')
    ) on measure_id using first(value)
)
select icb_code, MHS95 / MHS95a * 100000 as pop_u18_icb
from icb
where MHS95a > 0;


-- 4) Final analysis mart
create or replace table mart_sub_icb as
with d as (
    select
        d.*,
        u.pop_u18_icb,
        u.pop_u18_icb / sum(d.pop_0_15) over (partition by d.icb_code) as u18_to_0_15_ratio
    from dim_sub_icb d
    left join icb_u18_population u using (icb_code)
)
select
    d.sub_icb_code, d.sub_icb_name, d.icb_code, d.icb_name, d.region_name,
    d.n_lsoas, d.pop_total, d.pop_0_15,
    round(d.pop_0_15 * d.u18_to_0_15_ratio)                    as pop_u18_est,
    d.imd_score, d.idaci_score, d.pct_children_core20, d.pct_pop_rural,
    m.MHS95                                                     as cyp_accessed_12m,
    m.MHS95 / (d.pop_0_15 * d.u18_to_0_15_ratio) * 100000       as access_rate_per_100k,
    m.MHS130                                                    as referrals_first_contact_3m,
    m.MHS131                                                    as median_wait_first_contact_days,
    m.MHS132                                                    as p90_wait_first_contact_days,
    m.MHS133                                                    as still_waiting_count,
    m.MHS134                                                    as median_wait_still_waiting_days,
    m.MHS135                                                    as p90_wait_still_waiting_days,
    m.MRS08                                                     as clock_stops_3m,
    m.MRS08a                                                    as clock_stops_within_4w_3m,
    m.MRS08b                                                    as pct_clock_stops_within_4w,
    m.MRS10                                                     as open_waiting_first_contact,
    m.MRS10a                                                    as median_open_wait_days,
    ntile(5) over (order by d.idaci_score desc)                 as idaci_quintile  -- 1 = most deprived
from d
join fct_sub_icb_measures m using (sub_icb_code);


-- 5) England-level equity breakdowns published by NHS England
create or replace table mart_england_equity as
select breakdown, area_name as group_name, measure_id, value
from stg_mhsds
where (breakdown like 'England; %' or breakdown = 'England')
  and measure_id in ('MHS95', 'MHS95a', 'MHS95b', 'MHS95c', 'MRS08', 'MRS08a', 'MRS08b', 'MRS10', 'MRS10a', 'MRS10b');
