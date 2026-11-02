# Validation log

> Evidence that the numbers are right.

Each check is logged with date, check, expected, actual, result and notes, and every headline number
in the README is traced to the file that produced it.

| Date | Check | Expected | Actual | Result | Notes |
|---|---|---|---|---|---|
| 2026-11-02 | Re-levelled mean per historical FY (scale and shift) | Equals F after clipping | Matches to 1e-6 before calibration; scale never clips, shift clips 3 (FY22) and 8 (FY23) intervals at the floor | Pass | Cross-check; `relevel_check.csv` |
| 2026-11-02 | Daily-component cost engine vs the brief's 5-minute interval formula | Identical | Max difference 5e-10, with and without the negative-price PPA suspension | Pass | Cross-check |
| 2026-11-02 | Battery dispatch: state of charge, daily cycle, efficiency, look-ahead | SoC 0-40 MWh; at most 40 MWh discharged a day; discharged/charged = 0.88; no use of future prices | All hold; changing later prices leaves earlier dispatch unchanged; on 2022-06-10, 2023-01-15 and 2024-02-20 every charge and discharge matches thresholds recomputed from the prior 7 days | Pass | `test_battery_on_real_days_follows_the_trailing_percentile_rule`; fails if the 25th percentile is changed to the 45th |
| 2026-11-02 | Hedge break-even price vs F (FY28) | Close to F by construction | First run $101.45 vs $99.44 (month-edge under-sampling and pool mix); after wrap-around blocks and calibration $99.34 | Fail, fixed | `hedge_breakeven.csv`; decision log |
| 2026-11-02 | Seed sensitivity, FY28, 5,000 years, 20 seeds | Small next to findings | SD: spot expected $0.049M, spot P95 $0.132M, 100% hedge P95 $0.007M, break-even $0.10/MWh | Pass | |
| 2026-11-02 | NPV and equivalent annual cost by hand | Match code | NPV and EAC match the hand calculation | Pass | Cross-check |
| 2026-11-02 | Row counts per FY (`test_data_quality.py`) | FY22 273 days, FY23 365, FY24 366, each x 288 intervals | 78,624 / 105,120 / 105,408 rows (289,152 total) | Pass | Intervals unique and contiguous at 5 minutes; every trading date has 288 rows; the staging joins lose no rows and leave no nulls |
| 2026-11-02 | Staging SQL rebuild vs saved `intervals_5min.parquet` | Identical | Identical | Pass | |
| 2026-11-02 | Spot cost, SQL vs pandas (FY28 re-levelled prices) | Equal | Load rebuilt in DuckDB from the documented profile; matches `daily_components` to a relative 1e-9 | Pass | |
| 2026-11-02 | Re-levelled prices inside floor (-$1,000) and cap ($23,200), scale and shift, FY28-FY30 | All inside | All inside | Pass | |
| 2026-11-02 | Mean price equals F: per historical FY after re-levelling; bootstrap-weighted; simulated mean | 1e-5 for the first two; simulated within $0.35 | Simulated mean is $0.10 (FY28) and $0.19 (FY29, FY30) below F | Pass | The gap is sampling noise from 5,000 years; seed SD is $0.10 |
| 2026-11-02 | Annual load 463-464 GWh | 463-464 for a 365-day year | FY23 463.2; FY29 and FY30 simulated 463.1; leap years 464.3 (FY24) and 464.5 (FY28) | Pass, with note | A leap year adds one day, about 1.27 GWh, so the range is 464-465 for FY24 and FY28 |
| 2026-11-02 | Hedge payoff per $1/MWh realised spot is above F | About $0.47M | $0.4661M (FY28), $0.4648M (FY29, FY30); test recomputes it from simulated years at 80% and 120% realised price | Pass | |
| 2026-11-02 | Hand-worked 2-interval example (spot, hedge, PPA, PPA suspended, battery, combined) | 420; 884; 613; 310; 264; 924.12 | All six match | Pass | Worked on paper before running |
| 2026-11-02 | Historical day 2023-01-15 for every strategy, FY28 and FY29 prices | Brief's 5-minute interval formula | Match to a relative 1e-9 for 11 strategy specs | Pass | |
| 2026-11-02 | One simulated year (year 7 of the draw) for every strategy, FY28 and FY29 | Interval formula summed over the drawn days | Match to a relative 1e-9 for 11 strategy specs | Pass | Checks the daily aggregation and the bootstrap day mapping |
| 2026-11-02 | Battery limits on synthetic prices | Power within 20 MW; stored energy 0-40 MWh; at most 40 MWh sold a day; energy sold at most 88% of energy bought; no look-ahead | All hold | Pass | Also tested: raising prices after day 12 leaves days 1-12 unchanged |
| 2026-11-02 | NPV by hand (2-year example) | -34.7107 | -34.7107 | Pass | |
| 2026-11-02 | Strategy table contains `ppa_plus_battery` for FY28-FY30; package row equals the 100% hedge row | Present; equal | Present; equal (neither add-on passes the rule) | Pass | |
| 2026-11-02 | All 14 tables in `reports/tables` reproduce from a clean `python -m src.scenarios` run (caches cleared) | Identical | Identical | Pass | About 14 s |
| 2026-11-02 | Mutation check: reverse the hedge sign; raise winter PUE from 1.20 to 1.25 | Tests fail | Hand-worked example failed; 6 tests failed | Pass | Source restored after each |
| 2026-11-02 | Audit finding: spot expected cost is $0.047M below its exact expectation; the hedge "cost" of $0.049M and the break-even gap of -$0.10 / -$0.19 per MWh are bootstrap noise | Differences under $0.1M are noise | Spot minus hedge of -$0.0486M equals the break-even gap x $0.4661M; the hedge saving is zero in expectation | Noted | Assumption 27; findings must not present a sub-$0.1M gap as a result |
| 2026-11-02 | Audit finding: tests reused `with_fade` and `expected_draws` on both sides | Independent checks | Added a hard-coded fade test (1, 0.98, 0.9604), a draw-frequency test against `expected_draws`, a calendar-flag test rebuilt from `interval_start`, a tighter simulated-mean tolerance ($0.25) and a payoff test against hedge MW x hours | Fixed | 43 tests pass |
| 2026-11-02 | Audit finding: crisis exclusion rests on thin pool data (July from one year) and the change is about one seed SD | "Does not lower" holds | Cost of uncertainty 15.66% vs 15.96% of expected | Noted | Word as "no reduction", not "rises" |
| 2026-11-02 | Audit finding: P95 excludes battery capex while expected cost incl. capex includes it | Columns labelled | `p95_cost_m` is before capex | Noted | Label the columns in the README and findings |
| 2026-11-02 | Exact expected cost vs interval formula weighted by expected draws, every strategy, FY28 and FY29 (`test_costs.py`) | Equal | Match to a relative 1e-9 for 11 strategy specs, battery rows including capex | Pass | Independent of `expected_parts`: weights each 5-minute interval cost by its day's expected draws |
| 2026-11-02 | Exact expected cost vs simulated mean (spot, FY28-FY30) | Within sampling noise | Within $0.15M (three seed SDs) | Pass | |
| 2026-11-02 | Every hedge level has the spot expected cost | Equal to within $0.001M | Equal | Pass | Replaces the earlier $0.049M hedge "cost", which was seed noise |
| 2026-11-02 | Battery capex on one basis: equivalent annual cost by hand; expected, P95 and cost of uncertainty | $21.0M / 8.5595 + $0.525M = $2.9784M; P95 shifts by the same amount; spread unchanged | $2.9784M; P95 = P95 before capex + $2.9784M; cost of uncertainty unchanged | Pass | |
| 2026-11-02 | Mutation: drop capex from the exact expected cost | Test fails | `test_exact_expected_cost_matches_the_interval_formula...` failed | Pass | Source restored |
| 2026-11-02 | Full suite after the switch to exact expected cost and common-basis capex; all 14 tables regenerated | All pass | 50 tests pass; tables identical on a clean rerun | Pass | Spot FY28 expected $45.90M (was $45.85M simulated); battery strategy $47.50M incl. $2.98M capex; PPA break-even $53.41 / $66.99; battery NPV -$14.62M and payback 29.5 years unchanged to the stated precision |
| 2026-11-02 | Supersedes the audit notes above: the sampling-noise finding (spot expected $0.047M off) and the P95-vs-capex basis finding | Resolved | Expected cost is exact; P95 includes capex | Fixed | See decision log |
| 2026-11-02 | Full suite after adding the real-day battery test | All pass | 56 tests pass | Pass | Three real days, each run for FY28 and FY29 prices |
