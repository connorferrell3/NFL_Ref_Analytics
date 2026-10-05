"""Small-sample statistics. A referee works ~17 games a season, so raw rates are mostly noise;
everything shown in the dashboard goes through one of these."""
import numpy as np
import pandas as pd
from scipy import stats


def wilson_ci(k, n, z: float = 1.96):
    """95% Wilson interval for a proportion; well behaved at small n unlike the normal approx."""
    k, n = np.asarray(k, float), np.asarray(n, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        p = k / n
        denom = 1 + z**2 / n
        center = (p + z**2 / (2 * n)) / denom
        half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return center - half, center + half


def binom_pvalue(k, n, p0: float = 0.5) -> np.ndarray:
    """Two-sided exact binomial test of each rate against p0."""
    return np.array([stats.binomtest(int(ki), int(ni), p0).pvalue if ni > 0 else np.nan
                     for ki, ni in zip(k, n)])


def bh_qvalues(p) -> np.ndarray:
    """Benjamini-Hochberg FDR q-values. With 17+ crews and several betting markets, a handful of
    raw p < .05 results are expected by chance alone; q-values correct for that."""
    p = np.asarray(p, float)
    q = np.full_like(p, np.nan)
    ok = ~np.isnan(p)
    pv = p[ok]
    order = np.argsort(pv)
    ranked = pv[order] * len(pv) / (np.arange(len(pv)) + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty_like(pv)
    out[order] = np.clip(ranked, 0, 1)
    q[ok] = out
    return q


def eb_proportion(k, n) -> tuple[np.ndarray, np.ndarray]:
    """Empirical-Bayes (beta-binomial, method of moments) shrinkage of per-group rates.

    Returns (shrunk_rate, reliability). Reliability = n / (n + kappa) is the share of a crew's
    raw deviation we believe is real. If observed spread between crews is no larger than
    binomial noise would produce, kappa -> inf and every crew is shrunk to the league rate."""
    k, n = np.asarray(k, float), np.asarray(n, float)
    m = k.sum() / n.sum()
    p = k / n
    var_obs = np.average((p - m) ** 2, weights=n)
    var_noise = np.average(m * (1 - m) / n, weights=n)
    tau2 = var_obs - var_noise
    if tau2 <= 1e-9:
        return np.full_like(p, m), np.zeros_like(p)
    kappa = m * (1 - m) / tau2 - 1
    kappa = max(kappa, 0.0)
    return (k + kappa * m) / (n + kappa), n / (n + kappa)


def eb_mean(means, ns, within_var: float) -> tuple[np.ndarray, np.ndarray]:
    """Normal-normal shrinkage of per-group means (e.g. penalties per game).

    within_var is the game-to-game variance of the metric (pooled). Returns (shrunk, reliability)."""
    x, n = np.asarray(means, float), np.asarray(ns, float)
    m = np.average(x, weights=n)
    noise = within_var / n
    tau2 = max(np.var(x, ddof=1) - noise.mean(), 0.0)
    b = tau2 / (tau2 + noise)
    return m + b * (x - m), b


def year_over_year(df: pd.DataFrame, metric: str, group: str = "referee",
                   min_games: int = 8) -> dict:
    """Does a crew's metric in season t predict the same metric in season t+1?

    This is the core "signal vs noise" test. A tendency that doesn't persist year to year
    (r ~ 0) cannot be used to predict next week's game, however striking it looks."""
    by = (df.groupby([group, "season"])[metric].agg(["mean", "size"]).reset_index())
    by = by[by["size"] >= min_games]
    nxt = by.assign(season=by["season"] - 1)
    pairs = by.merge(nxt, on=[group, "season"], suffixes=("_t", "_t1"))
    n = len(pairs)
    if n < 5:
        return {"metric": metric, "r": np.nan, "lo": np.nan, "hi": np.nan, "pairs": n}
    r = pairs["mean_t"].corr(pairs["mean_t1"])
    z, se = np.arctanh(r), 1 / np.sqrt(n - 3)
    return {"metric": metric, "r": r, "lo": np.tanh(z - 1.96 * se), "hi": np.tanh(z + 1.96 * se), "pairs": n}
