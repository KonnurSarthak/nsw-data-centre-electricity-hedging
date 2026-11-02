"""Stylised 5-minute grid load profile for a 50 MW data centre."""
import pandas as pd

IT_CAPACITY_MW = 50
# Utilisation, intraday factors and PUE are stylised values informed by Uptime Institute (2023) and IEA data centre analysis.
UTILISATION = {False: 0.85, True: 0.75}  # keyed by is_weekend
INTRADAY_FACTOR = {"day": 1.05, "night": 0.97, "shoulder": 1.00}
# Cooling overhead rises with outside temperature, so PUE is highest in summer.
PUE = {"winter": 1.20, "shoulder": 1.27, "summer": 1.35}


def grid_mw(calendar: pd.DataFrame) -> pd.Series:
    """Grid load in MW per interval: IT capacity x utilisation x intraday factor x PUE.

    calendar needs the is_weekend, tod_band and season columns from sql/03_stg_calendar.sql.
    """
    return (
        IT_CAPACITY_MW
        # A 0/1 flag (e.g. read back from CSV) would not match the bool keys and map to NaN.
        * calendar["is_weekend"].astype(bool).map(UTILISATION)
        * calendar["tod_band"].map(INTRADAY_FACTOR)
        * calendar["season"].map(PUE)
    ).rename("load_mw")
