"""Unit tests for the statistical helpers - known answers and edge cases."""

import numpy as np
import pandas as pd
import pytest

from cypmh_access import stats as st


def test_funnel_limits_narrow_as_population_grows():
    lo, hi = st.funnel_limits(1000, np.array([1_000, 100_000]), z=1.96)
    assert hi[0] - lo[0] > hi[1] - lo[1]
    # symmetric about the target
    assert np.allclose((lo + hi) / 2, 1000)


def test_funnel_limits_known_value():
    # rate 1000 per 100k on population 100k -> expected count 1000, SE(rate) = sqrt(1000) per 100k
    lo, hi = st.funnel_limits(1000, np.array([100_000]), z=1.96)
    assert hi[0] == pytest.approx(1000 + 1.96 * np.sqrt(1000))


def test_overdispersion_is_one_for_pure_poisson():
    rng = np.random.default_rng(0)
    pops = rng.integers(50_000, 500_000, size=2000)
    rate = 7000
    counts = rng.poisson(rate / 100_000 * pops)
    phi = st.overdispersion_phi(counts / pops * 100_000, pops, rate)
    assert phi == pytest.approx(1.0, abs=0.15)


def test_overdispersion_detects_extra_variation():
    rng = np.random.default_rng(1)
    pops = rng.integers(50_000, 500_000, size=500)
    true_rates = rng.normal(7000, 1500, size=500).clip(1000)
    counts = rng.poisson(true_rates / 100_000 * pops)
    assert st.overdispersion_phi(counts / pops * 100_000, pops, 7000) > 10


def test_classify_funnel_labels():
    out = st.classify_funnel([5000, 7000, 9000], [100_000] * 3, target_rate=7000)
    assert list(out) == ["Low (<99.8%)", "Within limits", "High (>99.8%)"]


def test_sii_recovers_linear_gradient():
    # rate rises linearly by 1000 from least to most deprived across equal-population areas
    n = 10
    dep = np.arange(n)
    ridit = (np.arange(n) + 0.5) / n
    rates = 5000 + 1000 * ridit
    res = st.slope_index_of_inequality(rates, np.ones(n) * 1000, dep)
    assert res.sii == pytest.approx(1000, rel=1e-6)
    assert res.rii == pytest.approx(1000 / rates.mean(), rel=1e-6)


def test_sii_sign_flips_when_gradient_reverses():
    n = 10
    rates = 6000 - 100 * np.arange(n)
    res = st.slope_index_of_inequality(rates, np.ones(n), np.arange(n))
    assert res.sii < 0


def test_negative_binomial_recovers_rate_ratio():
    rng = np.random.default_rng(3)
    n = 400
    x = rng.normal(size=n)
    pop = rng.integers(50_000, 300_000, size=n)
    mu = pop * 0.07 * np.exp(0.2 * x)
    counts = rng.negative_binomial(n=50, p=50 / (50 + mu))
    df = pd.DataFrame({"y": counts, "pop": pop, "x": x})
    _, table = st.negative_binomial_rate_model(df, "y", "pop", ["x"])
    assert table.loc["x", "irr_per_sd"] == pytest.approx(np.exp(0.2 * x.std()), rel=0.05)


def test_two_proportion_ztest_symmetry_and_null():
    res = st.two_proportion_ztest(50, 100, 50, 100)
    assert res["diff"] == 0 and res["p_value"] == pytest.approx(1.0)
    a = st.two_proportion_ztest(30, 100, 50, 100)
    b = st.two_proportion_ztest(50, 100, 30, 100)
    assert a["z"] == pytest.approx(-b["z"])


def test_rate_ratio_ci_contains_point_estimate():
    rr = st.rate_ratio(300, 3000, 700, 7000)
    assert rr["ci_low"] < rr["rate_ratio"] < rr["ci_high"]
    assert rr["rate_ratio"] == pytest.approx(3000 / 7000)


def test_spearman_bootstrap_perfect_monotone():
    x = np.arange(50)
    res = st.spearman_with_bootstrap_ci(x, x**2, n_boot=200)
    assert res["rho"] == pytest.approx(1.0)
    assert res["ci_low"] > 0.95
