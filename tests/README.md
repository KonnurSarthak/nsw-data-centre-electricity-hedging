# Tests

Running `pytest` from the repo root runs all 56 tests. They read the processed data and the result tables, so the
pipeline has to run first.

- [`test_costs.py`](test_costs.py) checks the cost engine against a hand-worked example and against real historical days for every strategy. It also tests the battery's physical limits and confirms that a fresh run reproduces every table in `reports/tables/`.
- [`test_data_quality.py`](test_data_quality.py) checks the staged data: row counts, missing or duplicate intervals, prices within the market floor and cap, and that SQL and pandas give the same spot cost.
