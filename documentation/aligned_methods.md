# Return and cash-flow specifications

The authoritative computation is `code/aligned/`. Preparation reads GW Monthly
columns CRSP_SPvw, Rfree, D12, E12 and the EE Data column FMP_SA_3MA. The published
EE series is shifted by one calendar month and is never smoothed again.
Nominal TTM levels are neither deflated nor re-aggregated.

The in-sample predictor is standardized using the fixed mean and sample SD
(ddof=1) of valid lagged predictors over January 1996-December 2025. Return
targets are average monthly excess log returns, h=1,3,6,12. EE and cumulative
coefficient/SE identities are saved. Monthly and cumulative t-statistics and
R-squared are identical.

Cash-flow cumulative targets are 100 log(C[t+h]/C[t]), h=1,3,6,12,24,36,48,60.
Post-first-year targets are 100 log(C[t+h]/C[t+12]), h=24,36,48,60. Past growth
is 100 log(C[t]/C[t-12]), retained in percentage points. All three specifications
use common valid origins for a given target and horizon. Full coefficients,
including both slopes in the joint model, are saved. Presentation reports the
EE slope for models containing EE and the past-growth slope otherwise.

Separate-year targets are 100 log(C[t+12k]/C[t+12(k-1)]), k=1,...,5. The same
300 origins per outcome have all five years and past growth observed. EE-only
and EE plus past growth use this common sample.

Calendar Bartlett HAC preserves gaps. Intercept-inclusive correction is N/(N-K).
Return slopes use NW(h); short cash-flow slopes use NW(12); long/post-first-year
slopes use NW(h); separate-year slopes use NW(60).

Return inference uses 10,000 regenerated monthly innovations, seed 20260925,
on the December 1995-December 2025 return calendar. The original auxiliary
regression uses underlying seasonally adjusted FMP_SA and the twelve independent
GW predictors; it is not a monthly demeaning generator. The regenerated
residuals/innovations are generated locally from the recipient-supplied inputs. Only the
lagged predictor and its valid-date mask change in the core regressions.

Short cash-flow bootstrap resamples non-circular overlapping blocks jointly
across y and all explanatory variables: length 12, 20,000 draws,
RandomState(20261006). The statistic is (beta_star-beta_hat)/SE_star. Two-sided
probabilities are (extreme_count+1)/(draws+1). Draw ordering is preserved across
dividend then earnings targets and ascending short horizons; each target/horizon
shares blocks across specifications. Long and separate-year formal probabilities
are two-sided Student-t(N-K), not bootstrap probabilities.

OOS begins at origin December 2009. Training admits origins s only if s+h<=t;
post-first-year windows use the total endpoint h. EE standardization is computed
from the common mature training observations at each origin. The return HA uses
monthly realized excess log returns from December 1995 through t. Dividend HA
is the mean of the same growth target over the common mature training sample.
EE, past growth and both predictors are compared with HA; both predictors are
also compared with past growth. Earnings have no OOS forecasts.

R2_OS is 100 times one minus the MSFE ratio. CW uses centered calendar Bartlett
HAC(h) of the adjusted loss differential, no covariance df correction, and the
Student-t(N-2) upper tail. Negative statistics and probabilities are retained.

`results/aligned/` preserves OLS/HAC objects, individual regression observations,
target endpoints, bootstrap draws and counts, OOS forecasts, training membership,
training scales, coefficient ledgers and CW differences. Validation independently
rebuilds these identities without altering them.
