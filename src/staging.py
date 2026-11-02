"""Run the staging SQL in DuckDB and write the joined 5-minute interval table to data/processed/.

Usage from the project root: python -m src.staging
"""
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"
INTERVALS_PATH = ROOT / "data" / "processed" / "intervals_5min.parquet"


def build_intervals() -> pd.DataFrame:
    """Run sql/*.sql in file-number order and return the int_intervals table."""
    con = duckdb.connect()
    # The SQL files use repo-relative paths so they also run from the DuckDB CLI at the project root.
    con.execute(f"set file_search_path = '{ROOT.as_posix()}'")
    for sql_file in sorted(SQL_DIR.glob("*.sql")):
        con.execute(sql_file.read_text())
    return con.sql("select * from int_intervals").df()


def main() -> None:
    intervals = build_intervals()
    intervals.to_parquet(INTERVALS_PATH, index=False)
    print(f"intervals: {len(intervals):,} rows")


if __name__ == "__main__":
    main()
