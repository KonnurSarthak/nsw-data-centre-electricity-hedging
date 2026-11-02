"""KPI formulas from docs/project-brief.md."""
import pandas as pd

BAD_YEAR_QUANTILE = 0.95


def summarise(simulated_cost: pd.Series, expected_cost: float, expected_load_mwh: float) -> dict:
    """Expected cost, effective price, P95 and cost of uncertainty ($M, $/MWh).

    expected_cost is the exact expectation (no sampling noise); P95 comes from the simulated annual costs.
    Both must already include any equivalent annual capex, so they sit on the same basis.
    """
    p95 = simulated_cost.quantile(BAD_YEAR_QUANTILE)
    return {
        "expected_cost_m": expected_cost / 1e6,
        "effective_price": expected_cost / expected_load_mwh,
        "p95_cost_m": p95 / 1e6,
        "cost_of_uncertainty_m": (p95 - expected_cost) / 1e6,
    }


def annuity_factor(rate: float, years: int) -> float:
    """Present value of $1 a year for `years` years at `rate`."""
    return (1 - (1 + rate) ** -years) / rate


def equivalent_annual_cost(capex: float, annual_om: float, rate: float, years: int) -> float:
    """Capex spread evenly over the asset life at `rate`, plus annual O&M."""
    return capex / annuity_factor(rate, years) + annual_om


def npv(capex: float, savings: list[float], annual_om: float, rate: float, fade: float) -> float:
    """-capex + sum over t of (saving_t x (1 - fade)^(t-1) - O&M) / (1 + rate)^t; savings[0] is year 1."""
    return -capex + sum(
        (saving * (1 - fade) ** (t - 1) - annual_om) / (1 + rate) ** t
        for t, saving in enumerate(savings, start=1)
    )


def simple_payback(capex: float, savings: list[float], annual_om: float, fade: float) -> float:
    """Capex divided by the average annual saving after fade and O&M (years); inf if that saving is not positive."""
    net = [saving * (1 - fade) ** (t - 1) - annual_om for t, saving in enumerate(savings, start=1)]
    average = sum(net) / len(net)
    return capex / average if average > 0 else float("inf")
