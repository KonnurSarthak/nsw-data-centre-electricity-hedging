"""Battery dispatch, daily cost components and the strategy cost formula."""
import numpy as np
import pandas as pd

INTERVALS_PER_HOUR = 12
BATTERY_MW = 20.0
BATTERY_MWH = 40.0
ROUND_TRIP_EFFICIENCY = 0.88
# CSIRO GenCost 2025-26: 2-hour battery $1,050/kW (2025).
BATTERY_CAPEX = BATTERY_MW * 1_000 * 1_050
# No citable O&M found; 2.5% of capex per year, 1.5-3.5% sensitivity (assumption 18).
BATTERY_OM_SHARE = 0.025
BATTERY_FADE = 0.02


def battery_dispatch(interval_start: pd.Series, spot_price: pd.Series) -> np.ndarray:
    """Battery net export in MW per interval: discharge positive, charging negative."""
    prices = pd.Series(spot_price.to_numpy(), index=pd.DatetimeIndex(interval_start))
    # closed="left" leaves the current interval out of its own window, so thresholds use past prices only.
    trailing = prices.rolling("7D", closed="left")
    # No thresholds until a full 7 days of history exists.
    warm_up = prices.index < prices.index[0] + pd.Timedelta(days=7)
    low = np.where(warm_up, np.nan, trailing.quantile(0.25).to_numpy())
    high = np.where(warm_up, np.nan, trailing.quantile(0.75).to_numpy())

    price = prices.to_numpy()
    day = prices.index.normalize().to_numpy()
    step_mwh = BATTERY_MW / INTERVALS_PER_HOUR
    net_mw = np.zeros(len(price))
    stored_mwh = 0.0
    discharged_today = 0.0
    for i in range(len(price)):
        if i == 0 or day[i] != day[i - 1]:
            discharged_today = 0.0
        # NaN thresholds compare False, so the battery idles during warm-up.
        if price[i] > high[i] and stored_mwh > 0 and discharged_today < BATTERY_MWH:
            # One cycle a day: discharge at most the battery's energy capacity per trading day.
            out_mwh = min(step_mwh, stored_mwh, BATTERY_MWH - discharged_today)
            stored_mwh -= out_mwh
            discharged_today += out_mwh
            net_mw[i] = out_mwh * INTERVALS_PER_HOUR
        elif price[i] < low[i] and stored_mwh < BATTERY_MWH:
            # Round-trip losses are taken on charging, so stored energy is what can later be sold.
            in_mwh = min(step_mwh, (BATTERY_MWH - stored_mwh) / ROUND_TRIP_EFFICIENCY)
            stored_mwh += in_mwh * ROUND_TRIP_EFFICIENCY
            net_mw[i] = -in_mwh * INTERVALS_PER_HOUR
    return net_mw


def daily_components(
    trading_date: pd.Series,
    spot_price: pd.Series,
    load_mw: pd.Series,
    solar_mw: pd.Series,
    battery_mw: np.ndarray,
) -> pd.DataFrame:
    """Per-day sums that every strategy cost is a linear combination of."""
    price = spot_price.to_numpy()
    load_mwh = load_mw.to_numpy() / INTERVALS_PER_HOUR
    solar_mwh = solar_mw.to_numpy() / INTERVALS_PER_HOUR
    # Settlement is suspended when spot < 0, so zero-price intervals still settle.
    settles = price >= 0
    parts = pd.DataFrame({
        "trading_date": trading_date.to_numpy(),
        "load_mwh": load_mwh,
        "spot_cost": load_mwh * price,
        "hours": 1 / INTERVALS_PER_HOUR,
        # Dollars paid by 1 MW of flat load: the floating leg of a baseload swap.
        "baseload_settlement_per_mw": price / INTERVALS_PER_HOUR,
        "solar_mwh": solar_mwh,
        "solar_value": solar_mwh * price,
        "solar_mwh_settled": solar_mwh * settles,
        "solar_value_settled": solar_mwh * price * settles,
        "battery_revenue": battery_mw / INTERVALS_PER_HOUR * price,
    })
    return parts.groupby("trading_date").sum()


def strategy_cost(
    parts: pd.DataFrame,
    futures_price: float,
    hedge_mw: float = 0.0,
    strike: float | None = None,
    suspend_negative: bool = False,
    battery_fade: float | None = None,
) -> pd.Series:
    """Cost of buying load at spot plus hedge and PPA settlements, less battery revenue.

    parts can be daily, monthly or simulated-annual sums of daily_components, because the cost is linear.
    battery_fade is the capacity factor applied to battery revenue; None means no battery.
    """
    cost = parts["spot_cost"] + hedge_mw * (futures_price * parts["hours"] - parts["baseload_settlement_per_mw"])
    if strike is not None:
        solar_mwh = parts["solar_mwh_settled"] if suspend_negative else parts["solar_mwh"]
        solar_value = parts["solar_value_settled"] if suspend_negative else parts["solar_value"]
        cost = cost + strike * solar_mwh - solar_value
    if battery_fade is not None:
        cost = cost - battery_fade * parts["battery_revenue"]
    return cost
