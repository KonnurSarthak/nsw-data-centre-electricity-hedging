-- purpose: one table per 5-minute interval joining calendar, spot price and solar factor for the cost engine
-- grain:   one row per 5-minute interval, keyed by interval_start
-- inputs:  stg_calendar, stg_prices, stg_solar_factor

create or replace view int_intervals as
select
    calendar.interval_start,
    calendar.trading_date,
    calendar.fy,
    calendar.month,
    calendar.season,
    calendar.is_weekend,
    calendar.tod_band,
    prices.spot_price,
    prices.region_demand_mw,
    prices.administered_period,
    solar.solar_factor
-- left joins from the full calendar so a missing interval shows up as a null instead of silently dropping out
from stg_calendar as calendar
left join stg_prices as prices
    on calendar.interval_start = prices.interval_start
left join stg_solar_factor as solar
    on calendar.interval_start = solar.interval_start
order by calendar.interval_start;
