# Methodology

## 1. Pipeline architecture

```
 NHS England MHSDS (CSV, ~200 MB)  ─┐
 MHCLG IoD 2025 (LSOA CSV)          ├─► download.py ─► data/raw/ (git-ignored)
 ONS lookup + boundaries (ArcGIS)  ─┘                       │
                                                            ▼
                         build.py ── DuckDB ── sql/01_staging.sql   (type, trim, de-duplicate)
                                          └── sql/02_marts.sql      (aggregate LSOA→Sub-ICB, pivot, join)
                                                            │
                                   data/processed/*.parquet + sub_icb_2026.geojson (committed)
                                                            │
                     analysis.py (stats.py) ─► reports/figures/*.png + reports/results.json
                                                            │
                                     app/streamlit_app.py (interactive dashboard)
```

The pipeline is split into **staging** and **mart** layers, the same layering
dbt uses. Staging tables are a cleaned 1:1 copy of each source. Marts are joined,
analysis-ready tables at a declared grain. SQL does the data shaping; Python does
the statistics and visualisation.

## 2. Data engineering decisions

| Issue found in the raw data | Handling |
|---|---|
| Trailing whitespace in `STATUS` and `BREAKDOWN` in the four-week-wait file (`"Performance "`) | `trim()` every text column in staging |
| Disclosure control: small counts published as `*` | `try_cast` to NULL and keep an `is_suppressed` flag. Nothing is imputed |
| `MRS08` published for **both** a 12-month and a 3-month window in the same file, so a naive pivot double-counts | The grain includes `period_start`. Staging keeps the latest window per measure (`qualify … max(period_start)`). A test asserts there are no duplicates at (breakdown, group, measure) |
| April 2026 ICB mergers (42 → 36 ICBs; four Sub-ICBs in Surrey, Sussex and Hampshire redrawn). Older ICB-level public-health data no longer lines up | Everything is rebuilt bottom-up from **LSOA 2021** neighbourhoods using the ONS April 2026 lookup, so deprivation and population are exact for the new areas |
| No published generalised boundaries for 2026 Sub-ICBs | LSOA polygons dissolved in British National Grid. Invalid geometries repaired (`make_valid`). Slivers closed with a ±120 m buffer. Holes under 5 km² removed. Simplified to 250 m |
| No under-18 population at Sub-ICB level in the inputs | Under-18 population estimated by scaling the LSOA 0–15 population by each ICB's (under-18 ÷ 0–15) ratio. The ICB under-18 figure is implied by NHS England's published crude rate (MHS95 ÷ MHS95a) |

**Reconciliation (QA):** the Sub-ICB MHS95 counts add up to **100.3%** of the
England total. The small excess is expected, because area counts are rounded to the
nearest 5 and children with unknown residence go to `UNKNOWN`. The 0–15 population
across all Sub-ICBs equals the England total (each LSOA is allocated exactly once).
Both are enforced as tests in `tests/test_data_contracts.py`.

## 3. Statistical methods

### 3.1 Funnel plot with over-dispersion adjustment
A league table ranks areas even when their differences are just noise. A **funnel
plot** compares each area's rate with the England rate, using control limits that
narrow as population grows:

$$ \text{limits} = r_0 \pm z \sqrt{\frac{r_0 \cdot 100{,}000}{n}\,\phi} $$

with z = 1.96 (95%) and z = 3.09 (99.8%). Large administrative areas almost always
vary more than pure Poisson chance allows, because of service models, recording
practice and case-mix. Following Spiegelhalter (2005), the over-dispersion factor φ
is the mean of squared **winsorised** z-scores (10%/90%). Here **φ ≈ 281**: the
between-area variation is far larger than chance. Without the adjustment, almost
every area would be flagged. With it, 11 of 106 areas fall outside the 95% limits.

### 3.2 Slope Index of Inequality (SII) and Relative Index (RII)
Areas (or quintiles) are ranked from least to most deprived. Each is given the
midpoint of its cumulative population share, a "ridit" score from 0 to 1. A
population-weighted least-squares regression of the rate on this rank gives the
**SII**: the modelled gap between the most and least deprived ends of the
population. **RII** = SII ÷ mean rate. This is the standard measure in the OHID
Fingertips and NHS England inequality frameworks. Unlike a top-versus-bottom
comparison, it uses the whole distribution.

### 3.3 Negative-binomial regression with a population offset
Area counts of children seen (`MHS95`) are modelled as

$$ \log E[y_i] = \log(\text{pop}_i) + \beta_0 + \beta_1 z(\text{IDACI}_i) + \beta_2 z(\text{rural}_i) $$

using a **negative-binomial** rather than Poisson likelihood, because counts are
over-dispersed (estimated α ≈ 0.05). Predictors are standardised, so
exp(β) is an **incidence-rate ratio per standard deviation**.

### 3.4 Other tests
- **Spearman rank correlation with a bootstrap 95% CI** (5,000 resamples). Used for
  deprivation against waiting time, which is skewed and non-linear.
- **Two-proportion z-test** (Wald CI for the difference). Used for the four-week
  standard in the most deprived quintile against the rest.
- **Rate ratios with log-normal CIs** for age-standardised access by ethnic group
  and by IMD quintile.

## 4. Visualisation conventions

- One palette across all figures: sequential blue for magnitude, orange for waits,
  and grey for "within expected variation".
- Choropleths use **quantile** bands, so the colour scale isn't dominated by one
  extreme area.
- Every figure carries a source line. The dashboard includes a full data table and a
  CSV download, so no value is shown by colour alone.

## 5. Testing strategy

| Test file | What it protects |
|---|---|
| `tests/test_stats.py` | Known-answer tests: funnel limits, φ ≈ 1 on simulated Poisson data, SII recovers a planted gradient, NB recovers a planted rate ratio |
| `tests/test_data_contracts.py` | **pandera** schema (types, ranges, uniqueness), 106 areas / 36 ICBs, population and count reconciliation, geometry validity, no duplicate measures |
| `tests/test_app.py` | Streamlit `AppTest`: the dashboard renders, and the region filter works without exceptions |

CI (GitHub Actions) runs lint and all tests on every push.

## References
- Spiegelhalter D. (2005). *Funnel plots for comparing institutional performance.* Statistics in Medicine 24:1185–1202.
- Spiegelhalter D. et al. (2012). *Statistical methods for healthcare regulation: rating, screening and surveillance.* JRSS A 175:1–47.
- Office for Health Improvement and Disparities. *Slope index of inequality (SII) – Fingertips technical guidance.*
- NHS England. *Mental Health Services Monthly Statistics – metadata and measure definitions.*
- MHCLG (2025). *English Indices of Deprivation 2025: technical report.*
