# Data dictionary

All timestamps are in NEM time (AEST, UTC+10, no daylight saving) and mark the **end** of the
interval. A timestamp of 00:00 belongs to the previous day.

## AEMO aggregated price and demand (`data/raw/aemo/PRICE_AND_DEMAND_YYYYMM_NSW1.csv`)
Source of truth for prices. Downloaded by `src/fetch_aemo.py` from the
[AEMO aggregated data page](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/aggregated-data).
Licence: [AEMO Copyright Permissions](https://www.aemo.com.au/privacy-and-legal-notices/copyright-permissions)
allow use for any purpose with accurate attribution to AEMO.

- **Grain:** one row per region per trading interval. 30-minute intervals up to 1 Oct 2021, 5-minute after (5-minute settlement start).
- **Primary key:** `REGION` + `SETTLEMENTDATE` (unique: 0 duplicates)
- **Rows:** 293,568 for Jul 2021-Jun 2024 (4,416 half-hours to 1 Oct 2021 00:00, then 289,152 five-minute intervals). No missing or off-grid intervals.

| Column | Type | Description | Example | Issues found |
|---|---|---|---|---|
| REGION | text | NEM region code | NSW1 | Single value |
| SETTLEMENTDATE | datetime (`YYYY/MM/DD HH:MM:SS`) | Interval end time | 2021/10/01 00:05:00 | Interval-ending; last row is 2024/07/01 00:00:00, which belongs to 30 Jun 2024 |
| TOTALDEMAND | float, MW | NSW regional demand | 7263.77 | None; range 3,664-13,764 MW. Context only, not used for site cost |
| RRP | float, $/MWh | Regional reference (spot) price | 43.64 | Range -1,000 (floor) to 16,600 (cap); 4.39% of 5-min intervals negative; June 2022 administered price cap ($300) and market suspension visible |
| PERIODTYPE | text | Interval type | TRADE | Single value |

## Local price and demand export (`data/raw/NSW Price and Demand 20210701_20240630.xlsx`, sheet `in`)
Used only to reconcile the AEMO download.

- **Grain:** one row per 5-minute dispatch interval, Jul 2021-Jun 2024 (5-minute rows even before 1 Oct 2021).
- **Primary key:** `SETTLEMENTDATE`
- **Rows:** 315,646 (2 intervals missing: 2023-12-05 13:45 and 13:50 interval-end).

| Column | Type | Description | Example | Issues found |
|---|---|---|---|---|
| SETTLEMENTDATE | datetime | Interval end minus 1 second | 2021-07-01 00:04:59 | All timestamps end in :59; round up to the minute to align with AEMO |
| NSW1_Price | float, $/MWh | 5-minute price | 96.93584 | From 1 Oct 2021 matches AEMO RRP on all 289,150 shared intervals (max abs diff $0.005). Before then these are dispatch prices; their half-hour mean matches AEMO's 30-minute trading price |
| NSW1_Demand | float, MW | NSW demand | 8388.62 | Matches AEMO TOTALDEMAND exactly from 1 Oct 2021 |

## Solar farm dispatch (`data/raw/Solar Farm Dispatch Data.xlsx`, sheet `in`)
5-minute output of an existing 102 MW NSW utility-scale solar farm (AEMO dispatch data). Only a
normalised 0-1 factor is committed.

- **Grain:** one row per 5-minute interval, Jul 2021-Jun 2024
- **Primary key:** `SETTLEMENTDATE`
- **Rows:** 315,646 (same 2 missing intervals as the price export, both around midday)

| Column | Type | Description | Example | Issues found |
|---|---|---|---|---|
| SETTLEMENTDATE | datetime | Interval end minus 1 second | 2021-07-01 00:04:59 | Same :59 convention as the price export |
| Solar Farm Output | float, MW | Farm output | 0 | Range 0-102 MW (flat-tops at 102 MW); no negatives; no output 22:00-04:00. 53.1% of intervals are zero (night). Capacity factor 24.0% / 24.3% / 24.9% (FY22/FY23/FY24). 12 days with midday (10:00-15:00) max below 5 MW, including a 7-day run 27 Apr-3 May 2023 at normal prices, which looks like an outage |

## Processed tables (written by `src/clean.py`)
Both are keyed by `interval_start` (interval end − 5 minutes), 1 Oct 2021 00:00 to 30 Jun 2024 23:55, 289,152 rows, no nulls.

`data/processed/nsw1_prices_5min.parquet` (not committed; rebuild with `python -m src.clean`)

| Column | Type | Description | Example | Issues found |
|---|---|---|---|---|
| interval_start | datetime | Start of the 5-minute interval | 2021-10-01 00:00 | None |
| spot_price | float, $/MWh | AEMO RRP, unchanged | 43.64 | Spikes kept |
| region_demand_mw | float, MW | AEMO TOTALDEMAND, context only | 7263.77 | None |
| fy | int | Australian financial year of interval start | 2022 | FY2022 covers 1 Oct 2021-30 Jun 2022 only |
| administered_period | bool | 13 Jun 2022 00:00 to 24 Jun 2022 14:00 (administered price cap and market suspension) | False | 3,336 intervals flagged |

`data/processed/solar_factor_5min.csv.gz` (committed, gzip-compressed CSV; `pd.read_csv` reads it directly)

| Column | Type | Description | Example | Issues found |
|---|---|---|---|---|
| interval_start | datetime | Start of the 5-minute interval | 2021-10-01 00:00 | None |
| solar_factor | float, 0-1 | Farm output / 102 MW, rounded to 4 decimals | 0.9747 | 2 missing intervals filled linearly; outage days kept |

## Join: prices × solar
On interval-end timestamp from 1 Oct 2021: all 289,152 price intervals match except the 2 missing solar intervals.
No evidence of solar curtailment at negative prices: midday output averages 89.1 MW when price < 0 vs 76.7 MW otherwise
(negative prices happen on sunny days).
