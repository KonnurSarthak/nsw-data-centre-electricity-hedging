-- Purpose: 5-minute calendar with the attributes the load profile and reporting need
-- Grain:   one row per 5-minute interval from 1 Oct 2021 to 30 Jun 2024, keyed by interval_start
-- Inputs:  none (generated)

create or replace view stg_calendar as
with interval_grid as (
    -- End bound is exclusive, so the last row starts at 23:55 on 30 Jun 2024
    select unnest(range(timestamp '2021-10-01 00:00', timestamp '2024-07-01 00:00', interval 5 minute)) as interval_start
)

select
    interval_start,
    cast(interval_start as date) as trading_date,
    -- Australian financial year: Jul 2021-Jun 2022 is FY2022
    case when month(interval_start) >= 7 then year(interval_start) + 1 else year(interval_start) end as fy,
    month(interval_start) as month,
    -- Seasons follow the PUE assumption: summer Dec-Feb, winter Jun-Aug, shoulder otherwise
    case
        when month(interval_start) in (12, 1, 2) then 'summer'
        when month(interval_start) in (6, 7, 8) then 'winter'
        else 'shoulder'
    end as season,
    -- Public holidays count as weekdays: data centre load does not follow the holiday calendar
    dayofweek(interval_start) in (0, 6) as is_weekend,
    -- Bands by interval start in market time; each band includes its start hour and excludes its end hour
    case
        when hour(interval_start) >= 8 and hour(interval_start) < 18 then 'day'
        when hour(interval_start) >= 22 or hour(interval_start) < 5 then 'night'
        else 'shoulder'
    end as tod_band
from interval_grid;
