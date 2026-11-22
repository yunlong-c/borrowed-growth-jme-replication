# Cash-flow and economic-channel reproduction

Run `python code/channels_module.py` after the data and returns modules. Use
`python run_all.py --stage validate` after a complete run to check outputs.
All paths are relative to this package. The estimator never reads `reference/`.

## Inputs and derivation

`channel_support/prepare.py` reads the published FMP workbook and the frozen
Goyal-Welch workbook in `data/raw/descriptive/`. FMP_SA_3MA is used as published;
there is no second moving average. D12 and E12 are nominal trailing-twelve-month
levels. GW CRSP_SPvw and Rfree construct monthly excess log returns as
log(1+CRSP_SPvw)-log(1+Rfree), without dividing the monthly risk-free return by 12.

The channel-specific sources, original fields, units and versions are listed
in `data_acquisition.csv`. The practical field dictionary is
`channels_dictionary.csv`; it distinguishes source values, processed predictors,
target endpoints, missing-value rules and computed VAR/PCA fields. Shared raw
FMP/GW source availability is additionally documented in `data_acquisition.csv`. Workbook source data are supplied by the replicator. Output source-level CSVs
are reconstructed on every run. The original intermediate decimal serialization
(15 significant digits for source levels; 12 for the external pricing panel) is
retained to reproduce the manuscript's exact inputs.

SCE: workbook aggregate means on the Job finding expectations and Job separation
expectation sheets become JF and JL. Their units are percent probabilities.
Targets are future levels rather than changes. For h>0 the regression includes
the current expectation. The EE scale uses the SCE sample before horizon-specific
endpoint truncation. Pricing: select last observed trading-day SKEW each month,
merge the provider's monthly BEX variance and the Federal Reserve Figure 1.5 ERP
series; retain March 1996–December 2025, then use the original column-wise mean/SD.

## Quarterly production and other economic relationships

Cash-flow estimation is implemented separately in `code/aligned`; see
`aligned_methods.md`. This module retains economic-month EE in labor, survey,
financial-state and VAR projection relationships.

Quarterly production uses the average of three complete economic-month EE
observations. COMPNFB, OPHNFB and ULCNFB growth targets use native quarterly
endpoints; past growth is measured over four quarters. Separate-year paths
share 100 five-year-complete origins. Short targets use NW(4), cumulative targets
use NW(h), and separate-year paths use NW(20), with N/(N-K) and Student-t(N-K).
Table C5 displays the identical short/cumulative h=4 estimates once while
retaining the separate-year first-year estimates. All 78 computed rows remain.

## All 23 VAR systems and PCA are re-estimated

`config/channels_var.json` explicitly registers the state sets and exact PCA
inputs. `data/processed/return_comparison_panel.csv` is reconstructed by the
returns module and contains the original Nov 1995–Dec 2025 state calendar. The
measure in that input is not added as a VAR state. `channel_support/return_decomposition.py`
standardizes the 12 financial PCA inputs over this calendar with ddof=1 and uses
SVD to calculate 3 PCs. It then estimates all 23 demeaned, no-intercept VAR(1) systems
on valid adjacent calendar months. Rho is
1/(1+exp(mean(log(D12/Index)))/12), preserving the manuscript's monthly_dp rule.

Expected returns are VAR fitted total log returns, including the return mean.
Discount-rate news uses the linear-system loading rho e1'A(I-rho A)^(-1);
cash-flow news is the return innovation plus discount-rate news. Every
observation satisfies realized_return=expected_return+CF_news-DR_news.
No frozen return components, transition matrices or PCA scores are inputs.

`channels_module.var` then matches each component's origin month to published
SA3MA EE_t, discards missing EE, and standardizes EE on that system's projection
sample. It regresses each component multiplied by 100 on const and EE. All four
projections include an intercept and use NW(1) without covariance df correction,
with normal probabilities. The resulting formal manuscript estimates are
`channel_var.csv`; the component and slope identities are retained. The generic
engine's auxiliary projection ledger uses the original input-panel EE and is
kept for computational traceability; it does not replace the formal SA3MA
projection estimates.

## Outputs and validation

The module estimates 183 models and 413 coefficient rows, including 78 production
rows, ten SCE rows, three financial-state rows and projections for 23 VAR systems.
`channel_coefficients.csv`, `channel_covariance.csv` and observation ledgers
record the fitted parameters. `channel_var.csv` contains the EE projections;
PCA scores, loadings and return components are regenerated. Validation checks
component and slope identities. The removed attention-state analysis is not executed.
