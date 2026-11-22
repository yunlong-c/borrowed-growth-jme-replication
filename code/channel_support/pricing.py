from pathlib import Path
from html.parser import HTMLParser
import numpy as np
import pandas as pd
RAW=Path(__file__).resolve().parents[2]/"data/raw/channels"
RAW_CBOE=RAW
RAW_BEX=RAW
RAW_FED=RAW
ANALYSIS_START=pd.Period("1996-03",freq="M")
ANALYSIS_END=pd.Period("2025-12",freq="M")
ACCESS_DATE="2026-09-01"

def _read_cboe_skew() -> pd.DataFrame:
    frame = pd.read_csv(RAW_CBOE / "SKEW_History.csv")
    if list(frame.columns) != ["DATE", "SKEW"]:
        raise ValueError(f"unexpected SKEW schema: {list(frame.columns)}")
    frame["date"] = pd.to_datetime(frame["DATE"], format="%m/%d/%Y")
    frame["skew"] = pd.to_numeric(frame["SKEW"], errors="raise")
    frame["month"] = frame["date"].dt.to_period("M")

    last = (
        frame.sort_values("date")
        .groupby("month", as_index=False)
        .tail(1)
        .set_index("month")
    )
    means = frame.groupby("month")["skew"].mean().rename("skew_daily_mean")
    result = last[["date", "skew"]].rename(
        columns={"date": "skew_observation_date"}
    )
    return result.join(means, how="left").reset_index()


def _read_bex() -> pd.DataFrame:
    path = RAW_BEX / "BEX_Indices_20260808.xlsx"
    frame = pd.read_excel(
        path,
        sheet_name="DATA_PLOT_monthly",
        usecols="A:D",
    )
    expected = [
        "yyyymm",
        "ra_bex_PAPER",
        "unc_bex_PAPER",
        "unc_bex_AnnualVolPercentage",
    ]
    if list(frame.columns) != expected:
        raise ValueError(f"unexpected BE-X monthly schema: {list(frame.columns)}")
    frame["month"] = pd.to_datetime(
        frame["yyyymm"].astype("Int64").astype(str), format="%Y%m"
    ).dt.to_period("M")
    frame = frame.rename(
        columns={
            "ra_bex_PAPER": "bex_risk_aversion",
            "unc_bex_PAPER": "bex_uncertainty_variance",
            "unc_bex_AnnualVolPercentage": "bex_uncertainty_ann_vol_pct",
        }
    )
    return frame[
        [
            "month",
            "bex_risk_aversion",
            "bex_uncertainty_variance",
            "bex_uncertainty_ann_vol_pct",
        ]
    ]


class _FedEquityPremiumParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_target_table = False
        self.in_row = False
        self.in_cell = False
        self.cell_text: list[str] = []
        self.current_row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        if tag == "table" and str(attributes.get("title", "")).startswith(
            "Figure 1.5."
        ):
            self.in_target_table = True
        elif self.in_target_table and tag == "tr":
            self.in_row = True
            self.current_row = []
        elif self.in_row and tag in {"th", "td"}:
            self.in_cell = True
            self.cell_text = []

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.cell_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.in_cell and tag in {"th", "td"}:
            text = " ".join("".join(self.cell_text).split())
            self.current_row.append(text)
            self.in_cell = False
            self.cell_text = []
        elif self.in_row and tag == "tr":
            if self.current_row:
                self.rows.append(self.current_row)
            self.current_row = []
            self.in_row = False
        elif self.in_target_table and tag == "table":
            self.in_target_table = False


def _read_fed_equity_premium() -> pd.DataFrame:
    path = (
        RAW_FED / "financial_stability_report_2026_may_accessibility_tables.htm"
    )
    parser = _FedEquityPremiumParser()
    parser.feed(path.read_text(encoding="utf-8"))
    if not parser.rows or parser.rows[0] != ["Date", "Equity premium"]:
        raise ValueError("Federal Reserve Figure 1.5 table was not identified")
    frame = pd.DataFrame(parser.rows[1:], columns=parser.rows[0])
    frame["month"] = pd.to_datetime(frame["Date"], errors="raise").dt.to_period("M")
    frame["fed_equity_premium_pp"] = pd.to_numeric(
        frame["Equity premium"], errors="raise"
    )
    return frame[["month", "fed_equity_premium_pp"]]


def build_market_pricing_panel() -> pd.DataFrame:
    panel = _read_cboe_skew()
    panel = panel.merge(_read_bex(), on="month", how="outer", validate="one_to_one")
    panel = panel.merge(
        _read_fed_equity_premium(),
        on="month",
        how="outer",
        validate="one_to_one",
    )
    panel = panel.loc[
        panel["month"].between(ANALYSIS_START, ANALYSIS_END)
    ].copy()
    panel = panel.sort_values("month").reset_index(drop=True)

    panel["cboe_observation_date"] = panel["skew_observation_date"]
    panel["source_vintage"] = ACCESS_DATE
    panel["cboe_timing"] = "last_available_trading_day_in_month"
    panel["bex_timing"] = "provider_monthly_current_vintage"
    panel["fed_erp_timing"] = "month_end_current_vintage"

    for column in (
        "cboe_observation_date",
        "skew_observation_date",
    ):
        panel[column] = pd.to_datetime(panel[column]).dt.strftime("%Y-%m-%d")
    panel["month"] = panel["month"].astype(str)
    return panel[
        [
            "month",
            "cboe_observation_date",
            "skew_observation_date",
            "skew",
            "bex_risk_aversion",
            "bex_uncertainty_variance",
            "bex_uncertainty_ann_vol_pct",
            "fed_equity_premium_pp",
            "skew_daily_mean",
            "source_vintage",
            "cboe_timing",
            "bex_timing",
            "fed_erp_timing",
        ]
    ]


