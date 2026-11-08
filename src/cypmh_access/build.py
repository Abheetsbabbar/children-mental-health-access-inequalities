"""Build the DuckDB warehouse (staging -> marts) and export analysis-ready files.

Run:  python -m cypmh_access.build
Outputs (committed to the repo so the dashboard runs without the 200 MB raw download):
    data/processed/mart_sub_icb.parquet
    data/processed/mart_england_equity.parquet
    data/processed/sub_icb_2026.geojson
"""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path

import duckdb
import geopandas as gpd

from . import config

log = logging.getLogger(__name__)

MEASURES = list(config.ACCESS_MEASURES) + list(config.FOUR_WEEK_WAIT_MEASURES)


def _extract_csv(zip_path: Path) -> Path:
    out_dir = config.RAW / "extracted"
    out_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        target = out_dir / Path(name).name
        if not target.exists():
            log.info("extract %s", name)
            with zf.open(name) as src, open(target, "wb") as dst:
                dst.write(src.read())
    return target


def _render(sql_file: Path, **params) -> str:
    return sql_file.read_text().format(**params)


def build_warehouse() -> duckdb.DuckDBPyConnection:
    lsoa = gpd.read_file(config.RAW_FILES["lsoa_boundaries"])
    ruc_frame = lsoa[["LSOA21CD", "RUC21CD", "RUC21NM"]].rename(columns=str.lower)  # noqa: F841 (used by SQL)

    con = duckdb.connect(str(config.DB_PATH))
    con.register("ruc_frame", ruc_frame)
    params = dict(
        mhsds_main_csv=_extract_csv(config.RAW_FILES["mhsds_main"]),
        mhsds_4ww_csv=_extract_csv(config.RAW_FILES["mhsds_4ww"]),
        iod_csv=config.RAW_FILES["iod"],
        lsoa_lookup_csv=config.RAW_FILES["lsoa_lookup"],
        measure_ids=", ".join(f"'{m}'" for m in MEASURES),
        sub_icb_breakdown=config.SUB_ICB_BREAKDOWN,
        icb_breakdown=config.ICB_BREAKDOWN,
    )
    for sql_file in sorted(config.SQL_DIR.glob("*.sql")):
        log.info("run %s", sql_file.name)
        con.execute(_render(sql_file, **params))
    return con


def _drop_small_holes(geom, min_area_m2: float = 5e6):
    """Remove interior rings (holes) smaller than ~5 km2 left over from generalisation gaps."""
    from shapely.geometry import MultiPolygon, Polygon

    def fix(poly: Polygon) -> Polygon:
        keep = [r for r in poly.interiors if Polygon(r).area >= min_area_m2]
        return Polygon(poly.exterior, keep)

    if geom.geom_type == "Polygon":
        return fix(geom)
    if geom.geom_type == "MultiPolygon":
        return MultiPolygon([fix(p) for p in geom.geoms])
    return geom


def build_boundaries(con: duckdb.DuckDBPyConnection) -> None:
    """Dissolve LSOA polygons into 2026 Sub-ICB areas.

    ONS has not yet published generalised boundaries for the April 2026 Sub-ICB
    configuration (four areas in Surrey/Sussex/Hampshire changed), so we build
    them from their LSOA building blocks.
    """
    lsoa = gpd.read_file(config.RAW_FILES["lsoa_boundaries"])
    lookup = con.sql("select lsoa21cd as LSOA21CD, sub_icb_code from stg_lsoa_lookup").df()
    # Work in British National Grid (metres). Server-side generalisation can produce
    # self-intersections, so repair geometries and snap to a 1 m grid before dissolving.
    merged = lsoa.merge(lookup, on="LSOA21CD", how="inner").to_crs(27700)
    merged["geometry"] = merged.make_valid().buffer(120)  # close slivers between generalised LSOAs
    sub_icb = merged.dissolve(by="sub_icb_code", as_index=False, grid_size=1)[["sub_icb_code", "geometry"]]
    sub_icb["geometry"] = sub_icb.buffer(-120).apply(_drop_small_holes).simplify(250)
    sub_icb = sub_icb.to_crs(4326)
    sub_icb.to_file(config.PROCESSED / "sub_icb_2026.geojson", driver="GeoJSON")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    con = build_warehouse()
    for table in ("mart_sub_icb", "mart_england_equity"):
        out = config.PROCESSED / f"{table}.parquet"
        con.execute(f"copy {table} to '{out}' (format parquet)").fetchall()
        n_rows = con.execute(f"select count(*) from {table}").fetchall()[0][0]
        log.info("wrote %s (%d rows)", out.name, n_rows)
    build_boundaries(con)
    con.close()


if __name__ == "__main__":
    main()
