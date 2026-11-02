-- Purpose: typed NSW1 spot prices and regional demand for the analysis pool
-- Grain:   one row per 5-minute interval, keyed by interval_start (AEMO market time, AEST)
-- Inputs:  data/processed/nsw1_prices_5min.parquet (built by src/clean.py)

create or replace view stg_prices as
select
    cast(interval_start as timestamp) as interval_start,
    cast(spot_price as double) as spot_price,
    cast(region_demand_mw as double) as region_demand_mw,
    -- June 2022 administered and suspension prices stay in the data; the flag lets charts and the crisis sensitivity find them
    cast(administered_period as boolean) as administered_period
from read_parquet('data/processed/nsw1_prices_5min.parquet');
