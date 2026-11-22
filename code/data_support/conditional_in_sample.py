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

