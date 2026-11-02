"""Run every scenario and write the result tables to reports/tables/.

Usage from the project root: python -m src.scenarios
"""
from functools import cache
from pathlib import Path

import pandas as pd

from src.bootstrap import annual_sums, draw_years, expected_annual_sums, expected_draws
from src.load import grid_mw
from src.metrics import equivalent_annual_cost, npv, simple_payback, summarise
from src.pricing import FUTURES_PRICE, MARKET_FLOOR, MARKET_PRICE_CAP, calibrate, relevel
from src.strategies import (
    BATTERY_CAPEX, BATTERY_FADE, BATTERY_OM_SHARE, battery_dispatch, daily_components, strategy_cost,
)

ROOT = Path(__file__).resolve().parents[1]
INTERVALS_PATH = ROOT / "data" / "processed" / "intervals_5min.parquet"
TABLES_DIR = ROOT / "reports" / "tables"

TARGET_FYS = [2028, 2029, 2030]
# Above 100% the hedge sells surplus baseload; the curve shows where P95 stops falling.
HEDGE_LEVELS = [round(level / 10, 1) for level in range(14)]
COMPARISON_HEDGE_LEVELS = [0.8, 0.9, 1.0]
PPA_STRIKE = 65.0
PPA_STRIKES = [55.0, 60.0, 65.0, 70.0, 75.0]
DISCOUNT_RATE = 0.08
DISCOUNT_RATES = [0.06, 0.08, 0.10]
OM_SHARES = [0.015, 0.025, 0.035]
BATTERY_LIFE_YEARS = 15
REALISED_LEVELS = [0.8, 1.0, 1.2]
HEDGE_PRICE_LEVELS = [0.8, 0.9, 1.0, 1.1, 1.2]
CRISIS_START, CRISIS_END = pd.Timestamp("2022-05-01"), pd.Timestamp("2022-07-31")
TOP_SHARE = 0.01


@cache
def intervals() -> pd.DataFrame:
    """5-minute intervals with load and contracted solar output in MW."""
    table = pd.read_parquet(INTERVALS_PATH)
    table["load_mw"] = grid_mw(table)
    # The PPA is sized so peak solar output equals average load; the factor peaks at 1.
    table["solar_mw"] = table["solar_factor"] * table["load_mw"].mean()
    return table


def average_load_mw() -> float:
    return intervals()["load_mw"].mean()


def pool(exclude_crisis: bool = False) -> pd.DataFrame:
    table = intervals()
    # Dropped before re-levelling, so both runs average F and only the shape of the history differs.
    return table[~table["trading_date"].between(CRISIS_START, CRISIS_END)] if exclude_crisis else table


@cache
def scenario_price(fy: int, price_level: float = 1.0, method: str = "scale", exclude_crisis: bool = False) -> pd.Series:
    """Historical 5-minute prices re-levelled so the simulated FY averages price_level x F."""
    table = pool(exclude_crisis)
    target_price = FUTURES_PRICE[fy] * price_level
    dates = pd.DatetimeIndex(table["trading_date"].unique())
    weights = table["trading_date"].map(pd.Series(expected_draws(dates, fy), index=dates)).to_numpy()
    return calibrate(relevel(table["spot_price"], table["fy"], target_price, method), weights, target_price, method)


@cache
def daily_parts(fy: int, price_level: float = 1.0, method: str = "scale", exclude_crisis: bool = False) -> pd.DataFrame:
    """Daily cost components for one price scenario."""
    table = pool(exclude_crisis)
    spot_price = scenario_price(fy, price_level, method, exclude_crisis)
    battery_mw = battery_dispatch(table["interval_start"], spot_price)
    return daily_components(table["trading_date"], spot_price, table["load_mw"], table["solar_mw"], battery_mw)


@cache
def simulated_years(fy: int, price_level: float = 1.0, method: str = "scale", exclude_crisis: bool = False) -> pd.DataFrame:
    """Annual sums of daily components for the simulated years of target FY fy."""
    daily = daily_parts(fy, price_level, method, exclude_crisis)
    # Same pool gives the same draw, so every strategy and price level in a FY shares one set of years.
    return annual_sums(daily, draw_years(daily.index, fy))


@cache
def expected_parts(fy: int, price_level: float = 1.0, method: str = "scale", exclude_crisis: bool = False) -> pd.Series:
    """Exact expected annual sums for target FY fy (no sampling noise)."""
    return expected_annual_sums(daily_parts(fy, price_level, method, exclude_crisis), fy)


def monthly_parts(fy: int) -> pd.DataFrame:
    daily = daily_parts(fy)
    return daily.groupby([daily.index.year, daily.index.month]).sum()


def battery_fade(fy: int) -> float:
    # The battery starts on 1 July 2027, so FY28 is year 1 with no fade yet.
    return (1 - BATTERY_FADE) ** (fy - TARGET_FYS[0])


def battery_eac(om_share: float = BATTERY_OM_SHARE, rate: float = DISCOUNT_RATE) -> float:
    return equivalent_annual_cost(BATTERY_CAPEX, BATTERY_CAPEX * om_share, rate, BATTERY_LIFE_YEARS)


def evaluate(fy: int, futures_price: float, price_level: float = 1.0, method: str = "scale",
             exclude_crisis: bool = False, worst_month_parts: pd.DataFrame | None = None, **strategy) -> dict:
    """KPIs for one strategy in one price scenario: exact expected cost, simulated P95.

    A battery strategy carries its equivalent annual capex and O&M in every figure, so all columns share one basis.
    """
    case = (fy, price_level, method, exclude_crisis)
    capex = battery_eac() if strategy.get("battery_fade") is not None else 0.0
    simulated_cost = strategy_cost(simulated_years(*case), futures_price, **strategy) + capex
    expected = expected_parts(*case)
    row = summarise(simulated_cost, strategy_cost(expected, futures_price, **strategy) + capex, expected["load_mwh"])
    row["capex_m"] = capex / 1e6
    if worst_month_parts is not None:
        # Capex is spread evenly over the 12 months.
        row["worst_month_cost_m"] = (strategy_cost(worst_month_parts, futures_price, **strategy) + capex / 12).max() / 1e6
    return row


def hedge_curve() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Expected and P95 cost by hedge level, and the level with the lowest FY-average P95."""
    rows = []
    for fy in TARGET_FYS:
        for level in HEDGE_LEVELS:
            hedge_mw = level * average_load_mw()
            rows.append({"fy": fy, "hedge_pct": level * 100, "hedge_mw": hedge_mw,
                         **evaluate(fy, FUTURES_PRICE[fy], hedge_mw=hedge_mw)})
    curve = pd.DataFrame(rows)
    curve["p95_reduction_m"] = curve.groupby("fy")["p95_cost_m"].transform(lambda s: s.iloc[0] - s)
    # One level for all three years: the CFO signs one policy, so it uses the FY-average P95 curve.
    p95 = curve.groupby("hedge_pct")["p95_cost_m"].mean()
    min_p95_pct = p95.idxmin()
    recommendation = pd.DataFrame({
        "min_p95_hedge_pct": [min_p95_pct], "min_p95_hedge_mw": [min_p95_pct / 100 * average_load_mw()],
        "average_load_mw": [average_load_mw()],
        "fy_avg_p95_at_min_m": [p95.min()], "fy_avg_p95_unhedged_m": [p95.iloc[0]],
    })
    return curve, recommendation


def strategy_specs(min_p95_level: float) -> dict[str, dict]:
    recommended_mw = min_p95_level * average_load_mw()
    hedges = {f"hedge_{round(level * 100)}": {"hedge_mw": level * average_load_mw()} for level in COMPARISON_HEDGE_LEVELS}
    return {
        "spot": {},
        **hedges,
        "hedge_min_p95": {"hedge_mw": recommended_mw},
        "battery": {"battery_fade": 1.0},
        "ppa": {"strike": PPA_STRIKE},
        "ppa_suspend_negative": {"strike": PPA_STRIKE, "suspend_negative": True},
        "ppa_plus_battery": {"strike": PPA_STRIKE, "battery_fade": 1.0},
        "hedge_min_p95_plus_battery": {"hedge_mw": recommended_mw, "battery_fade": 1.0},
        "hedge_min_p95_plus_ppa": {"hedge_mw": recommended_mw, "strike": PPA_STRIKE},
    }


def with_fade(spec: dict, fy: int) -> dict:
    return {**spec, "battery_fade": battery_fade(fy)} if "battery_fade" in spec else spec


def strategy_table(specs: dict[str, dict], method: str = "scale", exclude_crisis: bool = False,
                   worst_month: bool = False) -> pd.DataFrame:
    rows = []
    for fy in TARGET_FYS:
        months = monthly_parts(fy) if worst_month else None
        for name, spec in specs.items():
            rows.append({"fy": fy, "strategy": name,
                         **evaluate(fy, FUTURES_PRICE[fy], method=method, exclude_crisis=exclude_crisis,
                                    worst_month_parts=months, **with_fade(spec, fy))})
    table = pd.DataFrame(rows)
    spot = table[table["strategy"] == "spot"].set_index("fy")
    table["expected_saving_vs_spot_m"] = table["fy"].map(spot["expected_cost_m"]) - table["expected_cost_m"]
    table["p95_reduction_vs_spot_m"] = table["fy"].map(spot["p95_cost_m"]) - table["p95_cost_m"]
    return table


def ppa_breakeven() -> pd.DataFrame:
    """Solar capture price and the PPA strike at which expected PPA settlement is zero, per FY."""
    rows = []
    for fy in TARGET_FYS:
        expected = expected_parts(fy)
        # Expected settlement K x solar MWh - solar value is zero at K = generation-weighted price.
        capture_price = expected["solar_value"] / expected["solar_mwh"]
        rows.append({"fy": fy, "futures_price": FUTURES_PRICE[fy], "solar_capture_price": capture_price,
                     "capture_ratio": capture_price / FUTURES_PRICE[fy],
                     "breakeven_strike_all_intervals": capture_price,
                     # With suspension only non-negative intervals settle, so break-even is their weighted price.
                     "breakeven_strike_suspend_negative": expected["solar_value_settled"] / expected["solar_mwh_settled"],
                     "assumed_strike": PPA_STRIKE})
    return pd.DataFrame(rows)


def add_ppa_breakeven(summary: pd.DataFrame, breakeven_strikes: pd.DataFrame) -> pd.DataFrame:
    """Attach capture price and the matching break-even strike to rows that hold a PPA."""
    by_fy = breakeven_strikes.set_index("fy")
    has_ppa = summary["strategy"].str.contains("ppa")
    suspended = summary["strategy"].str.contains("suspend_negative")
    summary["solar_capture_price"] = summary["fy"].map(by_fy["solar_capture_price"]).where(has_ppa)
    summary["ppa_breakeven_strike"] = summary["fy"].map(by_fy["breakeven_strike_all_intervals"]).where(has_ppa & ~suspended)
    summary.loc[suspended, "ppa_breakeven_strike"] = summary.loc[suspended, "fy"].map(by_fy["breakeven_strike_suspend_negative"])
    return summary


def package_rule(summary: pd.DataFrame, min_p95_level: float) -> tuple[pd.DataFrame, dict]:
    """Add the battery or PPA to the recommended hedge only if it lowers both expected cost and P95 (both incl. capex)."""
    average = summary.groupby("strategy")[["expected_cost_m", "p95_cost_m"]].mean()
    base = average.loc["hedge_min_p95"]
    rows = []
    for add_on in ["battery", "ppa"]:
        change = average.loc[f"hedge_min_p95_plus_{add_on}"] - base
        rows.append({"add_on": add_on,
                     "expected_change_m": change["expected_cost_m"],
                     "p95_change_m": change["p95_cost_m"],
                     "included": bool((change < 0).all())})
    rule = pd.DataFrame(rows)
    spec = dict(strategy_specs(min_p95_level)["hedge_min_p95"])
    if rule.loc[rule["add_on"] == "battery", "included"].item():
        spec["battery_fade"] = 1.0
    if rule.loc[rule["add_on"] == "ppa", "included"].item():
        spec["strike"] = PPA_STRIKE
    return rule, spec


def relevel_check() -> pd.DataFrame:
    rows = []
    table = intervals()
    for method in ["scale", "shift"]:
        for fy in TARGET_FYS:
            spot_price = scenario_price(fy, method=method)
            for hist_fy, prices in spot_price.groupby(table["fy"]):
                rows.append({"method": method, "target_fy": fy, "hist_fy": hist_fy,
                             "hist_mean": table.loc[prices.index, "spot_price"].mean(),
                             "relevelled_mean": prices.mean(), "min_price": prices.min(), "max_price": prices.max(),
                             "n_at_floor": int((prices <= MARKET_FLOOR).sum()),
                             "n_at_cap": int((prices >= MARKET_PRICE_CAP).sum())})
    return pd.DataFrame(rows)


def breakeven(min_p95_level: float) -> pd.DataFrame:
    rows = []
    for fy in TARGET_FYS:
        annual = simulated_years(fy)
        # Expected hedge payoff is zero where F x expected hours = expected sum of price x hours. Because prices
        # are calibrated to average F in the bootstrap, this equals F up to sampling noise.
        breakeven_price = annual["baseload_settlement_per_mw"].mean() / annual["hours"].mean()
        rows.append({"fy": fy, "futures_price": FUTURES_PRICE[fy], "breakeven_price": breakeven_price,
                     "breakeven_minus_futures": breakeven_price - FUTURES_PRICE[fy],
                     # Each $1/MWh that realised average spot ends above F pays the hedge holder hedge_mw x hours.
                     "payoff_m_per_dollar_min_p95": min_p95_level * average_load_mw() * annual["hours"].mean() / 1e6,
                     "payoff_m_per_dollar_100": average_load_mw() * annual["hours"].mean() / 1e6})
    return pd.DataFrame(rows)


def realised_vs_futures(min_p95_level: float) -> pd.DataFrame:
    rows = []
    for fy in TARGET_FYS:
        for level in REALISED_LEVELS:
            for name, hedge in [("spot", 0.0), ("hedge_min_p95", min_p95_level), ("hedge_100", 1.0)]:
                rows.append({"fy": fy, "realised_level": level, "realised_price": FUTURES_PRICE[fy] * level,
                             "strategy": name, **evaluate(fy, FUTURES_PRICE[fy], price_level=level,
                                                          hedge_mw=hedge * average_load_mw())})
    return pd.DataFrame(rows)


def hedge_price_sensitivity(min_p95_level: float) -> pd.DataFrame:
    rows = []
    for fy in TARGET_FYS:
        for level in HEDGE_PRICE_LEVELS:
            hedge_price = FUTURES_PRICE[fy] * level
            rows.append({"fy": fy, "hedge_price_level": level, "hedge_price": hedge_price, "strategy": "hedge_min_p95",
                         **evaluate(fy, hedge_price, hedge_mw=min_p95_level * average_load_mw())})
    return pd.DataFrame(rows)


def ppa_strike_sensitivity() -> pd.DataFrame:
    rows = []
    for fy in TARGET_FYS:
        spot = evaluate(fy, FUTURES_PRICE[fy])
        for strike in PPA_STRIKES:
            for settlement, suspend in [("all_intervals", False), ("suspend_negative", True)]:
                row = evaluate(fy, FUTURES_PRICE[fy], strike=strike, suspend_negative=suspend)
                rows.append({"fy": fy, "strike": strike, "settlement": settlement, **row,
                             "expected_saving_vs_spot_m": spot["expected_cost_m"] - row["expected_cost_m"],
                             "p95_reduction_vs_spot_m": spot["p95_cost_m"] - row["p95_cost_m"]})
    return pd.DataFrame(rows)


def battery_npv() -> pd.DataFrame:
    # Saving vs spot is the battery's expected revenue; years after FY30 hold the FY30 level.
    revenue = [expected_parts(fy)["battery_revenue"] for fy in TARGET_FYS]
    savings = revenue + [revenue[-1]] * (BATTERY_LIFE_YEARS - len(revenue))
    rows = []
    for rate in DISCOUNT_RATES:
        for om_share in OM_SHARES:
            annual_om = BATTERY_CAPEX * om_share
            rows.append({"discount_rate": rate, "om_share_of_capex": om_share, "capex_m": BATTERY_CAPEX / 1e6,
                         "annual_om_m": annual_om / 1e6, "year1_saving_m": savings[0] / 1e6,
                         "npv_m": npv(BATTERY_CAPEX, savings, annual_om, rate, BATTERY_FADE) / 1e6,
                         "simple_payback_years": simple_payback(BATTERY_CAPEX, savings, annual_om, BATTERY_FADE),
                         "equivalent_annual_cost_m": battery_eac(om_share, rate) / 1e6})
    return pd.DataFrame(rows)


def sensitivity_table(specs: dict[str, dict], **case) -> pd.DataFrame:
    table = strategy_table(specs, **case)
    table["cost_of_uncertainty_pct"] = table["cost_of_uncertainty_m"] / table["expected_cost_m"] * 100
    keep = ["fy", "strategy", "expected_cost_m", "p95_cost_m",
            "cost_of_uncertainty_m", "cost_of_uncertainty_pct"]
    return table[keep]


def crisis_diagnostics() -> pd.DataFrame:
    """Price level, spread and share of the most expensive intervals by month, on FY28 re-levelled prices."""
    table = intervals()
    prices = table.assign(relevelled_price=scenario_price(TARGET_FYS[0]))
    top_cut = prices["relevelled_price"].quantile(1 - TOP_SHARE)
    prices["in_top"] = prices["relevelled_price"] >= top_cut
    prices["at_300"] = prices["spot_price"] == 300
    monthly = prices.groupby(prices["interval_start"].dt.to_period("M")).agg(
        mean_price_hist=("spot_price", "mean"), mean_price_relevelled=("relevelled_price", "mean"),
        std_price_relevelled=("relevelled_price", "std"), max_price_relevelled=("relevelled_price", "max"),
        n_intervals_at_300=("at_300", "sum"), n_top_intervals=("in_top", "sum"),
    )
    monthly["share_of_top_intervals_pct"] = monthly["n_top_intervals"] / prices["in_top"].sum() * 100
    monthly["in_crisis_window"] = monthly.index.to_timestamp().to_series().between(CRISIS_START, CRISIS_END).to_numpy()
    return monthly.reset_index(names="month").assign(month=lambda m: m["month"].astype(str), top_price_cut=top_cut)


def main() -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    curve, recommendation = hedge_curve()
    min_p95_level = recommendation["min_p95_hedge_pct"].item() / 100
    specs = strategy_specs(min_p95_level)
    summary = strategy_table(specs, worst_month=True)
    rule, package = package_rule(summary, min_p95_level)
    summary = pd.concat([summary, strategy_table({"spot": {}, "package": package}, worst_month=True)
                         .query("strategy == 'package'")], ignore_index=True)

    ppa_strikes = ppa_breakeven()
    summary = add_ppa_breakeven(summary, ppa_strikes)

    core = {name: specs[name] for name in ["spot", "hedge_min_p95", "hedge_100", "battery", "ppa"]}
    crisis = pd.concat([sensitivity_table(core).assign(pool="all_days"),
                        sensitivity_table(core, exclude_crisis=True).assign(pool="excl_may_jul_2022")])
    shift = pd.concat([sensitivity_table(core).assign(method="scale"),
                       sensitivity_table(core, method="shift").assign(method="shift")])

    tables = {
        "relevel_check": relevel_check(),
        "hedge_curve": curve,
        "hedge_recommendation": recommendation,
        "strategy_summary": summary,
        "package_rule": rule,
        "ppa_breakeven": ppa_strikes,
        "hedge_breakeven": breakeven(min_p95_level),
        "realised_vs_futures": realised_vs_futures(min_p95_level),
        "hedge_price_sensitivity": hedge_price_sensitivity(min_p95_level),
        "ppa_strike_sensitivity": ppa_strike_sensitivity(),
        "crisis_sensitivity": crisis,
        "crisis_diagnostics": crisis_diagnostics(),
        "shift_sensitivity": shift,
        "battery_npv": battery_npv(),
    }
    for name, table in tables.items():
        table.round(4).to_csv(TABLES_DIR / f"{name}.csv", index=False)
    print(f"P95-minimising hedge level: {min_p95_level:.0%}; wrote {len(tables)} tables to {TABLES_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
