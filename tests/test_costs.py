"""Cost-engine checks: hand-worked numbers, interval-level recomputation, battery rules and table reproduction."""
import numpy as np
import pandas as pd
import pytest

from src import scenarios
from src.bootstrap import draw_years
from src.metrics import npv
from src.pricing import FUTURES_PRICE
from src.strategies import (
    BATTERY_MWH, BATTERY_MW, ROUND_TRIP_EFFICIENCY, battery_dispatch, daily_components, strategy_cost,
)

INTERVALS_PER_DAY = 288
HAND_CHECKED_DAY = pd.Timestamp("2023-01-15")
TOLERANCE = 1e-9


def test_cost_formulas_match_a_hand_worked_example():
    # Two 5-minute intervals, F = 100, hedge 48 MW, PPA strike 65. Every figure below was worked by hand.
    # Interval 1: price 120, load 60 MW (5 MWh), solar 24 MW (2 MWh), battery discharges 12 MW (1 MWh).
    # Interval 2: price -36, load 60 MW, solar 36 MW (3 MWh), battery charges 12 MW.
    parts = daily_components(
        pd.Series([pd.Timestamp("2023-01-01")] * 2),
        pd.Series([120.0, -36.0]), pd.Series([60.0, 60.0]), pd.Series([24.0, 36.0]), np.array([12.0, -12.0]),
    ).iloc[0]
    # spot: 5 x 120 + 5 x -36 = 420; hedge: 48 x (100 - 120) / 12 + 48 x (100 + 36) / 12 = -80 + 544 = 464
    assert strategy_cost(parts, 100.0) == pytest.approx(420)
    assert strategy_cost(parts, 100.0, hedge_mw=48) == pytest.approx(884)
    # PPA: 2 x (65 - 120) + 3 x (65 + 36) = -110 + 303 = 193; suspended below zero price: -110
    assert strategy_cost(parts, 100.0, strike=65) == pytest.approx(420 + 193)
    assert strategy_cost(parts, 100.0, strike=65, suspend_negative=True) == pytest.approx(420 - 110)
    # battery revenue: 1 x 120 + (-1) x -36 = 156, taken off cost; 2% fade leaves 98%
    assert strategy_cost(parts, 100.0, battery_fade=1.0) == pytest.approx(420 - 156)
    assert strategy_cost(parts, 100.0, hedge_mw=48, strike=65, battery_fade=0.98) == pytest.approx(884 + 193 - 152.88)


def test_battery_fade_follows_the_two_percent_a_year_rule():
    assert [scenarios.battery_fade(fy) for fy in scenarios.TARGET_FYS] == pytest.approx([1.0, 0.98, 0.9604])


def test_npv_matches_a_hand_worked_example():
    # capex 100, savings 50 a year for 2 years, O&M 10, rate 10%, fade 10%:
    # -100 + (50 - 10) / 1.1 + (45 - 10) / 1.21 = -34.7107
    assert npv(100, [50, 50], 10, 0.10, 0.10) == pytest.approx(-34.7107, abs=1e-4)


def interval_cost(price, load_mw, solar_mw, battery_mw, futures_price, hedge_mw=0.0, strike=None,
                  suspend_negative=False, battery_fade=None):
    """The brief's 5-minute interval cost, summed over the given intervals."""
    cost = load_mw * price / 12 + hedge_mw * (futures_price - price) / 12
    if strike is not None:
        settles = (price >= 0) if suspend_negative else np.ones(len(price), dtype=bool)
        cost = cost + solar_mw * (strike - price) / 12 * settles
    if battery_fade is not None:
        cost = cost - battery_fade * battery_mw * price / 12
    return cost.sum()


@pytest.fixture(scope="module")
def specs():
    # 100% of average load is the P95-minimising level in hedge_recommendation.csv.
    return scenarios.strategy_specs(1.0)


@pytest.fixture(scope="module", params=[2028, 2029])
def fy_case(request):
    fy = request.param
    table = scenarios.intervals()
    price = scenarios.scenario_price(fy)
    battery_mw = battery_dispatch(table["interval_start"], price)
    return fy, table, price.to_numpy(), battery_mw


def test_one_historical_day_matches_the_interval_formula_for_every_strategy(fy_case, specs):
    fy, table, price, battery_mw = fy_case
    rows = np.flatnonzero(table["trading_date"].to_numpy() == HAND_CHECKED_DAY.to_datetime64())
    assert len(rows) == INTERVALS_PER_DAY
    day = scenarios.daily_parts(fy).loc[HAND_CHECKED_DAY]
    for name, spec in specs.items():
        spec = scenarios.with_fade(spec, fy)
        expected = interval_cost(price[rows], table["load_mw"].to_numpy()[rows], table["solar_mw"].to_numpy()[rows],
                                 battery_mw[rows], FUTURES_PRICE[fy], **spec)
        assert strategy_cost(day, FUTURES_PRICE[fy], **spec) == pytest.approx(expected, rel=TOLERANCE), name


def test_one_simulated_year_matches_the_interval_formula_for_every_strategy(fy_case, specs):
    fy, table, price, battery_mw = fy_case
    daily = scenarios.daily_parts(fy)
    year = 7
    day_positions = draw_years(daily.index, fy)[year]
    # Each trading date holds 288 consecutive rows (checked in test_data_quality), so day p starts at row p x 288.
    rows = (day_positions[:, None] * INTERVALS_PER_DAY + np.arange(INTERVALS_PER_DAY)).ravel()
    assert pd.DatetimeIndex(table["trading_date"].to_numpy()[rows[::INTERVALS_PER_DAY]]).equals(daily.index[day_positions])
    annual = scenarios.simulated_years(fy).iloc[year]
    for name, spec in specs.items():
        spec = scenarios.with_fade(spec, fy)
        expected = interval_cost(price[rows], table["load_mw"].to_numpy()[rows], table["solar_mw"].to_numpy()[rows],
                                 battery_mw[rows], FUTURES_PRICE[fy], **spec)
        assert strategy_cost(annual, FUTURES_PRICE[fy], **spec) == pytest.approx(expected, rel=TOLERANCE), name


@pytest.mark.parametrize("fy", scenarios.TARGET_FYS)
def test_hedge_payoff_is_about_047_million_per_dollar(fy):
    futures_price = FUTURES_PRICE[fy]
    hedge_mw = scenarios.average_load_mw()
    low, high = scenarios.simulated_years(fy, 0.8), scenarios.simulated_years(fy, 1.2)

    def hedge_payoff(annual):
        # What the hedge pays: the spot bill less the hedged bill.
        return (strategy_cost(annual, futures_price) - strategy_cost(annual, futures_price, hedge_mw=hedge_mw)).mean()

    realised_gap = futures_price * (1.2 - 0.8)
    payoff_per_dollar = (hedge_payoff(high) - hedge_payoff(low)) / realised_gap / 1e6
    assert payoff_per_dollar == pytest.approx(0.47, abs=0.01)
    # Size of the hedge times hours in the year; the gap to the realised slope is sampling noise in the mean price.
    assert payoff_per_dollar == pytest.approx(hedge_mw * low["hours"].mean() / 1e6, abs=2e-3)


def test_battery_respects_its_physical_limits():
    prices = pd.Series(np.random.default_rng(1).gamma(2.0, 50.0, 30 * INTERVALS_PER_DAY))
    start = pd.Series(pd.date_range("2023-01-01", periods=len(prices), freq="5min"))
    net_mw = battery_dispatch(start, prices)
    assert np.abs(net_mw).max() <= BATTERY_MW + 1e-9
    step_mwh = net_mw / 12
    charged, discharged = -step_mwh[step_mwh < 0].sum(), step_mwh[step_mwh > 0].sum()
    # Losses are taken on charging, so energy sold is at most 88% of energy bought.
    assert discharged <= ROUND_TRIP_EFFICIENCY * charged + 1e-9
    stored = np.cumsum(np.where(step_mwh < 0, -step_mwh * ROUND_TRIP_EFFICIENCY, -step_mwh))
    assert stored.min() >= -1e-9 and stored.max() <= BATTERY_MWH + 1e-9
    daily_discharge = pd.Series(np.clip(step_mwh, 0, None)).groupby(start.dt.date).sum()
    assert daily_discharge.max() <= BATTERY_MWH + 1e-9


def test_battery_dispatch_uses_only_past_prices():
    rng = np.random.default_rng(2)
    prices = pd.Series(rng.gamma(2.0, 50.0, 20 * INTERVALS_PER_DAY))
    start = pd.Series(pd.date_range("2023-01-01", periods=len(prices), freq="5min"))
    cut = 12 * INTERVALS_PER_DAY
    changed = prices.copy()
    changed.iloc[cut:] = changed.iloc[cut:] * 10
    assert np.array_equal(battery_dispatch(start, prices)[:cut], battery_dispatch(start, changed)[:cut])


def test_package_row_equals_the_hundred_percent_hedge_because_no_add_on_is_included():
    summary = pd.read_csv(scenarios.TABLES_DIR / "strategy_summary.csv")
    rule = pd.read_csv(scenarios.TABLES_DIR / "package_rule.csv")
    assert not rule["included"].any()
    package = summary[summary["strategy"] == "package"].set_index("fy")
    hedge = summary[summary["strategy"] == "hedge_min_p95"].set_index("fy")
    cols = ["expected_cost_m", "p95_cost_m", "worst_month_cost_m"]
    pd.testing.assert_frame_equal(package[cols], hedge[cols])


def test_strategy_table_has_a_ppa_plus_battery_row_for_every_fy():
    summary = pd.read_csv(scenarios.TABLES_DIR / "strategy_summary.csv")
    rows = summary[summary["strategy"] == "ppa_plus_battery"]
    assert sorted(rows["fy"]) == scenarios.TARGET_FYS


def test_every_table_reproduces_from_a_clean_scenario_run(tmp_path, monkeypatch):
    committed = {path.name: pd.read_csv(path) for path in scenarios.TABLES_DIR.glob("*.csv")}
    # Cleared so the rerun recomputes from the processed data instead of reusing earlier results in this session.
    for cached in (scenarios.intervals, scenarios.scenario_price, scenarios.daily_parts, scenarios.simulated_years):
        cached.cache_clear()
    monkeypatch.setattr(scenarios, "TABLES_DIR", tmp_path)
    # main() prints the output folder relative to ROOT, which a temp folder is not under.
    monkeypatch.setattr(scenarios, "ROOT", tmp_path.parent)
    scenarios.main()
    rerun = {path.name: pd.read_csv(path) for path in tmp_path.glob("*.csv")}
    assert rerun.keys() == committed.keys()
    for name, table in committed.items():
        pd.testing.assert_frame_equal(rerun[name], table, obj=name)
