"""Simulate financial years by drawing 7-day blocks of historical days from the same calendar month."""
import numpy as np
import pandas as pd

BLOCK_DAYS = 7
N_YEARS = 5_000
# One seed for every FY, so differences between FYs come only from the futures price and the calendar.
SEED = 2028


def draw_years(pool_dates: pd.DatetimeIndex, fy: int, n_years: int = N_YEARS) -> np.ndarray:
    """Positions into pool_dates for each simulated day: shape (n_years, days in target FY).

    pool_dates must be sorted whole calendar months. The same matrix is reused for every strategy,
    so differences come from the strategy, not the draw.
    """
    rng = np.random.default_rng(SEED)
    pool_dates = pd.DatetimeIndex(pool_dates)
    positions = pd.Series(np.arange(len(pool_dates)))
    year_month = pool_dates.year * 100 + pool_dates.month
    month_first = positions.groupby(year_month).transform("min").to_numpy()
    month_len = positions.groupby(year_month).transform("size").to_numpy()

    columns = []
    for month_start in pd.date_range(f"{fy - 1}-07-01", f"{fy}-06-01", freq="MS"):
        month_days = month_start.days_in_month
        starts = positions.to_numpy()[pool_dates.month == month_start.month]
        n_blocks = -(-month_days // BLOCK_DAYS)
        chosen = rng.choice(starts, size=(n_years, n_blocks))[:, :, None]
        offset = chosen - month_first[chosen] + np.arange(BLOCK_DAYS)
        # Blocks wrap from the month's last day back to its first, so every day is equally likely to be drawn.
        days = month_first[chosen] + offset % month_len[chosen]
        # The last block is cut short so each simulated month has its real number of days.
        columns.append(days.reshape(n_years, -1)[:, :month_days])
    return np.hstack(columns)


def expected_draws(pool_dates: pd.DatetimeIndex, fy: int) -> np.ndarray:
    """Expected number of times each pool day appears in one simulated year of FY fy."""
    pool_month = pd.Series(pd.DatetimeIndex(pool_dates).month)
    target_days = pd.Series(pd.date_range(f"{fy - 1}-07-01", f"{fy}-06-30").month).value_counts()
    # With wrap-around blocks every pool day of a calendar month is equally likely, so it gets that month's
    # simulated days shared over the pool days available for it.
    return pool_month.map(target_days / pool_month.value_counts()).to_numpy()


def expected_annual_sums(daily: pd.DataFrame, fy: int) -> pd.Series:
    """Exact expected annual sums of the daily components: each pool day weighted by its expected draws.

    Every strategy cost is linear in these sums, so the expected cost has no sampling noise.
    """
    return daily.mul(expected_draws(daily.index, fy), axis=0).sum()


def annual_sums(daily: pd.DataFrame, day_index: np.ndarray) -> pd.DataFrame:
    """Sum daily components over each simulated year: one row per simulated year."""
    return pd.DataFrame(daily.to_numpy()[day_index].sum(axis=1), columns=daily.columns)
