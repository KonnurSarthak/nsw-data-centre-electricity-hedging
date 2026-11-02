-- purpose: typed 0-1 solar output factor of one NSW utility-scale farm
-- grain:   one row per 5-minute interval, keyed by interval_start (AEMO market time, AEST)
-- inputs:  data/processed/solar_factor_5min.csv.gz (built by src/clean.py)

create or replace view stg_solar_factor as
select
    cast(interval_start as timestamp) as interval_start,
    cast(solar_factor as double) as solar_factor
from read_csv('data/processed/solar_factor_5min.csv.gz', header = true);
