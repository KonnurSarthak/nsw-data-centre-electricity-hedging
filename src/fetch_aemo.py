"""Download AEMO aggregated price and demand CSVs, one file per region per month.

Usage from the project root: python -m src.fetch_aemo --region NSW1 --start 2021-07 --end 2024-06
"""
import argparse
import time
from pathlib import Path

import pandas as pd
import requests

AEMO_URL = "https://www.aemo.com.au/aemo/data/nem/priceanddemand/PRICE_AND_DEMAND_{yyyymm}_{region}.csv"
AEMO_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "aemo"
# AEMO rejects requests without a browser-like user agent.
HEADERS = {"User-Agent": "Mozilla/5.0 (research data download)"}


def month_list(start: str, end: str) -> list[str]:
    """Return 'YYYYMM' for every month from start to end inclusive (inputs as 'YYYY-MM')."""
    return [month.strftime("%Y%m") for month in pd.period_range(start, end, freq="M")]


def fetch_month(yyyymm: str, region: str, out_dir: Path = AEMO_DIR) -> Path:
    """Download one monthly CSV unless it is already on disk."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"PRICE_AND_DEMAND_{yyyymm}_{region}.csv"
    if path.exists():
        return path
    response = requests.get(AEMO_URL.format(yyyymm=yyyymm, region=region), headers=HEADERS, timeout=60)
    response.raise_for_status()
    path.write_bytes(response.content)
    # Pause between requests so a 36-file download doesn't hammer AEMO's server.
    time.sleep(1)
    return path


def load_months(region: str, start: str, end: str, raw_dir: Path = AEMO_DIR) -> pd.DataFrame:
    """Read the downloaded monthly CSVs for a region into one uncleaned table."""
    monthly = [pd.read_csv(raw_dir / f"PRICE_AND_DEMAND_{m}_{region}.csv") for m in month_list(start, end)]
    return pd.concat(monthly, ignore_index=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download AEMO aggregated price and demand CSVs.")
    parser.add_argument("--region", default="NSW1")
    parser.add_argument("--start", default="2021-07")
    parser.add_argument("--end", default="2024-06")
    args = parser.parse_args()
    for yyyymm in month_list(args.start, args.end):
        print(fetch_month(yyyymm, args.region).name)


if __name__ == "__main__":
    main()
