"""Re-level historical 5-minute spot prices to the futures price of a target financial year."""
import numpy as np
import pandas as pd

# AEMC schedule of reliability settings 2026-27 is the latest published cap; FY28-FY30 caps are not set yet.
MARKET_PRICE_CAP = 23_200.0
MARKET_FLOOR = -1_000.0
# ASX Energy NSW base strip settles retrieved 28 Oct 2026; FY30 held at the FY29 settle (no quote shown).
FUTURES_PRICE = {2028: 99.44, 2029: 103.47, 2030: 103.47}


def _match_mean(spot_price: np.ndarray, target_price: float, method: str, weights: np.ndarray | None = None) -> np.ndarray:
    """Scale or shift prices so that, after clipping to floor and cap, their weighted mean is target_price."""
    def mean(prices: np.ndarray) -> float:
        return np.average(prices, weights=weights)

    adjust = target_price / mean(spot_price) if method == "scale" else target_price - mean(spot_price)
    for _ in range(100):
        moved = spot_price * adjust if method == "scale" else spot_price + adjust
        relevelled = np.clip(moved, MARKET_FLOOR, MARKET_PRICE_CAP)
        clipped_mean = mean(relevelled)
        if abs(clipped_mean - target_price) < 1e-6:
            return relevelled
        # Clipping pulls the mean away from target, so nudge the adjustment and clip again.
        adjust = adjust * target_price / clipped_mean if method == "scale" else adjust + target_price - clipped_mean
    raise RuntimeError(f"re-levelling to {target_price} did not converge")


def relevel(spot_price: pd.Series, fy: pd.Series, target_price: float, method: str = "scale") -> pd.Series:
    """Re-level each historical FY separately so its clipped mean equals target_price.

    method "scale" multiplies prices (base case); "shift" adds a constant (P95 sensitivity).
    Every interval is 5 minutes long, so the plain mean is the time-weighted mean a baseload future settles on.
    """
    return spot_price.groupby(fy).transform(lambda p: _match_mean(p.to_numpy(), target_price, method))


def calibrate(spot_price: pd.Series, weights: np.ndarray, target_price: float, method: str = "scale") -> pd.Series:
    """Adjust re-levelled prices once more so their mean, weighted as the bootstrap draws them, is target_price.

    The bootstrap weights months differently from history (July comes from two pool years, October from three),
    so per-FY re-levelling alone leaves the simulated mean price off the futures price.
    """
    return pd.Series(_match_mean(spot_price.to_numpy(), target_price, method, weights), index=spot_price.index)
