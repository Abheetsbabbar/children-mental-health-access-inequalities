# Data dictionary

## `data/processed/mart_sub_icb_scored.parquet` (and `mart_sub_icb.parquet`)

**Grain:** one row per 2026 Sub-ICB location (106 rows). This is the main analysis table.

| Column | Type | Definition | Source |
|---|---|---|---|
| `sub_icb_code` | str | ODS code of the Sub-ICB location, e.g. `00R` (primary key) | ONS lookup / MHSDS |
| `sub_icb_name` | str | Sub-ICB name | ONS lookup |
| `icb_code`, `icb_name` | str | Integrated Care Board as configured from April 2026 (36 ICBs) | ONS lookup |
| `region_name` | str | NHS England commissioning region (7) | ONS lookup |
| `n_lsoas` | int | Number of LSOA 2021 neighbourhoods in the area | derived |
| `pop_total` | float | Total population, mid-2022 | IoD 2025 File 7 |
| `pop_0_15` | float | Population aged 0–15, mid-2022 | IoD 2025 File 7 |
| `pop_u18_est` | float | **Estimated** population aged 0–17. Calculated as `pop_0_15` × the ICB's (under-18 ÷ 0–15) ratio, where the ICB under-18 population is implied by the published crude rate (`MHS95 / MHS95a × 100,000`) | derived |
| `imd_score` | float | Population-weighted mean IMD 2025 score (higher = more deprived) | IoD 2025 |
| `idaci_score` | float | Income Deprivation Affecting Children Index, weighted by 0–15 population: share of children living in income-deprived families (0–1) | IoD 2025 |
| `pct_children_core20` | float | Share of children (0–15) living in England's most deprived 20% of LSOAs | IoD 2025 |
| `pct_pop_rural` | float | Share of population living in LSOAs classed as rural (RUC 2021 `R*`) | ONS |
| `cyp_accessed_12m` | float | **MHS95**: children and young people aged under 18 supported through NHS-funded mental health services with at least one contact, rolling 12 months to Aug 2026 | MHSDS |
| `access_rate_per_100k` | float | `cyp_accessed_12m / pop_u18_est × 100,000` | derived |
| `referrals_first_contact_3m` | float | **MHS130**: referrals with a first contact, Jun–Aug 2026 | MHSDS |
| `median_wait_first_contact_days` | float | **MHS131**: median days from referral to first contact, for referrals that **had** a first contact | MHSDS |
| `p90_wait_first_contact_days` | float | **MHS132**: 90th percentile of the same | MHSDS |
| `still_waiting_count` | float | **MHS133**: referrals still waiting for a first contact at period end | MHSDS |
| `median_wait_still_waiting_days` | float | **MHS134**: median days waited so far by referrals **still waiting** (the live waiting list) | MHSDS |
| `p90_wait_still_waiting_days` | float | **MHS135**: 90th percentile of the same | MHSDS |
| `clock_stops_3m` | float | **MRS08**: CYP referral-spells receiving a full "clock stop" (first meaningful help), Jun–Aug 2026 | MHSDS 4WW |
| `clock_stops_within_4w_3m` | float | **MRS08a**: of those, clock stop in under 4 weeks (suppressed in 6 small areas) | MHSDS 4WW |
| `pct_clock_stops_within_4w` | float | **MRS08b**: % of clock stops within 4 weeks | MHSDS 4WW |
| `open_waiting_first_contact` | float | **MRS10**: open CYP referral-spells waiting for a first contact at 31 Aug 2026 | MHSDS 4WW |
| `median_open_wait_days` | float | **MRS10a**: median days waited by those open spells | MHSDS 4WW |
| `idaci_quintile` | int | Quintile of `idaci_score` across the 106 areas (1 = most deprived) | derived |
| `funnel_class` | str | Funnel-plot position of `access_rate_per_100k` compared with England, after adjusting for over-dispersion | derived (`analysis.py`) |

## `data/processed/mart_england_equity.parquet`

**Grain:** one row per (`breakdown`, `group_name`, `measure_id`). This is NHS England's
national equity breakdown, kept in long format.

| Column | Definition |
|---|---|
| `breakdown` | e.g. `England`, `England; IMD Quintile`, `England; Upper Ethnicity`, `England; IMD Core20`, `England; Pathway` |
| `group_name` | The group within the breakdown, e.g. `01 Most deprived`, `Black or Black British` |
| `measure_id` | `MHS95`, `MHS95a` (crude rate), `MHS95b` (age-standardised rate), `MHS95c` (± 95% CI of MHS95b), `MRS08*`, `MRS10*` |
| `value` | Numeric value |

The **pathway** groups overlap: a referral-spell that contains both an autism
referral and an "other" referral counts in both groups. Do not add the pathway
groups together.

## `data/processed/sub_icb_2026.geojson`

There is one simplified polygon per Sub-ICB location, in WGS84 (EPSG:4326). ONS had
not yet published generalised boundaries for the April 2026 Sub-ICB configuration.
These polygons are built by dissolving the 33,755 LSOA 2021 polygons using the ONS
2026 lookup.

## `reports/results.json`

This file holds every number quoted in the README, produced by `analysis.py`:
headline figures, the reconciliation check, funnel over-dispersion (`phi`), the Slope
Index of Inequality, negative-binomial incidence-rate ratios, Spearman correlations
with bootstrap CIs, ethnicity rate ratios, the four-week two-proportion test and
waits by pathway.
