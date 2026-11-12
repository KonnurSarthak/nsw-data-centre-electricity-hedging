# SQL

These four queries run on DuckDB in number order. I don't run them by hand: `python -m src.staging` runs each file
and saves the final table to `data/processed/intervals_5min.parquet`.

- [`01_stg_prices.sql`](01_stg_prices.sql) reads the cleaned NSW spot prices and demand, one row per five-minute interval.
- [`02_stg_solar_factor.sql`](02_stg_solar_factor.sql) does the same for the solar farm's output, stored as a share of capacity between 0 and 1.
- [`03_stg_calendar.sql`](03_stg_calendar.sql) generates every five-minute interval from Oct 2021 to Jun 2024 with the date fields the load profile and reports need.
- [`04_int_intervals.sql`](04_int_intervals.sql) joins prices and solar onto the calendar. Everything after the SQL reads this table.
