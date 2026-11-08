# Data sources and licensing

Every input is official, openly licensed and **aggregate**. No patient-level or
personally identifiable data is used, downloaded or stored at any point.

| # | Dataset | Publisher | Used for | Granularity | Period | Licence |
|---|---|---|---|---|---|---|
| 1 | [Mental Health Services Monthly Statistics, Performance August 2026](https://digital.nhs.uk/data-and-information/publications/statistical/mental-health-services-monthly-statistics/performance-august-2026) – main data file (`MHSDS Data_AugPerf_2026.zip`) | NHS England | Children's access metric (MHS95), waits to first contact (MHS130–135), equity breakdowns | Sub-ICB, ICB, region, England; England by IMD, ethnicity, age, gender | 12 months to 31 Aug 2026 (MHS95); Jun–Aug 2026 (waits) | OGL v3.0 |
| 2 | Same publication – four-week-wait file (`MHSDS Data_4WW_AugPerf_2026.zip`) | NHS England | % of children helped within 4 weeks (MRS08–08b), open waiting list (MRS10–10b), referral pathway | Sub-ICB, ICB, England by IMD Core20 and pathway | Jun–Aug 2026; snapshot at 31 Aug 2026 | OGL v3.0 |
| 3 | [English Indices of Deprivation 2025](https://www.gov.uk/government/statistics/english-indices-of-deprivation-2025) – File 7 | Ministry of Housing, Communities & Local Government | IMD score/decile, IDACI (child income deprivation), 0–15 population | LSOA 2021 (33,755 neighbourhoods) | Indicators mostly 2022–23; population mid-2022 | OGL v3.0 |
| 4 | [LSOA (2021) to Sub-ICB Location to ICB to NHS England Region to LAD (April 2026) lookup](https://geoportal.statistics.gov.uk/) (`LSOA21_SICBL26_ICB26_NHSER26_LAD26`) | Office for National Statistics | Allocating every LSOA to its April 2026 Sub-ICB, ICB and region | LSOA 2021 | April 2026 | OGL v3.0 |
| 5 | [LSOA (Dec 2021) boundaries EW BSC V4 with RUC 2021](https://geoportal.statistics.gov.uk/) (`LSOA_2021_EW_BSC_V4_RUC`) | Office for National Statistics | Map polygons (dissolved to Sub-ICB); rural–urban classification | LSOA 2021 | 2021 | OGL v3.0; contains OS data |

All five are downloaded by `python -m access_inequalities.download` from the URLs in
[`src/access_inequalities/config.py`](../src/access_inequalities/config.py). Files are cached in
`data/raw/`, which git ignores.

## Required attribution

- Copyright © 2026, NHS England. Licensed under the Open Government Licence v3.0.
- Contains public sector information licensed under the Open Government Licence v3.0 (MHCLG).
- Source: Office for National Statistics, licensed under the Open Government Licence v3.0.
- Contains OS data © Crown copyright and database right 2026.

## Status of the NHS figures

The August 2026 MHSDS release is **Performance** data, not Final data. Providers can
resubmit, and later releases may revise these figures slightly. Small counts are
**suppressed** (published as `*`) and other counts are **rounded to the nearest 5**
for disclosure control. See NHS England's
[data quality statement](https://digital.nhs.uk/data-and-information/publications/statistical/mental-health-services-monthly-statistics)
for provider coverage and known data-quality issues.

## Independence

This is an independent portfolio project built on public data. It is not produced,
endorsed or quality-assured by NHS England, OHID or any NHS organisation.
