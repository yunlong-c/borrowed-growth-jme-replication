# Replication Guide

**Borrowed Growth: Employer-to-Employer Mobility, Corporate Cash Flows, and Stock Returns**

Version 1.0.0, prepared November 22, 2026  

All file paths below are relative to the repository root.

## Overview

This package constructs the empirical analysis from external inputs and generates
the current JME manuscript's **22 empirical tables and three empirical figures**:
main Tables 1–6 and Figures 1–2; Internet Appendix Tables A1–A2, B1–B6 and C1–C8,
and Figure A1. It contains variable dictionaries, data acquisition instructions,
estimation programs, table layouts and figure code.

The calibration and simulation code for Section 5 (Tables 7–10 and Figure 3)
is not included in this release. The authors will deposit it before publication.
This package generates empirical exhibits, not the manuscript PDF.

## Data availability

**No source datasets or precomputed analytical results are distributed.**
Obtain the 36 input files below from their original providers and put them at
the specified relative paths. Several sources have third-party licensing or
redistribution conditions, including CRSP-derived fields in Goyal–Welch,
Federal Reserve Bank datasets, Cboe indices and author-produced indices.
Public download access is distinct from permission to republish a dataset.

BLS numerical series are public-domain material; they are also omitted under
this package's uniform code-only distribution. FRED is a distributor, and the
originating provider's terms govern each series.

Use the recorded versions, including the August 2026 FMP workbook, the
Goyal–Welch snapshot acquired in September 2026 with observations through
December 2025, and Census R2026Q3. Live download endpoints may now contain
revisions. If a recorded vintage is no longer served, request it from the
provider; the corresponding author can clarify provenance and facilitate
access within the provider's terms. Exact historical vintages are needed for
numerical agreement with the paper.

The CTYZ attention index and VIX attention-state analysis belong to a table
removed from the current manuscript and are not required.

## Quick start

Install **Python 3.12**, obtain the inputs, and run from the package root:

```text
python -m pip install -r requirements.txt
python run_all.py
```

A run with missing files stops before estimation and prints missing paths,
provider links, versions, worksheets and columns. No data are downloaded.
Keep workbook sheet names and CSV columns unchanged; filenames alone do not
establish the data vintage.

Execution order: data construction → returns and allocation → economic channels
→ core return/cash-flow inference → tables and figures → validation.
The returns module reconstructs bootstrap innovations using the original
residual generator and seed; no frozen residual data are needed.

```text
python run_all.py --stage estimate
python run_all.py --stage presentation
python run_all.py --stage validate
python run_all.py --module returns
```

`--module data|returns|channels|aligned` runs that module and its predecessors.
Presentation requires completed estimates; validation also requires generated
exhibits. The full command is recommended. Repeated runs replace local outputs.

## Computational requirements

Pinned dependencies: NumPy 2.5.1, pandas 3.0.5, SciPy 1.18.0,
Matplotlib 3.11.1, openpyxl 3.1.5 and pyarrow 25.0.0.
No proprietary statistical software, GPU or TeX installation is required.
All input and output paths are relative to the package.

The complete run was tested with Python 3.12.14 on Windows 11, an Intel Core i7-14650HX (16 cores / 24 logical processors) and 31.7 GiB installed RAM. Computation, exhibit generation and validation took 178.7 seconds (about 3.0 minutes); generated files occupied about 152.3 MiB. This is the measured test configuration.

Bootstrap designs use 10,000 monthly wild-bootstrap draws with seed 20260925
and 20,000 paired moving-block draws with seed 20261006. See the four methods
documents in `documentation/` for calendar timing, sample definitions,
inference and serialization precision.

## Files and generated outputs

| Location | Contents |
| --- | --- |
| `run_all.py`, `requirements.txt` | Entry point and dependencies |
| `code/`, `config/` | Computation, presentation and validation |
| `layouts/` | Current empirical table shells, with zero-valued numeric placeholders |
| `documentation/` | Acquisition register, dictionaries, methods and exhibit map |
| `data/raw/` | Recipient-supplied inputs; empty in the public archive |
| `data/processed/`, `results/` | Locally reconstructed data and estimates |
| `output/tables/` | Generated LaTeX table fragments |
| `output/numerical/` | Full-precision table bindings and Figure 2 paths |
| `output/figures/` | Figures 1, 2 and A1 as PDF and PNG |
| `logs/` | Local runtime, environment and validation reports |

Table shells store no coefficient estimates. Computed results fill 3,544
displayed cells. The LaTeX fragments are intended for inclusion in a manuscript
using the corresponding table packages/macros; CSV bindings need no TeX.
The `.gitignore` excludes inputs, reconstructed data, results and logs.
Publish the supplied clean release, not a working directory containing
locally generated data governed by provider terms.

## Data acquisition register

`documentation/data_acquisition.csv` is the machine-readable register used by
the run entry point. `data_raw_dictionary.csv` additionally records original
snapshot coverage and missing-value conventions.

| Input path | Provider and access | Recorded vintage / acquisition | Download | Required worksheet / fields |
| --- | --- | --- | --- | --- |
| `data/raw/descriptive/PAYEMS.csv` | U.S. Bureau of Labor Statistics via FRED; Public-domain BLS series | 2026-09-13T16:03:37.228975+00:00 | [Provider file / page](https://fred.stlouisfed.org/graph/fredgraph.csv?id=PAYEMS) | Date: observation_date. Values: PAYEMS |
| `data/raw/descriptive/UNRATE.csv` | U.S. Bureau of Labor Statistics via FRED; Public-domain BLS series | 2026-09-13T16:03:35.924865+00:00 | [Provider file / page](https://fred.stlouisfed.org/graph/fredgraph.csv?id=UNRATE) | Date: observation_date. Values: UNRATE |
| `data/raw/descriptive/CIVPART.csv` | U.S. Bureau of Labor Statistics via FRED; Public-domain BLS series | 2026-09-23T12:35:02.200692+00:00 | [Provider file / page](https://fred.stlouisfed.org/graph/fredgraph.csv?id=CIVPART) | Date: observation_date. Values: CIVPART |
| `data/raw/descriptive/EMRATIO.csv` | U.S. Bureau of Labor Statistics via FRED; Public-domain BLS series | 2026-09-23T12:35:02.200692+00:00 | [Provider file / page](https://fred.stlouisfed.org/graph/fredgraph.csv?id=EMRATIO) | Date: observation_date. Values: EMRATIO |
| `data/raw/descriptive/JTSJOL.csv` | U.S. Bureau of Labor Statistics via FRED; Public-domain BLS series | 2026-09-13T16:03:37.592604+00:00 | [Provider file / page](https://fred.stlouisfed.org/graph/fredgraph.csv?id=JTSJOL) | Date: observation_date. Values: JTSJOL |
| `data/raw/descriptive/JTS1000JOL.csv` | U.S. Bureau of Labor Statistics via FRED; Public-domain BLS series | 2026-09-23T12:35:03.994018+00:00 | [Provider file / page](https://fred.stlouisfed.org/graph/fredgraph.csv?id=JTS1000JOL) | Date: observation_date. Values: JTS1000JOL |
| `data/raw/descriptive/UNEMPLOY.csv` | U.S. Bureau of Labor Statistics via FRED; Public-domain BLS series | 2026-09-13T16:03:36.265069+00:00 | [Provider file / page](https://fred.stlouisfed.org/graph/fredgraph.csv?id=UNEMPLOY) | Date: observation_date. Values: UNEMPLOY |
| `data/raw/descriptive/USPRIV.csv` | U.S. Bureau of Labor Statistics via FRED; Public-domain BLS series | 2026-09-13T16:03:37.231756+00:00 | [Provider file / page](https://fred.stlouisfed.org/graph/fredgraph.csv?id=USPRIV) | Date: observation_date. Values: USPRIV |
| `data/raw/descriptive/JTS1000HIR.csv` | U.S. Bureau of Labor Statistics via FRED; Public-domain BLS series | 2026-09-23T12:35:04.871041+00:00 | [Provider file / page](https://fred.stlouisfed.org/graph/fredgraph.csv?id=JTS1000HIR) | Date: observation_date. Values: JTS1000HIR |
| `data/raw/descriptive/JTS1000QUR.csv` | U.S. Bureau of Labor Statistics via FRED; Public-domain BLS series | 2026-09-23T12:35:05.524591+00:00 | [Provider file / page](https://fred.stlouisfed.org/graph/fredgraph.csv?id=JTS1000QUR) | Date: observation_date. Values: JTS1000QUR |
| `data/raw/descriptive/PI.csv` | U.S. Bureau of Economic Analysis via FRED; Provider download; source-specific terms | 2026-09-23T12:35:02.200692+00:00 | [Provider file / page](https://fred.stlouisfed.org/graph/fredgraph.csv?id=PI) | Date: observation_date. Values: PI |
| `data/raw/descriptive/PDI.csv` | U.S. Bureau of Economic Analysis via FRED; Provider download; source-specific terms | 2026-09-23T12:35:02.201690+00:00 | [Provider file / page](https://fred.stlouisfed.org/graph/fredgraph.csv?id=PDI) | Date: observation_date. Values: PDI |
| `data/raw/descriptive/POPTHM.csv` | U.S. Bureau of Economic Analysis via FRED; Provider download; source-specific terms | 2026-09-23T12:35:02.824837+00:00 | [Provider file / page](https://fred.stlouisfed.org/graph/fredgraph.csv?id=POPTHM) | Date: observation_date. Values: POPTHM |
| `data/raw/descriptive/IC4WSA.csv` | U.S. Department of Labor via FRED; Provider download; source-specific terms | 2026-09-23T12:41:21.789711+00:00 | [Provider file / page](https://fred.stlouisfed.org/graph/fredgraph.csv?id=IC4WSA) | Date: observation_date. Values: IC4WSA |
| `data/raw/descriptive/CE16OV.csv` | U.S. Bureau of Labor Statistics via FRED; Public-domain BLS series | 2026-09-13T16:03:36.845036+00:00 | [Provider file / page](https://fred.stlouisfed.org/graph/fredgraph.csv?id=CE16OV) | Date: observation_date. Values: CE16OV |
| `data/raw/descriptive/LNS17100000.csv` | U.S. Bureau of Labor Statistics via FRED; Public-domain BLS series | 2026-09-13T16:05:36.787258+00:00 | [Provider file / page](https://fred.stlouisfed.org/graph/fredgraph.csv?id=LNS17100000) | Date: observation_date. Values: LNS17100000 |
| `data/raw/descriptive/LNS17500000.csv` | U.S. Bureau of Labor Statistics via FRED; Public-domain BLS series | 2026-09-13T16:05:40.206008+00:00 | [Provider file / page](https://fred.stlouisfed.org/graph/fredgraph.csv?id=LNS17500000) | Date: observation_date. Values: LNS17500000 |
| `data/raw/descriptive/LNS17900000.csv` | U.S. Bureau of Labor Statistics via FRED; Public-domain BLS series | 2026-09-13T16:05:38.272030+00:00 | [Provider file / page](https://fred.stlouisfed.org/graph/fredgraph.csv?id=LNS17900000) | Date: observation_date. Values: LNS17900000 |
| `data/raw/descriptive/PRS85006173.csv` | U.S. Bureau of Labor Statistics via FRED; Public-domain BLS series | 2026-09-23T12:35:03.940171+00:00 | [Provider file / page](https://fred.stlouisfed.org/graph/fredgraph.csv?id=PRS85006173) | Date: observation_date. Values: PRS85006173 |
| `data/raw/descriptive/COMPNFB.csv` | U.S. Bureau of Labor Statistics via FRED; Public-domain BLS series | 2026-09-13T16:03:40.033281+00:00 | [Provider file / page](https://fred.stlouisfed.org/graph/fredgraph.csv?id=COMPNFB) | Date: observation_date. Values: COMPNFB |
| `data/raw/descriptive/OPHNFB.csv` | U.S. Bureau of Labor Statistics via FRED; Public-domain BLS series | 2026-09-23T12:35:03.868867+00:00 | [Provider file / page](https://fred.stlouisfed.org/graph/fredgraph.csv?id=OPHNFB) | Date: observation_date. Values: OPHNFB |
| `data/raw/descriptive/ULCNFB.csv` | U.S. Bureau of Labor Statistics via FRED; Public-domain BLS series | 2026-09-13T16:03:40.049697+00:00 | [Provider file / page](https://fred.stlouisfed.org/graph/fredgraph.csv?id=ULCNFB) | Date: observation_date. Values: ULCNFB |
| `data/raw/descriptive/USREC.csv` | NBER recession chronology via FRED; Provider download; source-specific terms | 2026-09-13T16:03:40.068444+00:00 | [Provider file / page](https://fred.stlouisfed.org/graph/fredgraph.csv?id=USREC) | Date: observation_date. Values: USREC |
| `data/raw/descriptive/e2e-2026-08.xlsx` | Philadelphia Fed / Fujita, Moscarini and Postel-Vinay; Provider download; source-specific terms | 2026-09-13T16:02:35.435678+00:00 | [Provider file / page](https://www.philadelphiafed.org/-/media/FRBP/Assets/Surveys-And-Data/employer-to-employer/2026/e2e-2026-08.xlsx) | Sheet: Data. Date: year, month. Values: FMP_NSA;FMP_SA;FMP_SA_3MA |
| `data/raw/descriptive/PredictorData_updated.xlsx` | Goyal-Welch; includes CRSP-derived fields; Provider download; source-specific terms | 2026-09-13T16:03:43.521395+00:00 | [Provider file / page](https://docs.google.com/spreadsheets/d/1qwpl2R_DNujpU5YUkk8lacP1tTeMb9iJ/export?format=xlsx) | Sheet: Monthly. Date: yyyymm (first column). Values: D12;E12;Index;b/m;ntis;tbl;lty;BAA;AAA;ltr;corpr;svar;infl;CRSP_SPvw;Rfree |
| `data/raw/descriptive/barnichon_composite_hwi.xlsx` | Regis Barnichon; Provider download; source-specific terms | 2026-09-13T16:03:47.110374+00:00 | [Provider file / page](https://docs.google.com/spreadsheets/d/1fkMinSHkjTL99-bLZYFldQ8rHtgh8lxd/export?format=xlsx) | Sheet: Sheet1. Date: first column: decimal year. Values: second column V_hwi |
| `data/raw/descriptive/DFH XS TS Synthetic JOLTS Series (1990-2010).xlsx` | Davis, Faberman and Haltiwanger; Provider download; source-specific terms | 2026-09-23 | [Provider file / page](https://stevenjdavis.com/s/FilesJMESubmission-6xwd.zip) | Sheet: Data. Date: first column YYYYQ. Values: H_Rate (fourth column);Q_Rate (sixth column) |
| `data/raw/descriptive/wage-growth-data.xlsx` | Federal Reserve Bank of Atlanta; Provider download; source-specific terms | 2026-09-13T16:02:36.019844+00:00 | [Provider file / page](https://www.atlantafed.org/-/media/Project/Atlanta/FRBA/Documents/datafiles/chcs/wage-growth-tracker/wage-growth-data.xlsx) | Sheet: data_overall. Date: column A. Values: I Job Stayer;J Job Switcher |
| `data/raw/descriptive/j2jr_us_d_f_gn_n_oslp_s.csv.gz` | U.S. Census Bureau / LEHD; Provider download; source-specific terms | 2026-09-23T12:41:27.641343+00:00 | [Provider file / page](https://lehd.ces.census.gov/data/j2j/R2026Q3/us/j2jr/j2jr_us_d_f_gn_n_oslp_s.csv.gz) | Date: year;quarter. Values: EEHireR;sEEHireR;geography;industry;ownercode;sex;agegrp;race;ethnicity;education;firmage;firmsize |
| `data/raw/channels/SKEW_History.csv` | Cboe; Provider download; source-specific terms | 2026-09-01 | [Provider file / page](https://cdn.cboe.com/api/global/us_indices/daily_prices/SKEW_History.csv) | Date: DATE. Values: SKEW |
| `data/raw/channels/BEX_Indices_20260808.xlsx` | Bekaert Engstrom Xu; Provider download; source-specific terms | workbook2026-08-08; acquired2026-09-01 | [Provider file / page](https://www.nancyxu.net/risk-aversion-index) | Sheet: DATA_PLOT_monthly. Date: yyyymm. Values: ra_bex_PAPER;unc_bex_PAPER;unc_bex_AnnualVolPercentage |
| `data/raw/channels/financial_stability_report_2026_may_accessibility_tables.htm` | Federal Reserve Board; Provider download; source-specific terms | 2026-May report; acquired2026-09-01 | [Provider file / page](https://www.federalreserve.gov/publications/2026-may-financial-stability-report-accessibility-tables.htm#figure-1.5) | Sheet: HTML table title starts Figure 1.5.. Date: Date. Values: Equity premium |
| `data/raw/channels/frbny-sce-data.xlsx` | Federal Reserve Bank of New York; Provider download; source-specific terms | 2026-09-14 | [Provider file / page](https://www.newyorkfed.org/microeconomics/sce) | Sheet: Job finding expectations;Job separation expectation. Date: first column YYYYMM; header row 4. Values: second column: mean probability |
| `data/raw/channels/COMPNFB.csv` | FRED / US Bureau of Labor Statistics; Public-domain BLS series | 2026-09-14 | [Provider file / page](https://fred.stlouisfed.org/series/COMPNFB) | Date: observation_date. Values: COMPNFB |
| `data/raw/channels/OPHNFB.csv` | FRED / US Bureau of Labor Statistics; Public-domain BLS series | 2026-09-23 | [Provider file / page](https://fred.stlouisfed.org/series/OPHNFB) | Date: observation_date. Values: OPHNFB |
| `data/raw/channels/ULCNFB.csv` | FRED / US Bureau of Labor Statistics; Public-domain BLS series | 2026-09-14 | [Provider file / page](https://fred.stlouisfed.org/series/ULCNFB) | Date: observation_date. Values: ULCNFB |

FRED CSVs use `observation_date` and the named series column. The three BLS
productivity inputs appear in both `descriptive/` and `channels/` because
modules read these locations separately; retain each path's vintage.
Barnichon uses the first two columns after eight header rows. DFH uses quarter
codes in A, hiring in D and quits in F. Atlanta Fed uses dates in A and wage
growth in I/J. The Census gzip must retain the category and publication-status
fields in `data_raw_dictionary.csv`. The Federal Reserve HTML must contain
the table titled Figure 1.5.

## Exhibit map

`documentation/exhibit_map.csv` links each current exhibit to results,
bindings and output files. Current C6 is return-decomposition fit,
C7 is employment expectations, and C8 is financial conditions.

| JME exhibit | Title | Reproduction status |
| --- | --- | --- |
| Table 1 | In-Sample and Out-of-Sample Return Predictability | Included |
| Table 2 | Economic Value of Mobility-Based Forecasts | Included |
| Table 3 | Forecast and Portfolio Robustness | Included |
| Table 4 | Cash-Flow Predictability | Included |
| Table 5 | Wages, Labor Costs, and Productivity | Included |
| Table 6 | Return Decomposition | Included |
| Table A1 | Summary Statistics and Correlations with EE Mobility | Included |
| Table A2 | EE Mobility and Labor-Market Outcomes | Included |
| Table B1 | Return Predictability of Financial and Macroeconomic Indicators | Included |
| Table B2 | Forecast Encompassing Tests for EE and Alternative Predictors | Included |
| Table B3 | Out-of-Sample Performance of EE Forecast Combinations | Included |
| Table B4 | Portfolio Performance of Alternative Return Forecasts | Included |
| Table B5 | Out-of-Sample Return Forecasts under Alternative Specifications | Included |
| Table B6 | Portfolio Performance under Alternative Investment Specifications | Included |
| Table C1 | Cash-Flow Predictability with Past-Growth Controls | Included |
| Table C2 | Long-Horizon Cash-Flow Predictability | Included |
| Table C3 | Year-by-Year Cash-Flow Predictability | Included |
| Table C4 | Out-of-Sample Dividend-Growth Forecasts with Past-Growth Controls | Included |
| Table C5 | Predictability of Compensation, Productivity, and Unit Labor Costs | Included |
| Table C6 | Predictive Regression Fit for Total Returns and Return Components | Included |
| Table C7 | EE Mobility and Workers’ Employment Expectations | Included |
| Table C8 | EE Mobility and Aggregate Financial Conditions | Included |
| Figure 1 | Employer-to-Employer Mobility | Included |
| Figure 2 | Cumulative Out-of-Sample Forecast Gains | Included |
| Figure A1 | EE Mobility and Wage Growth of Job Switchers and Stayers | Included |
| Table 7 | Calibration | Model code to be deposited before publication |
| Table 8 | Model vs. Data: Unconditional Moments (monthly) | Model code to be deposited before publication |
| Table 9 | Model vs. Data: Cumulative Predictability | Model code to be deposited before publication |
| Table 10 | Channel Ablation (twelve-month cumulative coefficients) | Model code to be deposited before publication |
| Figure 3 | The Mechanism in Event Time | Model code to be deposited before publication |

Figure A1 uses the current manuscript's dual-axis layout, with equal standard-deviation scales for EE and wages.

Current Tables 3, B5 and B6 omit the former 2005 training-start row.
Existing robustness computations are retained; display bindings select
the specifications reported in the current manuscript.

## Citation and licenses

Source code: [https://github.com/yunlong-c/borrowed-growth-jme-replication](https://github.com/yunlong-c/borrowed-growth-jme-replication).
Cite the fixed [v1.0.0 release](https://github.com/yunlong-c/borrowed-growth-jme-replication/releases/tag/v1.0.0) for this version.

Original code/configuration use [MIT](../LICENSE); original documentation and
table-layout text use [CC BY 4.0](../LICENSE-docs.md).
These grants do not cover externally obtained data.

## Provider terms and documentation

- [BLS copyright information](https://www.bls.gov/opub/copyright-information.htm)
- [Philadelphia Fed terms](https://www.philadelphiafed.org/about-us/privacy-notice)
- [FRED legal notices](https://fred.stlouisfed.org/legal/)
- [NY Fed terms](https://www.newyorkfed.org/privacy/termsofuse.html)
- [Cboe data policies](https://datashop.cboe.com/data-policies)
- [Goyal data page](https://sites.google.com/view/agoyal145)
- [Social Science Data Editors README guidance](https://social-science-data-editors.github.io/template_README/template-README.html)
