# Python code

The scripts run from the repo root as `python -m src.<name>`. Files are listed in the order they run. The modules
from `load.py` to `metrics.py` aren't run on their own; `scenarios.py` calls them.

- [`fetch_aemo.py`](fetch_aemo.py) downloads the monthly AEMO price and demand files into `data/raw/aemo/`.
- [`clean.py`](clean.py) applies the fixes from the data audit and writes clean five-minute tables to `data/processed/`.
- [`staging.py`](staging.py) runs the SQL in `sql/` and saves the joined interval table.
- [`load.py`](load.py) builds the data centre's grid load in MW for every interval.
- [`pricing.py`](pricing.py) re-levels historical prices so each year averages the futures price. The futures prices I used are here too.
- [`bootstrap.py`](bootstrap.py) builds simulated years by drawing 7-day blocks of real days from the same calendar month.
- [`strategies.py`](strategies.py) is the cost engine: when the battery charges and discharges, and what each strategy costs.
- [`metrics.py`](metrics.py) turns simulated costs into the KPIs from the project brief, and has the battery NPV and payback formulas.
- [`scenarios.py`](scenarios.py) runs every scenario and writes the 14 result tables to `reports/tables/`.
- [`seed_check.py`](seed_check.py) reruns the FY28 simulation with 20 different random seeds to see how much the results move by chance.
- [`viz.py`](viz.py) reads the tables and draws the six charts in `reports/figures/`.

[`profiling.py`](profiling.py) sits outside the pipeline. I used it in the data audit notebook to profile columns and
compare the AEMO download with a second export of the same prices.
