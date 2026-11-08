"""Inequality analysis: figures + machine-readable results.

Run:  python -m cypmh_access.analysis
Writes reports/figures/*.png and reports/results.json
"""

from __future__ import annotations

import json
import logging

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import BoundaryNorm, ListedColormap

from . import config, style
from . import stats as st

log = logging.getLogger(__name__)
SOURCE = "Source: NHS England MHSDS Monthly Statistics (Aug 2026, performance); MHCLG English IoD 2025; ONS."
ORANGE_RAMP = ["#fde0d2", "#f9b99c", "#f39268", "#eb6834", "#c4501f", "#963b14"]

PATHWAY_LABELS = {
    "a": "Gender identity",
    "b": "Neurodevelopmental (excl. autism)",
    "c": "Autism (suspected/diagnosed)",
    "d": "Other mental health",
    "e": "Mixed (neurodevelopmental + other)",
}


def load():
    sub = pd.read_parquet(config.PROCESSED / "mart_sub_icb.parquet")
    eng = pd.read_parquet(config.PROCESSED / "mart_england_equity.parquet")
    geo = gpd.read_file(config.PROCESSED / "sub_icb_2026.geojson")
    return sub, eng, geo


def england_value(eng: pd.DataFrame, measure: str) -> float:
    return float(eng.query("breakdown == 'England' and measure_id == @measure")["value"].iloc[0])


def equity_table(eng: pd.DataFrame, breakdown: str) -> pd.DataFrame:
    w = (eng[eng.breakdown == breakdown]
         .pivot_table(index="group_name", columns="measure_id", values="value", aggfunc="first"))
    w = w[(w.get("MHS95b", 0) > 0)]
    w["pop"] = w["MHS95"] / w["MHS95a"] * 100_000
    return w


# --------------------------------------------------------------------------- figures


def fig_funnel(sub: pd.DataFrame, target: float, phi: float) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 5))
    pop = np.linspace(sub.pop_u18_est.min() * 0.9, sub.pop_u18_est.max() * 1.05, 400)
    for z, ls, lab in [(1.96, "--", "95% limits"), (3.09, "-", "99.8% limits")]:
        lo, hi = st.funnel_limits(target, pop, z, phi=phi)
        lo = np.where(lo > 0, lo, np.nan)  # a rate cannot be negative
        ax.plot(pop / 1000, lo, ls, color=style.MUTED, lw=1, label=lab)
        ax.plot(pop / 1000, hi, ls, color=style.MUTED, lw=1)
    ax.axhline(target, color=style.INK_2, lw=1)
    cls = sub["funnel_class"]
    colors = np.where(cls.str.startswith("High"), style.BLUE,
                      np.where(cls.str.startswith("Low"), style.ORANGE, style.NEUTRAL))
    ax.scatter(sub.pop_u18_est / 1000, sub.access_rate_per_100k, s=34, c=colors,
               edgecolor=style.SURFACE, linewidth=1, zorder=3)
    for _, r in sub[sub.funnel_class.str.contains("99.8")].nlargest(3, "access_rate_per_100k").iterrows():
        ax.annotate(r.sub_icb_name.split(" - ")[0].replace("NHS ", "").replace(" ICB", ""),
                    (r.pop_u18_est / 1000, r.access_rate_per_100k), fontsize=7.5, color=style.INK_2,
                    xytext=(6, 2), textcoords="offset points")
    ax.text(pop[-1] / 1000, target, f" England {target:,.0f}", va="bottom", ha="right",
            fontsize=8, color=style.INK_2)
    ax.set_ylim(bottom=0)
    ax.set_xlabel("Estimated population aged under 18 (thousands)")
    ax.set_ylabel("CYP accessing services per 100,000 (12 months)")
    ax.set_title("Children's mental health access varies far beyond chance between areas")
    ax.scatter([], [], c=style.BLUE, s=34, label="Above limits")
    ax.scatter([], [], c=style.ORANGE, s=34, label="Below limits")
    ax.legend(loc="upper right", fontsize=8)
    style.source_note(fig, f"{SOURCE}\nFunnel limits adjusted for over-dispersion (phi = {phi:.1f}). "
                           "106 Sub-ICB locations, 12 months to Aug 2026.")
    fig.savefig(config.FIGURES / "01_funnel_access_rate.png")
    style.close(fig)


def _choropleth(ax, gdf, column, colors, title, fmt):
    vals = gdf[column].dropna()
    bins = np.quantile(vals, np.linspace(0, 1, len(colors) + 1))
    bins[0], bins[-1] = vals.min() - 1e-9, vals.max() + 1e-9
    cmap = ListedColormap(colors)
    norm = BoundaryNorm(bins, cmap.N)
    gdf.plot(column=column, ax=ax, cmap=cmap, norm=norm, edgecolor=style.SURFACE, linewidth=0.3,
             missing_kwds={"color": "#e1e0d9"})
    ax.set_axis_off()
    ax.set_title(title, fontsize=11)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in colors]
    labels = [f"{fmt(bins[i])} – {fmt(bins[i + 1])}" for i in range(len(colors))]
    ax.legend(handles, labels, loc="upper left", fontsize=7, title="Quantile bands", title_fontsize=7)


def fig_maps(sub: pd.DataFrame, geo: gpd.GeoDataFrame) -> None:
    g = geo.merge(sub, on="sub_icb_code", how="left").to_crs(27700)
    fig, axes = plt.subplots(1, 2, figsize=(11, 6.2))
    fig.subplots_adjust(wspace=0.02, top=0.9)
    _choropleth(axes[0], g, "access_rate_per_100k", style.SEQUENTIAL[1:], "Access rate per 100,000 under-18s",
                lambda v: f"{v:,.0f}")
    _choropleth(axes[1], g, "median_wait_still_waiting_days", ORANGE_RAMP,
                "Median days waited by children still waiting", lambda v: f"{v:,.0f}")
    fig.suptitle("Where children get seen - and where they wait", x=0.01, ha="left", fontweight="bold")
    style.source_note(fig, SOURCE + " 2026 Sub-ICB boundaries dissolved from LSOA 2021 (ONS).")
    fig.savefig(config.FIGURES / "02_maps_access_and_waits.png")
    style.close(fig)


def fig_deprivation(sub: pd.DataFrame, nb_model, predictors) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
    ax = axes[0]
    ax.scatter(sub.idaci_score * 100, sub.access_rate_per_100k, s=30, c=style.BLUE,
               edgecolor=style.SURFACE, linewidth=1)
    grid = pd.DataFrame({p: np.repeat(sub[p].mean(), 100) for p in predictors})
    grid["idaci_score"] = np.linspace(sub.idaci_score.min(), sub.idaci_score.max(), 100)
    z = (grid - sub[predictors].mean()) / sub[predictors].std(ddof=0)
    params = nb_model.params
    eta = params["const"] + sum(params[p] * z[p] for p in predictors)
    ax.plot(grid.idaci_score * 100, np.exp(eta) * 100_000, color=style.INK_2, lw=2,
            label="Negative-binomial fit")
    ax.set_xlabel("Child income deprivation (IDACI, % of children)")
    ax.set_ylabel("Access per 100,000 under-18s")
    ax.set_title("Access is higher in more deprived areas")
    ax.legend(fontsize=8, loc="upper left")

    ax = axes[1]
    ax.scatter(sub.idaci_score * 100, sub.median_wait_still_waiting_days, s=30, c=style.ORANGE,
               edgecolor=style.SURFACE, linewidth=1)
    ax.set_xlabel("Child income deprivation (IDACI, % of children)")
    ax.set_ylabel("Median days waited (still waiting)")
    ax.set_title("…but waits vary enormously at every level of deprivation")
    style.source_note(fig, SOURCE + " Each dot is a 2026 Sub-ICB location (n = 106).")
    fig.savefig(config.FIGURES / "03_deprivation_access_waits.png")
    style.close(fig)


def fig_equity(eng: pd.DataFrame, eth: pd.DataFrame, imd: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))
    fig.subplots_adjust(wspace=0.6)
    imd = imd.sort_index(ascending=False).rename(index=lambda s: {
        "01 Most deprived": "1 - most deprived", "05 Least deprived": "5 - least deprived"}.get(s, s.lstrip("0")))
    for ax, df, title in [
        (axes[0], imd, "By neighbourhood deprivation (IMD quintile)"),
        (axes[1], eth.sort_values("MHS95b"), "By ethnic group"),
    ]:
        y = np.arange(len(df))
        ax.barh(y, df["MHS95b"], height=0.6, color=style.BLUE)
        ax.errorbar(df["MHS95b"], y, xerr=df["MHS95c"], fmt="none", ecolor=style.INK, lw=1, capsize=2)
        for yi, (v, ci) in enumerate(zip(df["MHS95b"], df["MHS95c"], strict=True)):
            ax.text(v + ci + 150, yi, f"{v:,.0f}", va="center", fontsize=8, color=style.INK_2)
        ax.set_xlim(0, df["MHS95b"].max() * 1.15)
        ax.set_yticks(y, df.index)
        ax.grid(axis="y", visible=False)
        ax.set_xlabel("Age-standardised access per 100,000 under-18s")
        ax.set_title(title, fontsize=11)
    fig.suptitle("Who gets seen: England, 12 months to August 2026", x=0.01, ha="left", fontweight="bold")
    style.source_note(fig, SOURCE + " Error bars: 95% CI published with MHS95b.")
    fig.savefig(config.FIGURES / "04_equity_england.png")
    style.close(fig)


def fig_pathway_waits(path: pd.DataFrame) -> None:
    df = path.sort_values("MRS10a")
    fig, ax = plt.subplots(figsize=(8.5, 3.8))
    y = np.arange(len(df))
    ax.barh(y, df["MRS10a"], height=0.6, color=style.ORANGE)
    for yi, (v, n) in enumerate(zip(df["MRS10a"], df["MRS10"], strict=True)):
        ax.text(v + 15, yi, f"{v:,.0f} days  ({n:,.0f} waiting)", va="center", fontsize=8, color=style.INK_2)
    ax.axvline(28, color=style.CRITICAL, lw=1, ls="--")
    ax.text(36, -0.55, "28 days (4-week ambition)", color=style.CRITICAL, fontsize=8, va="center")
    ax.set_ylim(-0.8, len(df) - 0.5)
    ax.set_yticks(y, df.index)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Median days waited so far (open referrals awaiting first contact)")
    ax.set_title("Gender identity, autism and neurodevelopmental referrals wait longest")
    style.source_note(fig, SOURCE + " Four-week-wait (MRS10/MRS10a) measures, snapshot at 31 Aug 2026.")
    fig.savefig(config.FIGURES / "05_waits_by_pathway.png")
    style.close(fig)


# --------------------------------------------------------------------------- main


def run() -> dict:
    style.apply()
    config.FIGURES.mkdir(parents=True, exist_ok=True)
    sub, eng, geo = load()
    results: dict = {}

    # ---- England headline
    target = england_value(eng, "MHS95a")
    results["england"] = {
        "cyp_accessed_12m": england_value(eng, "MHS95"),
        "access_rate_per_100k": target,
        "pct_clock_stops_within_4w": england_value(eng, "MRS08b"),
        "open_waiting_first_contact": england_value(eng, "MRS10"),
        "median_open_wait_days": england_value(eng, "MRS10a"),
        "p90_open_wait_days": england_value(eng, "MRS10b"),
    }

    # ---- Reconciliation (data QA): Sub-ICBs should add up to England (minus 'UNKNOWN' residence)
    results["reconciliation"] = {
        "sum_sub_icb_accessed": float(sub.cyp_accessed_12m.sum()),
        "england_accessed": results["england"]["cyp_accessed_12m"],
        "coverage_pct": float(sub.cyp_accessed_12m.sum() / results["england"]["cyp_accessed_12m"] * 100),
    }

    # ---- Funnel plot with over-dispersion
    phi = st.overdispersion_phi(sub.access_rate_per_100k, sub.pop_u18_est, target)
    sub["funnel_class"] = st.classify_funnel(sub.access_rate_per_100k, sub.pop_u18_est, target, phi).values
    results["funnel"] = {"phi": phi, "counts": sub.funnel_class.value_counts().to_dict(),
                         "min_rate": float(sub.access_rate_per_100k.min()),
                         "max_rate": float(sub.access_rate_per_100k.max()),
                         "ratio_max_min": float(sub.access_rate_per_100k.max() / sub.access_rate_per_100k.min())}
    fig_funnel(sub, target, phi)

    # ---- Deprivation: SII + negative binomial model
    sii = st.slope_index_of_inequality(sub.access_rate_per_100k, sub.pop_u18_est, sub.idaci_score)
    results["sii_access_sub_icb"] = sii.__dict__
    predictors = ["idaci_score", "pct_pop_rural"]
    nb, irr = st.negative_binomial_rate_model(sub, "cyp_accessed_12m", "pop_u18_est", predictors)
    results["negative_binomial_irr"] = irr.round(4).to_dict(orient="index")
    results["nb_alpha"] = float(nb.params["alpha"])
    results["spearman_idaci_vs_median_wait"] = st.spearman_with_bootstrap_ci(
        sub.idaci_score, sub.median_wait_still_waiting_days)
    results["spearman_idaci_vs_pct_4w"] = st.spearman_with_bootstrap_ci(
        sub.idaci_score, sub.pct_clock_stops_within_4w)
    fig_deprivation(sub, nb, predictors)

    # ---- England equity breakdowns (age-standardised)
    imd = equity_table(eng, "England; IMD Quintile")
    eth = equity_table(eng, "England; Upper Ethnicity")
    most, least = imd.loc["01 Most deprived"], imd.loc["05 Least deprived"]
    results["imd_rate_ratio_most_vs_least"] = st.rate_ratio(most.MHS95, most.MHS95b, least.MHS95, least.MHS95b)
    results["sii_access_imd_quintile"] = st.slope_index_of_inequality(
        imd["MHS95b"], imd["pop"], -imd.index.str[:2].astype(int)).__dict__
    white = eth.loc["White or White British"]
    results["ethnicity_rate_ratios_vs_white"] = {
        g: st.rate_ratio(r.MHS95, r.MHS95b, white.MHS95, white.MHS95b)
        for g, r in eth.iterrows() if g != "White or White British"
    }
    fig_equity(eng, eth, imd)

    # ---- Four-week wait standard by deprivation (England, Jun-Aug 2026)
    c20 = (eng[eng.breakdown == "England; IMD Core20"]
           .pivot_table(index="group_name", columns="measure_id", values="value", aggfunc="first"))
    a, b = c20.loc["Most deprived quintile"], c20.loc["Other 4 quintiles"]
    results["four_week_core20_vs_rest"] = st.two_proportion_ztest(a.MRS08a, a.MRS08, b.MRS08a, b.MRS08)

    # ---- Waits by referral pathway
    path = (eng[eng.breakdown == "England; Pathway"]
            .pivot_table(index="group_name", columns="measure_id", values="value", aggfunc="first"))
    path.index = [PATHWAY_LABELS[_pathway_key(i)] for i in path.index]
    results["pathway_waits"] = path[["MRS10", "MRS10a", "MRS10b", "MRS08b"]].round(1).to_dict(orient="index")
    fig_pathway_waits(path)

    # ---- Maps
    fig_maps(sub, geo)

    # ---- Top/bottom areas table for README
    cols = ["sub_icb_name", "region_name", "access_rate_per_100k", "median_wait_still_waiting_days",
            "pct_clock_stops_within_4w", "idaci_score", "funnel_class"]
    results["highest_access"] = sub.nlargest(5, "access_rate_per_100k")[cols].round(2).to_dict("records")
    results["lowest_access"] = sub.nsmallest(5, "access_rate_per_100k")[cols].round(2).to_dict("records")
    results["longest_waits"] = sub.nlargest(5, "median_wait_still_waiting_days")[cols].round(2).to_dict("records")

    sub.to_parquet(config.PROCESSED / "mart_sub_icb_scored.parquet", index=False)
    out = config.ROOT / "reports" / "results.json"
    out.write_text(json.dumps(_json_safe(results), indent=2))
    log.info("wrote %s", out)
    return results


def _json_safe(obj):
    """Convert numpy scalars and NaN (invalid in strict JSON) to plain Python / null."""
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, np.generic):
        obj = obj.item()
    if isinstance(obj, float) and np.isnan(obj):
        return None
    return obj


def _pathway_key(description: str) -> str:
    """Map NHS England's long pathway descriptions to their published codes a-e.

    Order matters: the 'other' and 'mixed' descriptions also mention gender identity and autism.
    """
    d = description.lower()
    if d.startswith("spells with at least one 'other'"):
        return "d"
    if "; and at least one 'other'" in d:
        return "e"
    if d.endswith("gender discomfort issues"):
        return "a"
    if "neurodevelopmental conditions, excluding autism" in d:
        return "b"
    if "suspected autism" in d:
        return "c"
    raise ValueError(f"Unrecognised pathway description: {description!r}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run()
