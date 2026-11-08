"""Download raw open data into data/raw (idempotent: skips files that already exist).

Run:  python -m access_inequalities.download
"""

from __future__ import annotations

import logging

import geopandas as gpd
import pandas as pd
import requests

from . import config

log = logging.getLogger(__name__)
TIMEOUT = 300


def _fetch(url: str, dest) -> None:
    if dest.exists():
        log.info("cached  %s", dest.name)
        return
    log.info("download %s", url)
    with requests.get(url, stream=True, timeout=TIMEOUT) as r:
        r.raise_for_status()
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
        tmp.rename(dest)


def _arcgis_paged(url: str, params: dict, page: int = 2000) -> list[dict]:
    """Page through an ArcGIS FeatureServer query (server caps each page at 2,000 rows)."""
    rows, offset = [], 0
    while True:
        p = {**params, "resultOffset": offset, "resultRecordCount": page, "f": "json"}
        js = requests.get(url, params=p, timeout=TIMEOUT).json()
        feats = js.get("features", [])
        rows.extend(f["attributes"] for f in feats)
        if not feats or not js.get("exceededTransferLimit"):
            return rows
        offset += len(feats)


def download_lsoa_lookup() -> None:
    dest = config.RAW_FILES["lsoa_lookup"]
    if dest.exists():
        log.info("cached  %s", dest.name)
        return
    rows = _arcgis_paged(
        config.LSOA_LOOKUP_SERVICE,
        {"where": "1=1", "outFields": "*", "returnGeometry": "false"},
    )
    pd.DataFrame(rows).to_csv(dest, index=False)


def download_lsoa_boundaries() -> None:
    """Super-generalised LSOA 2021 boundaries + 2021 rural-urban classification.

    Geometry is simplified server-side (maxAllowableOffset) to keep the download small;
    it is only used to dissolve LSOAs into 2026 Sub-ICB areas for mapping.
    """
    dest = config.RAW_FILES["lsoa_boundaries"]
    if dest.exists():
        log.info("cached  %s", dest.name)
        return
    frames, offset = [], 0
    while True:
        params = {
            "where": "LSOA21CD LIKE 'E%'",
            "outFields": "LSOA21CD,RUC21CD,RUC21NM",
            "outSR": 4326,
            "f": "geojson",
            "resultOffset": offset,
            "resultRecordCount": 2000,
            "maxAllowableOffset": 0.0005,
            "geometryPrecision": 5,
        }
        r = requests.get(config.LSOA_BOUNDARY_SERVICE, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        g = gpd.read_file(r.text)
        if g.empty:
            break
        frames.append(g)
        offset += len(g)
        if len(g) < 2000:
            break
    gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=4326).to_file(dest)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config.RAW.mkdir(parents=True, exist_ok=True)
    _fetch(config.MHSDS_MAIN_URL, config.RAW_FILES["mhsds_main"])
    _fetch(config.MHSDS_4WW_URL, config.RAW_FILES["mhsds_4ww"])
    _fetch(config.IOD_URL, config.RAW_FILES["iod"])
    download_lsoa_lookup()
    download_lsoa_boundaries()


if __name__ == "__main__":
    main()
