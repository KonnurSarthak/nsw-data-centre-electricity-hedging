"""Rerun the FY28 bootstrap over many seeds to size the sampling noise in the simulated figures.

Usage from the project root: python -m src.seed_check
"""
import pandas as pd

from src import scenarios
from src.bootstrap import N_YEARS, annual_sums, draw_years
from src.pricing import FUTURES_PRICE
from src.strategies import strategy_cost

FY = 2028
SEEDS = range(20)


def seed_sensitivity(n_years: int = N_YEARS) -> pd.DataFrame:
    """One row per seed: the simulated mean, P95 and break-even price for FY28."""
    daily = scenarios.daily_parts(FY)
    futures_price = FUTURES_PRICE[FY]
    hedge_mw = scenarios.average_load_mw()
    rows = []
    for seed in SEEDS:
        annual = annual_sums(daily, draw_years(daily.index, FY, n_years, seed))
        spot = strategy_cost(annual, futures_price)
        hedged = strategy_cost(annual, futures_price, hedge_mw=hedge_mw)
        rows.append({
            "seed": seed,
            "spot_mean_m": spot.mean() / 1e6,
            "spot_p95_m": spot.quantile(0.95) / 1e6,
            "hedge_100_p95_m": hedged.quantile(0.95) / 1e6,
            "breakeven_price": annual["baseload_settlement_per_mw"].mean() / annual["hours"].mean(),
        })
    return pd.DataFrame(rows)


def main() -> None:
    table = seed_sensitivity()
    table.round(4).to_csv(scenarios.TABLES_DIR / "seed_sensitivity.csv", index=False)
    spread = table.drop(columns="seed").std()
    print(f"seed SD over {len(table)} seeds: " + ", ".join(f"{name} {value:.3f}" for name, value in spread.items()))


if __name__ == "__main__":
    main()
