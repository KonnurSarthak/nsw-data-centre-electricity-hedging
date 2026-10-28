# Decision log

Every judgement call, newest at the bottom.

| Date | Decision | Options considered | Why this one | Area |
|---|---|---|---|---|
| 2026-10-28 | Business question: compare spot, futures hedge, battery and solar PPA + battery on expected and bad-year cost for a 50 MW NSW data centre | Question set directly from the capstone follow-up; no alternative questions generated | It revisits the one capstone result that looked too good (hedge saving millions every year) | Framing |
| 2026-10-28 | Horizon FY2028-FY2030 | FY2027-FY2030 (FY27 partly elapsed, only remaining quarters hedgeable); FY2028-FY2030 | Three full forward years, all quoted (or held flat) on ASX; avoids a part-year | Framing |
| 2026-10-28 | Re-level history by scaling: `p × F / mean(p_hist_FY)` per historical FY, time-weighted mean | Scale; additive shift | Keeps shape in relative terms and creates no artificial negative prices; shift kept as a P95 sensitivity because scaling shrinks crisis spikes | Method |
| 2026-10-28 | Bootstrap 7-day blocks drawn within the same calendar month | 1-day blocks within month; 7-day blocks within month | Whole days alone break multi-day spike events (e.g. June 2022); same-month draw keeps seasonality | Method |
| 2026-10-28 | Recommended hedge level = lowest level capturing 90% of the maximum P95 reduction | Knee rule; minimise P95 subject to an expected-cost tolerance | Easy to explain and needs no invented budget tolerance | Method |
| 2026-10-28 | Battery dispatch: charge below trailing 7-day 25th percentile, discharge above 75th, max 1 cycle/day | Rolling percentile thresholds; fixed time-of-day schedule from prior year | Uses past information only and still reacts to spikes | Method |
| 2026-10-28 | Solar PPA sized so peak solar output = average load | Peak = average load; 100% annual energy match | Never over-contracted, consistent with the hedge's risk logic | Method |
| 2026-10-28 | Main comparison: each strategy alone vs spot, plus one recommended package layering battery/PPA on the chosen hedge | Layered only; standalone only; standalone + one package | Standalone is easiest to compare; the package shows what a CFO would actually do | Method |
| 2026-10-28 | Bootstrap pool and xlsx reconciliation start 1 Oct 2021 | Start 1 Oct 2021; repeat 30-min prices across six 5-min intervals for Jul-Sep 2021 | 5-minute settlement began 1 Oct 2021; earlier files are 30-minute and would understate volatility | Data |
| 2026-10-28 | Hypothesis 1 framed as "if futures are fairly priced, hedging buys certainty, not savings" | Claim the capstone saving was wrong; frame as an implicit bet on futures being cheap | Re-levelling makes futures fair by construction, so the honest claim is about the assumption, tested with break-even and realised-vs-futures runs | Framing |
| 2026-10-28 | NPV discount rate 8%, sensitivity 6-10% | Keep 8%; try 6% and 10% as sensitivities | [TBD: cite a source for the base rate in build] | Method |
| 2026-10-28 | Load profile: utilisation 85% weekday / 75% weekend; intraday ×1.05 08:00-18:00, ×0.97 22:00-05:00; PUE 1.20 / 1.27 / 1.35 by season | Flat load; stylised profile with documented factors | Simple, explainable, and shows seasonal cooling cost; limitation notes hyperscale loads are often flatter | Method |
| 2026-10-28 | Battery NPV over 15-year life, 2%/yr fade, FY30 prices held flat after FY30, 8% discount rate | FY28-FY30 only (with or without residual value); full asset life | A 3-year window would unfairly ignore most of the asset's life | Method |
| 2026-10-28 | Missing sources (PPA strike, discount rate, battery O&M): search in build; if none are solid, keep the assumption with its sensitivity range | Delay until sourced; use weak source as fact; keep with range | Keeps the build moving without overstating certainty | Method |
| 2026-10-28 | v1 deliverables exclude Power BI | Include dashboard in v1; defer | Publish date 29 Oct 2026; README charts carry the story for v1 | Scope |
