"""Fixed-design multivariate HAC and conditional wild-bootstrap inference."""
from __future__ import annotations

import numpy as np


def multivariate_hac_many(targets, design, maxlags):
    """OLS coefficients, Bartlett HAC SEs and t statistics for rows of targets.

    The supplied design includes the intercept. The correction is n/(n-k).
    """
    y = np.atleast_2d(np.asarray(targets, dtype=float))
    d = np.asarray(design, dtype=float)
    n, k = d.shape
    if y.shape[1] != n or np.linalg.matrix_rank(d) != k:
        raise ValueError("Targets must align with a full-rank design.")
    bread = np.linalg.inv(d.T @ d)
    beta = y @ (bread @ d.T).T
    residual = y - beta @ d.T
    influence = d @ bread
    variance = np.empty((len(y), k))
    for j in range(k):
        score = residual * influence[:, j]
        v = np.sum(score * score, axis=1)
        for lag in range(1, min(int(maxlags), n - 1) + 1):
            v += 2 * (1 - lag / (maxlags + 1)) * np.sum(
                score[:, lag:] * score[:, :-lag], axis=1)
        variance[:, j] = v * n / (n - k)
    se = np.sqrt(variance)
    return beta, se, beta / se


def monthly_wild_innovations(residuals, replications, seed):
    """Match the baseline RandomState normal-multiplier convention."""
    residual = np.asarray(residuals, dtype=float)
    return np.random.RandomState(int(seed)).standard_normal(
        (int(replications), len(residual))) * residual


def overlapping_innovations(monthly_innovations, horizon, scale=100.0):
    """Average monthly innovations indexed by their realized return month."""
    a = np.asarray(monthly_innovations, dtype=float)
    c = np.concatenate([np.zeros((len(a), 1)), np.cumsum(a, axis=1)], axis=1)
    h = int(horizon)
    return float(scale) * (c[:, h:] - c[:, :-h]) / h


def conditional_wild_bootstrap(target, design, innovations, maxlags,
                               tested_columns=(1, 2), batch_size=500):
    """Studentized tests imposing one coefficient restriction at a time.

    innovations already contain the registered overlapping monthly wild shocks,
    in the same units as target. Nuisance coefficients are retained through the
    observed restricted fit. All tests use the same innovations.
    """
    y = np.asarray(target, dtype=float)
    d = np.asarray(design, dtype=float)
    shocks = np.asarray(innovations, dtype=float)
    observed = multivariate_hac_many(y, d, maxlags)[2][0]
    columns = tuple(tested_columns)
    simulations = np.empty((len(shocks), len(columns)))
    restricted = {}
    for position, column in enumerate(columns):
        nuisance = np.delete(d, column, axis=1)
        fitted = nuisance @ np.linalg.lstsq(nuisance, y, rcond=None)[0]
        restricted[column] = fitted
        for start in range(0, len(shocks), batch_size):
            stop = min(start + batch_size, len(shocks))
            simulated_y = fitted[None, :] + shocks[start:stop]
            simulations[start:stop, position] = multivariate_hac_many(
                simulated_y, d, maxlags)[2][:, column]
    counts = np.sum(np.abs(simulations) >= np.abs(observed[list(columns)]), axis=0)
    return {"observed_t": observed[list(columns)], "t_draws": simulations,
            "extreme_count": counts, "p_two_sided": counts / len(shocks),
            "restricted_fitted": restricted}

