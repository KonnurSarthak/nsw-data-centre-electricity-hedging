"""Apply the data-audit fixes and write the cleaned 5-minute tables to data/processed/.

Usage from the project root: python -m src.clean
"""
from pathlib import Path

import pandas as pd

from src.fetch_aemo import load_months

ROOT = Path(__file__).resolve().parents[1]
SOLAR_XLSX = ROOT / "data" / "raw" / "Solar Farm Dispatch Data.xlsx"
PROCESSED_DIR = ROOT / "data" / "processed"

# Five-minute settlement started 1 Oct 2021; earlier AEMO files are 30-minute, so the pool starts here.
POOL_START = pd.Timestamp("2021-10-01 00:00")
POOL_END = pd.Timestamp("2024-07-01 00:00")
SOLAR_FARM_MW = 102
# NSW administered price cap applied from 13 June 2022; AEMO lifted the market suspension at 14:00 on 24 June 2022.
ADMINISTERED_START = pd.Timestamp("2022-06-13 00:00")
ADMINISTERED_END = pd.Timestamp("2022-06-24 14:00")


def financial_year(interval_start: pd.Series) -> pd.Series:
    """Australian financial year label: Jul 2021-Jun 2022 is FY2022."""
    return interval_start.dt.to_period("Q-JUN").dt.qyear


def clean_prices(region: str = "NSW1") -> pd.DataFrame:
    """5-minute spot prices and regional demand, keyed by interval start, for the analysis pool."""
    raw = load_months(region, "2021-10", "2024-06")
    interval_end = pd.to_datetime(raw["SETTLEMENTDATE"], format="%Y/%m/%d %H:%M:%S")
    # AEMO stamps the end of each interval; days, months and FYs must be assigned by interval start.
    prices = pd.DataFrame({
        "interval_start": interval_end - pd.Timedelta("5min"),
        "spot_price": raw["RRP"],
        "region_demand_mw": raw["TOTALDEMAND"],
    })
    prices = prices[(prices["interval_start"] >= POOL_START) & (prices["interval_start"] < POOL_END)]
    prices["fy"] = financial_year(prices["interval_start"])
    # Real settlement prices, kept as-is; flagged so charts and the crisis sensitivity can identify them.
    prices["administered_period"] = prices["interval_start"].between(ADMINISTERED_START, ADMINISTERED_END, inclusive="left")
    return prices.reset_index(drop=True)


def clean_solar_factor() -> pd.DataFrame:
    """Normalised 0-1 solar output factor at 5-minute resolution for the analysis pool."""
    raw = pd.read_excel(SOLAR_XLSX)
    # The export stamps interval end minus one second (00:04:59); rounding up aligns it with AEMO.
    interval_end = pd.to_datetime(raw["SETTLEMENTDATE"]).dt.ceil("min")
    solar_mw = pd.Series(raw["Solar Farm Output"].to_numpy(), index=interval_end - pd.Timedelta("5min"))
    grid = pd.date_range(POOL_START, POOL_END, freq="5min", inclusive="left")
    # Two midday intervals are missing (5 Dec 2023); output changes smoothly, so linear fill is safe.
    solar_mw = solar_mw.reindex(grid).interpolate(limit_area="inside")
    # Outage days are kept: a PPA with one farm carries that farm's outages.
    return pd.DataFrame({
        "interval_start": grid,
        "solar_factor": (solar_mw / SOLAR_FARM_MW).round(4).to_numpy(),
    })


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    prices = clean_prices()
    prices.to_parquet(PROCESSED_DIR / "nsw1_prices_5min.parquet", index=False)
    solar = clean_solar_factor()
    # Gzipped to keep the committed file around 1 MB; pandas reads .csv.gz directly.
    solar.to_csv(PROCESSED_DIR / "solar_factor_5min.csv.gz", index=False, date_format="%Y-%m-%d %H:%M")
    print(f"prices: {len(prices):,} rows; solar factor: {len(solar):,} rows")


if __name__ == "__main__":
    main()
