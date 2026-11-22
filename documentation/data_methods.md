# Native data and descriptive/labor-relation module

Run `python code/data_module.py` from the package root. This module reconstructs source observations, descriptive statistics, the 46 labor relations, and the two Figure 1 panels and Figure A1. It does not use any reference estimates. The supplied Python files contain all numerical routines needed by this module.

## Data files and units

`documentation/data_acquisition.csv` identifies each frozen provider file, its source URL and recorded acquisition date. `data_raw_dictionary.csv` lists fields read from those files. `data_dictionary.csv` documents constructed variables, units, native date coverage and transformations. `data_output_fields.csv` identifies every processed/output field, including scale changes and aliases. Original workbook sheets are retained; the code reads only the indicated sheets and fields.

`data/processed/native_measures.csv` contains unshifted monthly economic observations over their native histories. `E2E` is an alias for original `FMP_SA`, used by the historical auxiliary regressions. `FMP_SA_3MA` is the published smoothed series used by the target manuscript. The descriptive output retains the display row identifier `variable=E2E` for the manuscript SA3MA measure; this row is calculated from `data_monthly.EE*100`, not from the native `E2E` auxiliary column. No additional moving average is applied. Native returns and probabilities are decimal units. D12 and E12 are already trailing-twelve-month levels. `native_quarterly.csv` contains unshifted quarterly observations; native LEHD_EEHireR is a decimal probability.

`data_monthly.csv` restricts dates to October 1995--December 2025 and uses `EE=FMP_SA_3MA`. It converts MARKET_EXCESS_LOG_RETURN to percentage points. `data_quarterly.csv` covers 1995Q4--2025Q4, converts LEHD_EEHireR to percent, and computes EE as the mean of three nonmissing monthly observations in each quarter. Hence 1995Q4 EE is missing because the published 3MA series starts in December 1995. Native files are shared with the returns and channels modules; those modules impose their own forecasting lags and samples.

## Source construction

- Payroll growth: 100 times the monthly log change in PAYEMS. UNEMP, LFPR and EPR retain the provider rates.
- Vacancy series: Barnichon V_hwi before December 2000 and JOLTS thereafter. Historical private vacancies equal Barnichon vacancies times JTS1000JOL/V_hwi at December 2000. JPR_PRIVATE_LONG is 100 V_private/(USPRIV+V_private). LMT_VU_LONG is the monthly change in log(V_total/UNEMPLOY).
- Hiring and quits: divide DFH quarterly rates by three, assign the result to each month of that quarter, and add the level difference relative to private JOLTS in December 2000. From December 2000 use private JOLTS. The quarter assignment is part of the original variable construction, not interpolation from monthly observations. Actual splice parameters are saved in data_splice_parameters.csv.
- LIG_JW: set I=(PI-PDI)/POPTHM, then use 100[(I_t+I_(t-1))/(I_(t-1)+I_(t-2))-1]. Income annualization and population units cancel in this growth calculation.
- Claims intensity: the last weekly IC4WSA observation dated within each completed month, divided by lagged CE16OV times 1000, then multiplied by 100. No value is constructed for the partially observed final source month.
- CPS_UE: 100 UE/(UE+UU+UN) using LNS17100000, LNS17500000 and LNS17900000. Missing component observations propagate to the probability.
- LEHD: national, all-industry/all-demographic, seasonally adjusted EEHireR from the R2026Q3 J2JR file. The exact category selectors and eligible provider publication flags appear in native.py.
- WGT: columns I/J in the provider data_overall sheet are stayer/switcher wage growth; they already contain the provider's three-month averages. The spread is switcher minus stayer.
- Production: COMPNFB, OPHNFB and ULCNFB are transformed to 100 times their quarterly four-quarter log changes. PRS85006173 is retained as the labor-share index.
- GW variables: DP=log(D12)-log(Index), DY=log(D12)-log(lagged Index), EP=log(E12)-log(Index), DE=log(D12)-log(E12), TMS=lty-tbl, DFY=BAA-AAA, DFR=corpr-ltr; the other eight columns retain provider definitions. Excess log return is log(1+CRSP_SPvw)-log(1+Rfree). Rfree is a monthly holding return and is not divided by twelve.

## Descriptive statistics and 46 labor regressions

Each of the 25 descriptive rows uses its own nonmissing observations. Correlations with EE use common contemporaneous dates. Standard deviations use ddof=1. Autocorrelations use actual calendar lags, preserving missing months.

The eight outcomes are LEHD_EEHireR, LFPR, EPR, CPS_UE, WGT_SWITCHER, WGT_STAYER, WGT_SPREAD and LS_NFB_INDEX. Each has contemporaneous and next-period bivariate regressions (16 total). Six monthly outcomes have conditional horizons 1,3,6,12, and the two quarterly outcomes have horizons 1,2,4 (30 total). The conditional equation is Z_(t+h)=a+b EE_t+c Z_t+u. Within each regression's valid pairs or triplets, the dependent variable and regressors are separately standardized using the sample mean and sample SD. No forecasting release lag is applied to these economic relations.

Inference uses calendar-aware Bartlett Newey--West with 12 monthly or four quarterly lags, covariance correction N/(N-K), and two-sided Student t probabilities with N-K degrees of freedom. Missing periods are omitted from OLS but not compressed for HAC lag matching. data_relation_ledger.csv records every regression observation, its origin and outcome date, standardized values, fitted value and residual.

Figure datasets preserve the joint samples. Panel A presents EE in percent; Panel B standardizes quarterly EE and LEHD within their common sample; Figure A1 standardizes published monthly EE and switcher/stayer wage growth within their common sample. Missing October 2025 wage data remain a gap. data_figure_wages.csv has 348 calendar rows and 347 complete joint observations.

## Source access

Inputs are obtained separately using `data_acquisition.csv`. This package
contains definitions and code, not source observations or reconstructed data.
