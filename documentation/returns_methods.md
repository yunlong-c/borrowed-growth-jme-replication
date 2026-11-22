# Return prediction and allocation module

Run `python code/returns_module.py` after `python code/data_module.py` (or use the package master). The estimator reads only `data/processed/native_measures.csv`, produced from the recipient-supplied source data. It never reads `reference/`.

## Computation inherited from the manuscript

The native data are first mapped to forecast origins November 1995 through December 2025. GW predictors have lag zero except INFL (one month); PAYROLL, UNEMP, LFPR, LIG_JW and CLAIMS_INTENSITY have one month; JPR_PRIVATE_LONG, LMT_VU_LONG, HIRES_PRIVATE_LONG and QUITS_PRIVATE_LONG have two months. The comparison-bootstrap E2E regressor is FMP_SA lagged one month. The EE core regressions are implemented in code/aligned and use previous-month FMP_SA_3MA in both IS and OOS; their fixed IS scale spans January 1996-December 2025. The return_is.csv file from this module now contains the 23 comparison predictors only. The published moving average is not smoothed again.

In-sample targets are 100 times the average of the next h monthly log excess returns, h=1,3,6,12. Fixed predictor means and sample standard deviations use the complete registered origin window, retaining native missing observations. OLS uses complete targets and regressors. Calendar-aware Bartlett Newey-West uses h lags and N/(N-2). Stars use a two-sided studentized wild bootstrap with 10,000 replications, NumPy RandomState seed 20260925, and the original monthly normal-multiplier ordering. Monthly innovations are aggregated into overlapping h-month means before missing predictors are omitted.

Two auxiliary regressions are estimated afresh. The comparison variables use lagged FMP_SA plus twelve GW predictors. Current E2E uses contemporaneous FMP_SA plus the same GW predictors (INFL remains lagged). The twelve are DP, DY, EP, BM, NTIS, TBL, LTY, DFY, LTR, DFR, SVAR and INFL. Their generated residuals and coefficients are saved. This recreates the actual manuscript inference rather than imposing a single residual generator retrospectively.

## Out-of-sample calculations

The initial forecast origin is December 2009. At origin t, model estimation admits only origins s with s+h <= t, and predictor standardization is re-estimated in that training sample. The log-return HA is the mean of observed monthly log excess returns beginning December 1995, through t. Ordinary OOS R-squared compares squared prediction errors. Clark-West uses its adjusted loss differential, centered calendar Bartlett HAC(h), no covariance degrees-of-freedom correction, and the signed one-sided Student t(N-2) probability.

Forecast-encompassing comparisons use centered calendar Bartlett HAC(h), the HLN factor, and signed t(N-1) probabilities. Equal-weight combinations average paired forecasts. Dynamic combinations use inverse discounted squared-error scores (discount .75), with weights one half until twelve paired forecast errors have matured. The calendar target end controls maturity.

## Economic value and robustness

Economic-value regressions forecast compounded simple excess returns: product(1+market return) minus product(1+risk-free return). The HA is the average of mature same-horizon compounded targets. Portfolio weights are forecast/(gamma * variance), clipped to [-.5,1.5]. Baseline gamma=3 and risk variance uses the last 120 mature overlapping targets. Performance is evaluated on nonoverlapping holding periods starting January 2010, using annualized certainty equivalents and excess-return Sharpe ratios.

Comparison allocations retain the original risk history beginning December 1995. E2E recomputes risk using the longer native history beginning February 1994. Forecast robustness comprises OOS starts 2005/2015, training starts 2000/2005 (only the 2000 start is displayed in the current JME tables), rolling 120, arithmetic-average simple returns, and nonnegative forecasts. Economic robustness additionally uses gamma 5, risk-window 60, and proportional transaction costs 50/100 basis points. Transaction costs follow the original self-financing turnover equation and carry forward post-return weights.

## Files and source correspondence

- `return_comparison_panel.csv`, `return_panel.csv`, `return_timing_ledger.csv`: recreated origin inputs and date mappings.
- `return_is.csv`, `return_bootstrap_inference.csv`: comparison-predictor coefficients, actual fit and bootstrap counts. EE core IS results are in `results/aligned/`.
- `return_bootstrap_sink_*.csv`, `return_bootstrap_coefficients_*.csv`: independently fitted residual generators.
- `return_regression_observations.csv`: all IS rows.
- `return_forecasts.csv`, `return_oos.csv`: complete model forecasts and summary measures.
- `return_encompassing*`, `return_paired_oos.csv`, `return_combination*`: forecast comparisons and combinations.
- `return_robustness*`, `return_economic_robustness_forecasts.csv`: forecast scenarios.
- `portfolio_ledger.csv`, `portfolio_summary.csv`, `portfolio_robustness*`: holdings and performance.

The input is the rebuilt native-measure file. Core return and cash-flow
specifications, including the monthly innovation generator, are in `aligned_methods.md`.
