"""Profiling and reconciliation helpers. Read-only: nothing here modifies its inputs."""
import pandas as pd


def profile_table(table: pd.DataFrame) -> pd.DataFrame:
    """One row per column: dtype, nulls, distinct count, and min/median/max where meaningful."""
    rows = []
    for column in table.columns:
        values = table[column]
        is_numeric = pd.api.types.is_numeric_dtype(values)
        is_ordered = is_numeric or pd.api.types.is_datetime64_any_dtype(values)
        rows.append({
            "column": column,
            "dtype": str(values.dtype),
            "nulls": int(values.isna().sum()),
            "null_pct": round(100 * values.isna().mean(), 3),
            "distinct": int(values.nunique()),
            "min": values.min() if is_ordered else None,
            "median": values.median() if is_numeric else None,
            "max": values.max() if is_ordered else None,
        })
    return pd.DataFrame(rows)


def iqr_outliers(values: pd.Series, k: float = 1.5) -> pd.Series:
    """Boolean mask of values outside [Q1 - k*IQR, Q3 + k*IQR]."""
    q1, q3 = values.quantile([0.25, 0.75])
    iqr = q3 - q1
    return (values < q1 - k * iqr) | (values > q3 + k * iqr)


def interval_gaps(timestamps: pd.Series, freq: str = "5min") -> dict:
    """Compare timestamps with a complete regular grid: counts of duplicates, missing and off-grid."""
    observed = pd.DatetimeIndex(pd.to_datetime(timestamps))
    grid = pd.date_range(observed.min(), observed.max(), freq=freq)
    missing = grid.difference(observed)
    off_grid = observed.difference(grid)
    return {
        "expected": len(grid),
        "actual": len(observed),
        "duplicates": int(observed.duplicated().sum()),
        "missing": len(missing),
        "off_grid": len(off_grid),
        "missing_examples": list(missing[:5]),
        "off_grid_examples": list(off_grid[:5]),
    }


def reconcile(left: pd.DataFrame, right: pd.DataFrame, key: str, columns: dict, tol: float = 0.01) -> pd.DataFrame:
    """Outer-join two tables on `key` and compare matched values.

    columns: maps a left column name to the right column it should equal.
    """
    merged = left.merge(right, on=key, how="outer", indicator=True)
    matched = merged[merged["_merge"] == "both"]
    rows = []
    for left_col, right_col in columns.items():
        abs_diff = (matched[left_col] - matched[right_col]).abs()
        rows.append({
            "left": left_col,
            "right": right_col,
            "only_left": int((merged["_merge"] == "left_only").sum()),
            "only_right": int((merged["_merge"] == "right_only").sum()),
            "matched": len(matched),
            "mismatches": int((abs_diff > tol).sum()),
            "max_abs_diff": abs_diff.max(),
        })
    return pd.DataFrame(rows)
