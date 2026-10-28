# Project brief

**Powering a 50 MW Data Centre in NSW: What Does Electricity Really Cost, and What Can Go Wrong?**
*Capstone project, Master of Business Analytics, final semester (2026)*

## Business question
For a 50 MW data centre in NSW, how do buying at spot, hedging with futures, adding a battery, or
contracting solar compare on what electricity usually costs, and what it costs in a bad year, over
the next three financial years (FY2028-FY2030)?

## Stakeholder and decision
- **Stakeholder:** the data centre's CFO / energy procurement lead
- **Decision this supports:** procurement strategy, how much of the load to hedge, and whether a
  battery or a solar contract is worth it

## Success metric / KPIs
Energy per 5-minute interval: MWh = MW / 12. `F` = futures price for the FY, `K` = PPA strike price.

| KPI | Exact formula | Grain |
|---|---|---|
| Interval cost ($) | `load_MW × price / 12` + hedge settlement `hedge_MW × (F − price) / 12` + PPA settlement `solar_MW × (K − price) / 12` − battery net revenue | 5-min interval × strategy |
| Expected annual cost ($M) | mean of simulated annual costs across N bootstrap years | strategy × FY |
| Effective price ($/MWh) | expected annual cost / annual load MWh | strategy × FY |
| Bad-year cost ($M) | 95th percentile (P95) of simulated annual costs | strategy × FY |
| Cost of uncertainty ($M) | P95 − expected annual cost | strategy × FY |
| Worst-month cost ($M) | highest calendar-month cost in the re-levelled historical series | strategy |
| NPV ($M, capex options only) | `−capex + Σ_{t=1..15} (saving_t × 0.98^(t−1) − O&M_t) / (1 + r)^t`, where saving = spot cost − strategy cost; 15-year asset life, 2%/yr capacity fade, prices held at the FY30 level after FY30, r = 8% (6-10% sensitivity) | strategy |
| Simple payback (years, capex options only) | capex / average annual saving after O&M | strategy |
| Hedge break-even futures price ($/MWh) | futures price `F` at which expected hedged cost = expected spot cost | FY |

All strategies are costed on the **same** simulated days in each bootstrap run, so differences
between strategies come from the strategy, not from luck in the draw.

## Hypotheses
1. **If futures are fairly priced, hedging buys certainty, not savings.** Re-levelling historical
   prices to the futures curve makes futures fair by construction, so the hedge's expected saving
   should be close to zero while its P95 cost falls sharply. The capstone's multi-million annual
   saving is explained as an implicit bet that futures were cheap relative to future spot
   (today's futures compared against crisis-era spot). The analysis shows the break-even futures
   price and what the hedge does when realised spot ends up above or below futures.
2. Because load is nearly flat, most of the bad-year reduction comes from hedging up to about 100%
   of average load; the curve flattens before that point.
3. A battery dispatched on past information only does not pay back at forward price levels; its
   value shows up mainly in worst-month cost rather than expected cost.
4. A solar PPA's expected value depends on the strike versus solar's capture price (below the
   baseload price because midday prices are low); the solar/flat-load mismatch can add risk.
5. Bad-year cost is driven mainly by May-July 2022, so P95 falls noticeably when it is excluded.

## Context (sourced)
- ASX Energy NSW base strip settles, retrieved 28 Oct 2026: FY28 $99.44/MWh, FY29 $103.47/MWh,
  CY29 $104.85/MWh; no FY30 quote shown.
  [ASX Energy](https://www.asxenergy.com.au/futures/au_electricity)
- NSW $300 cap strip, FY28 settle $16.61/MWh (retrieved 28 Oct 2026): the market's price for
  spike protection. Same source.
- CSIRO GenCost 2025-26: 2-hour battery capital cost $1,050/kW in 2025, down 15% in the latest year.
  [GenCost 2025-26](https://www.csiro.au/-/media/Energy/GenCost-2025-26-Draft/GenCost2025-26ConsultDraft_20251216-FINAL.pdf)
  [TBD: replace with the final report and take O&M from the GenCost data tables]
- Solar PPA strike: [TBD: strong source]. Fallback is a $55-75/MWh sensitivity range; quotes that
  include LGCs overstate an energy-only strike.

## Scope
- **In:** wholesale energy cost only, NSW1 region, 5-minute resolution for all cost calculations
  (half-hourly only for charts and profiles). FY2022-FY2024 history (pool from 1 Oct 2021)
  re-levelled to FY2028-FY2030 futures. Four strategies plus one recommended package. Hedge-level
  curve 0-100% of average load, hedge-price and PPA-strike sensitivities, results with and without
  May-July 2022.
- **Out:** network charges, retail margin, loss factors, LGC and environmental charges (stated as
  excluded). Possible extensions: 10-year NSW demand-growth scenarios, a detailed price-impact
  regression, carbon shadow pricing, Power BI dashboard (planned after v1).

## Strategies
1. **Spot:** buy all load at 5-minute spot.
2. **Futures hedge:** baseload swap (contract for difference) at `F`. Hedge-level curve from 0-100%
   of average load (expected vs bad-year cost). Recommended level = lowest level that captures 90%
   of the maximum P95 reduction.
3. **Battery:** about 20 MW / 40 MWh, 88% round-trip efficiency, capex and O&M from CSIRO GenCost.
   Dispatch uses past information only: charge below the trailing 7-day 25th percentile price,
   discharge above the 75th, at most one cycle per day.
4. **Solar PPA + battery:** virtual PPA settled against spot (no on-site capex), contracted so
   peak solar output equals average load; strike-price sensitivity.

Main comparison: each strategy alone against spot. Plus one **recommended package** row that layers
the battery and/or PPA on top of the chosen hedge level.

## Method notes
- **Re-levelling (scale):** `p_adj = p × F_FY / mean(p_hist_FY)`, per historical FY, using the
  time-weighted mean (baseload futures are time-weighted). Sensitivity on P95: additive shift
  `p_adj = p + (F_FY − mean(p_hist_FY))`.
- **Bootstrap:** 7-day blocks drawn from the same calendar month, which keeps multi-day spike
  events and seasonality.
- **Realised-vs-futures test:** re-run with realised spot set above and below `F` to show what the
  hedge does when futures turn out cheap or expensive.
- **Load profile:** `grid_MW = 50 × utilisation × intraday factor × PUE`. Utilisation 85% weekdays,
  75% weekends; intraday factor 1.05 for 08:00-18:00, 0.97 for 22:00-05:00, 1.00 otherwise; PUE 1.20
  winter (Jun-Aug), 1.27 shoulder (Mar-May, Sep-Nov), 1.35 summer (Dec-Feb). Informed by the Uptime
  Institute Global Data Center Survey 2023 and IEA data centre energy analysis.

## Data
- **Price and demand:** AEMO Aggregated Price and Demand, NSW1, July 2021-June 2024, downloaded by
  script from the [AEMO aggregated data page](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/aggregated-data)
  (`PRICE_AND_DEMAND_YYYYMM_NSW1.csv`). Reconciled against the local xlsx export from 1 Oct 2021
  only (pre-5-minute-settlement files are 30-minute).
- **Solar:** 5-minute dispatch of an existing NSW utility-scale solar farm (102 MW, AEMO dispatch
  data), converted to a normalised 0-1 output factor. Only the factor is committed; the farm is not named.
- **Date range:** analysis pool 1 Oct 2021-30 Jun 2024.
- **Licence:** raw files are not committed (gitignored); a fetch script reproduces the price data.
  [TBD: confirm AEMO copyright permissions in the data audit]

## Limitations (known up front)
- About 3 years of history means P95 is drawn from a small number of seasons; a bad year worse
  than anything in FY22-FY24 is not represented.
- Re-levelling by scaling shrinks crisis-era spikes in proportion; the shift sensitivity tests this.
- FY30 is held flat at the FY29 settle (no FY30 quote on the retrieval date).
- The load profile is stylised. Hyperscale data centre loads are often flatter than this, which
  would make a baseload hedge fit even more closely.
- Battery NPV runs 15 years but prices are only observed to FY30; later years assume FY30 levels.
- Wholesale energy only; the total bill is higher.

## Deliverables (v1)
- [ ] SQL + Python pipeline
- [ ] Validated metrics
- [ ] Findings report (`reports/findings.md`)
- [ ] README that passes the 30-second test, with 5-6 takeaway-titled charts
- Later add-on: Power BI dashboard + screenshots

## Timeline
Build 28 Oct 2026 (evening); publish 29 Oct 2026.

## Analysis plan
1. **Fetch and reconcile (Python):** download AEMO CSVs, reconcile against the xlsx from 1 Oct 2021.
2. **Audit:** gaps, duplicates, interval resolution, price cap/floor events, solar data quality.
3. **Staging (SQL, DuckDB):** one model per file for prices, solar factor and calendar.
4. **Load profile (Python, `src/`):** utilisation × seasonal PUE at 5-minute resolution.
5. **Re-level prices (Python, `src/`):** scale to FY28-FY30 futures; shift version for sensitivity.
6. **Strategy cost engine (Python, `src/`):** spot, hedge, battery, PPA at 5-minute resolution.
7. **Bootstrap (Python, `src/`):** 7-day same-month blocks giving expected, P95 and worst-month cost.
8. **Scenarios:** hedge-level curve, break-even price, realised-vs-futures, hedge-price and strike
   sensitivities, with/without May-July 2022, recommended package.
9. **Validate:** reconciliations, hand-checked days, break-even check, logged in `docs/validation-log.md`.
10. **Report:** findings write-up and 5-6 takeaway-titled charts for the README.
