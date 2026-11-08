"""Central configuration: data source URLs and file locations.

All sources are official, openly licensed (Open Government Licence v3.0) and
contain aggregate statistics only - no patient-level records.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
FIGURES = ROOT / "reports" / "figures"
SQL_DIR = ROOT / "sql"
DB_PATH = RAW / "warehouse.duckdb"

# NHS England - Mental Health Services Monthly Statistics, Performance August 2026
# https://digital.nhs.uk/data-and-information/publications/statistical/mental-health-services-monthly-statistics/performance-august-2026
MHSDS_MAIN_URL = "https://files.digital.nhs.uk/23/69941D/MHSDS%20Data_AugPerf_2026.zip"
MHSDS_4WW_URL = "https://files.digital.nhs.uk/56/8C045D/MHSDS%20Data_4WW_AugPerf_2026.zip"

# MHCLG - English Indices of Deprivation 2025, File 7 (all ranks, scores, deciles, population denominators)
# https://www.gov.uk/government/statistics/english-indices-of-deprivation-2025
IOD_URL = (
    "https://assets.publishing.service.gov.uk/media/691ded56d140bbbaa59a2a7d/"
    "File_7_IoD2025_All_Ranks_Scores_Deciles_Population_Denominators.csv"
)

# ONS Open Geography Portal (ArcGIS REST)
ARCGIS = "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services"
LSOA_LOOKUP_SERVICE = f"{ARCGIS}/LSOA21_SICBL26_ICB26_NHSER26_LAD26/FeatureServer/0/query"
LSOA_BOUNDARY_SERVICE = f"{ARCGIS}/LSOA_2021_EW_BSC_V4_RUC/FeatureServer/0/query"

RAW_FILES = {
    "mhsds_main": RAW / "MHSDS_Data_AugPerf_2026.zip",
    "mhsds_4ww": RAW / "MHSDS_Data_4WW_AugPerf_2026.zip",
    "iod": RAW / "File_7_IoD2025.csv",
    "lsoa_lookup": RAW / "LSOA21_SICBL26_ICB26_NHSER26_LAD26.csv",
    "lsoa_boundaries": RAW / "LSOA21_EN_BSC_RUC.gpkg",
}

SUB_ICB_BREAKDOWN = "Sub ICB of GP Practice or Residence"
ICB_BREAKDOWN = "ICB of GP Practice or Residence"

# Measures used (definitions: MHSDS Monthly Statistics metadata file)
ACCESS_MEASURES = {
    "MHS95": "cyp_accessed_12m",  # CYP <18 with >=1 contact, rolling 12 months (NHS LTP access metric)
    "MHS95a": "cyp_access_crude_rate",  # per 100,000 population aged <18 (ICB level and above)
    "MHS95b": "cyp_access_dsr",  # directly age-standardised rate (England equity breakdowns)
    "MHS95c": "cyp_access_dsr_ci",  # +/- 95% CI of the standardised rate
    "MHS130": "referrals_first_contact_3m",
    "MHS131": "median_wait_first_contact_days",  # referrals that HAD a first contact
    "MHS132": "p90_wait_first_contact_days",
    "MHS133": "still_waiting_count",
    "MHS134": "median_wait_still_waiting_days",  # referrals STILL waiting (live waiting list)
    "MHS135": "p90_wait_still_waiting_days",
}
FOUR_WEEK_WAIT_MEASURES = {
    "MRS08": "clock_stops",
    "MRS08a": "clock_stops_within_4w",
    "MRS08b": "pct_clock_stops_within_4w",
    "MRS10": "open_waiting_first_contact",
    "MRS10a": "median_open_wait_days",
    "MRS10b": "p90_open_wait_days",
}
