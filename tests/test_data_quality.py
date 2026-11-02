"""Data-quality and reconciliation checks on the staged intervals and the re-levelled prices."""
import duckdb
import numpy as np
import pandas as pd
import pytest

from src import scenarios
from src.bootstrap import draw_years, expected_draws
from src.pricing import FUTURES_PRICE, MARKET_FLOOR, MARKET_PRICE_CAP, relevel
from src.staging import build_intervals
from src.strategies import daily_components

INTERVALS_PER_DAY = 288
# Analysis pool: 1 Oct 2021 to 30 Jun 2024 (FY2024 includes 29 Feb 2024).
DAYS_PER_FY = {2022: 273, 2023: 365, 2024: 366}


@pytest.fixture(scope="module")
def intervals():
    return scenarios.intervals()


def test_row_counts_per_fy(intervals):
    counts = intervals.groupby("fy").size()
    assert counts.to_dict() == {fy: days * INTERVALS_PER_DAY for fy, days in DAYS_PER_FY.items()}


def test_interval_start_is_unique_and_contiguous(intervals):
    assert intervals["interval_start"].is_unique
    assert (intervals["interval_start"].diff().dropna() == pd.Timedelta("5min")).all()


def test_every_trading_date_has_288_intervals(intervals):
    # The cost engine and the bootstrap index days by position, so a short day would shift every later day.
    assert (intervals.groupby("trading_date").size() == INTERVALS_PER_DAY).all()


def test_staging_joins_lose_no_rows_and_leave_no_nulls(intervals):
    prices = pd.read_parquet(scenarios.ROOT / "data" / "processed" / "nsw1_prices_5min.parquet")
    assert len(intervals) == len(prices)
    assert intervals[["spot_price", "solar_factor", "load_mw"]].notna().all().all()


def test_staging_sql_reproduces_the_saved_intervals_table():
    saved = pd.read_parquet(scenarios.INTERVALS_PATH)
    pd.testing.assert_frame_equal(build_intervals(), saved)


def test_prices_and_solar_factor_in_range(intervals):
    assert intervals["spot_price"].between(MARKET_FLOOR, MARKET_PRICE_CAP).all()
    assert intervals["solar_factor"].between(0, 1).all()


def test_spot_cost_reconciles_between_sql_and_pandas(intervals):
    prices = scenarios.scenario_price(2028)
    con = duckdb.connect()
    con.register("intervals", intervals.assign(relevelled_price=prices))
    # Load is rebuilt here from the documented profile (brief, Method notes), not from src/load.py.
    sql_total = con.sql("""
        select sum(
            50
            * case when is_weekend then 0.75 else 0.85 end
            * case tod_band when 'day' then 1.05 when 'night' then 0.97 else 1.00 end
            * case season when 'winter' then 1.20 when 'summer' then 1.35 else 1.27 end
            * relevelled_price / 12
        ) from intervals
    """).fetchall()[0][0]
    parts = daily_components(intervals["trading_date"], prices, intervals["load_mw"],
                             intervals["solar_mw"], np.zeros(len(intervals)))
    assert parts["spot_cost"].sum() == pytest.approx(sql_total, rel=1e-9)


@pytest.mark.parametrize("method", ["scale", "shift"])
@pytest.mark.parametrize("fy", scenarios.TARGET_FYS)
def test_relevelled_prices_stay_within_floor_and_cap(fy, method):
    prices = scenarios.scenario_price(fy, method=method)
    assert prices.min() >= MARKET_FLOOR
    assert prices.max() <= MARKET_PRICE_CAP


@pytest.mark.parametrize("fy", scenarios.TARGET_FYS)
def test_each_historical_fy_averages_the_futures_price_after_relevelling(intervals, fy):
    relevelled = relevel(intervals["spot_price"], intervals["fy"], FUTURES_PRICE[fy])
    assert relevelled.groupby(intervals["fy"]).mean().to_numpy() == pytest.approx(FUTURES_PRICE[fy], abs=1e-5)


@pytest.mark.parametrize("fy", scenarios.TARGET_FYS)
def test_bootstrap_weighted_mean_price_equals_futures_price(intervals, fy):
    dates = pd.DatetimeIndex(intervals["trading_date"].unique())
    weights = intervals["trading_date"].map(pd.Series(expected_draws(dates, fy), index=dates))
    weighted_mean = np.average(scenarios.scenario_price(fy), weights=weights)
    assert weighted_mean == pytest.approx(FUTURES_PRICE[fy], abs=1e-5)


@pytest.mark.parametrize("fy", scenarios.TARGET_FYS)
def test_simulated_mean_price_is_close_to_futures_price(fy):
    annual = scenarios.simulated_years(fy)
    simulated_mean = annual["price_mwh"].mean() / annual["hours"].mean()
    # 5,000 random years leave sampling noise: the seed check in the validation log has an SD of $0.10/MWh,
    # so $0.25 is about 2.5 SD. The exact weighted-mean test above guards the calibration itself.
    assert simulated_mean == pytest.approx(FUTURES_PRICE[fy], abs=0.25)


@pytest.mark.parametrize("fy", scenarios.TARGET_FYS)
def test_annual_load_matches_part_one(fy):
    annual_gwh = scenarios.simulated_years(fy)["load_mwh"].mean() / 1_000
    days = pd.Timestamp(f"{fy}-06-30") - pd.Timestamp(f"{fy - 1}-07-01") + pd.Timedelta(days=1)
    # 463-464 GWh holds for a 365-day year; a leap year has one more day (about 1.27 GWh).
    low, high = (463, 464) if days.days == 365 else (464, 465)
    assert low <= annual_gwh <= high


def test_historical_full_years_load_matches_part_one(intervals):
    annual_gwh = (intervals.groupby("fy")["load_mw"].sum() / 12 / 1_000).loc[[2023, 2024]]
    assert 463 <= annual_gwh[2023] <= 464
    assert 464 <= annual_gwh[2024] <= 465


def test_calendar_flags_follow_interval_start(intervals):
    start = intervals["interval_start"]
    hour = start.dt.hour
    # Load depends on these flags, so they are rebuilt here from the timestamp alone.
    assert intervals["is_weekend"].eq(start.dt.day_of_week >= 5).all()
    assert intervals["tod_band"].eq(np.select([hour.between(8, 17), (hour >= 22) | (hour < 5)], ["day", "night"], "shoulder")).all()
    assert intervals["season"].eq(np.select([start.dt.month.isin([12, 1, 2]), start.dt.month.isin([6, 7, 8])],
                                            ["summer", "winter"], "shoulder")).all()
    assert (intervals["trading_date"] == start.dt.normalize()).all()
    assert intervals["fy"].eq(np.where(start.dt.month >= 7, start.dt.year + 1, start.dt.year)).all()


def test_bootstrap_draw_frequencies_match_expected_draws():
    fy = 2028
    daily = scenarios.daily_parts(fy)
    drawn = np.bincount(draw_years(daily.index, fy).ravel(), minlength=len(daily)) / scenarios.simulated_years(fy).shape[0]
    relative_gap = np.abs(drawn / expected_draws(daily.index, fy) - 1)
    # Binomial noise at 5,000 years gives single-day gaps of a few percent; month-edge under-sampling was far larger.
    assert relative_gap.max() < 0.12
    assert relative_gap.mean() < 0.03
