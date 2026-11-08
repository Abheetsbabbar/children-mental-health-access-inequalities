"""Statistical methods used in public-health inequality analysis.

Every function here is pure (no I/O) and unit-tested in tests/test_stats.py.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

# --------------------------------------------------------------------------- funnel plots


def funnel_limits(target_rate: float, population: np.ndarray, z: float, per: float = 100_000,
                  phi: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """Control limits for a rate per `per` population (Poisson, normal approximation).

    SE(rate) = sqrt(rate * per / population) * sqrt(phi), where phi is an
    over-dispersion factor (phi = 1 gives the classic Poisson funnel).
    z = 1.96 -> 95% limits ("warning"); z = 3.09 -> 99.8% limits ("alarm").
    """
    population = np.asarray(population, dtype=float)
    se = np.sqrt(target_rate * per / population) * np.sqrt(phi)
    return target_rate - z * se, target_rate + z * se


def overdispersion_phi(rates: np.ndarray, populations: np.ndarray, target_rate: float,
                       per: float = 100_000, winsor: float = 0.10) -> float:
    """Spiegelhalter (2005) multiplicative over-dispersion estimate from winsorised z-scores.

    Large administrative areas almost always vary more than pure Poisson noise allows
    (case-mix, coding practice, service models). Ignoring this flags nearly every area
    as an outlier; phi > 1 widens the funnel accordingly.
    """
    rates = np.asarray(rates, dtype=float)
    populations = np.asarray(populations, dtype=float)
    z = (rates - target_rate) / np.sqrt(target_rate * per / populations)
    lo, hi = np.quantile(z, [winsor, 1 - winsor])
    z_w = np.clip(z, lo, hi)
    return float(max(1.0, np.mean(z_w**2)))


def classify_funnel(rates, populations, target_rate, phi=1.0, per=100_000) -> pd.Series:
    rates = np.asarray(rates, dtype=float)
    lo95, hi95 = funnel_limits(target_rate, populations, 1.96, per, phi)
    lo998, hi998 = funnel_limits(target_rate, populations, 3.09, per, phi)
    out = np.where(rates > hi998, "High (>99.8%)",
          np.where(rates > hi95, "High (>95%)",
          np.where(rates < lo998, "Low (<99.8%)",
          np.where(rates < lo95, "Low (<95%)", "Within limits"))))
    return pd.Series(out)


# --------------------------------------------------------------------------- inequality indices


@dataclass(frozen=True)
class SlopeIndex:
    sii: float  # absolute gap (rate units) between most and least deprived ends of the gradient
    rii: float  # SII divided by the population mean rate
    ci_low: float
    ci_high: float


def slope_index_of_inequality(rates, populations, deprivation_score, higher_is_more_deprived=True
                              ) -> SlopeIndex:
    """Slope Index of Inequality (SII) and Relative Index of Inequality (RII).

    Areas are ranked by deprivation; each gets the midpoint of its cumulative population
    share (a 'ridit' score from 0 = least to 1 = most deprived). A population-weighted
    least-squares regression of the rate on that rank gives the SII: the modelled
    difference between the very most and very least deprived. Used in the OHID
    Fingertips and NHS England health inequalities frameworks.
    """
    df = pd.DataFrame({"rate": rates, "pop": populations, "dep": deprivation_score}).dropna()
    df = df.sort_values("dep", ascending=higher_is_more_deprived)
    share = df["pop"] / df["pop"].sum()
    df["ridit"] = share.cumsum() - share / 2
    X = sm.add_constant(df["ridit"])
    fit = sm.WLS(df["rate"], X, weights=df["pop"]).fit()
    sii = float(fit.params["ridit"])
    lo, hi = fit.conf_int().loc["ridit"]
    mean_rate = float(np.average(df["rate"], weights=df["pop"]))
    return SlopeIndex(sii=sii, rii=sii / mean_rate, ci_low=float(lo), ci_high=float(hi))


# --------------------------------------------------------------------------- count models


def negative_binomial_rate_model(df: pd.DataFrame, outcome: str, exposure: str, predictors: list[str]):
    """Negative-binomial regression of counts with a log-population offset.

    Coefficients are standardised (per 1 SD) and exponentiated to Incidence Rate
    Ratios (IRR). NB rather than Poisson because area counts are over-dispersed.
    """
    data = df[[outcome, exposure, *predictors]].dropna().copy()
    Xz = (data[predictors] - data[predictors].mean()) / data[predictors].std(ddof=0)
    X = sm.add_constant(Xz)
    model = sm.NegativeBinomial(data[outcome], X, exposure=data[exposure]).fit(disp=False, maxiter=200)
    ci = model.conf_int()
    table = pd.DataFrame({
        "irr_per_sd": np.exp(model.params),
        "ci_low": np.exp(ci[0]),
        "ci_high": np.exp(ci[1]),
        "p_value": model.pvalues,
    }).drop(index=["const", "alpha"], errors="ignore")
    return model, table


# --------------------------------------------------------------------------- simple comparisons


def two_proportion_ztest(success_a: float, n_a: float, success_b: float, n_b: float) -> dict:
    p_a, p_b = success_a / n_a, success_b / n_b
    p_pool = (success_a + success_b) / (n_a + n_b)
    se = np.sqrt(p_pool * (1 - p_pool) * (1 / n_a + 1 / n_b))
    z = (p_a - p_b) / se
    diff_se = np.sqrt(p_a * (1 - p_a) / n_a + p_b * (1 - p_b) / n_b)
    return {
        "p_a": p_a, "p_b": p_b, "diff": p_a - p_b,
        "diff_ci_low": p_a - p_b - 1.96 * diff_se, "diff_ci_high": p_a - p_b + 1.96 * diff_se,
        "z": z, "p_value": 2 * stats.norm.sf(abs(z)),
    }


def rate_ratio(count_a: float, rate_a: float, count_b: float, rate_b: float) -> dict:
    """Rate ratio with a log-normal 95% CI; populations are treated as fixed."""
    rr = rate_a / rate_b
    se_log = np.sqrt(1 / count_a + 1 / count_b)
    return {"rate_ratio": rr, "ci_low": rr * np.exp(-1.96 * se_log), "ci_high": rr * np.exp(1.96 * se_log)}


def spearman_with_bootstrap_ci(x, y, n_boot: int = 5000, seed: int = 42) -> dict:
    x, y = np.asarray(x, float), np.asarray(y, float)
    mask = ~(np.isnan(x) | np.isnan(y))
    x, y = x[mask], y[mask]
    rho, p = stats.spearmanr(x, y)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(x), size=(n_boot, len(x)))
    boots = np.array([stats.spearmanr(x[i], y[i])[0] for i in idx])
    lo, hi = np.nanpercentile(boots, [2.5, 97.5])
    return {"rho": float(rho), "p_value": float(p), "ci_low": float(lo), "ci_high": float(hi), "n": int(len(x))}
