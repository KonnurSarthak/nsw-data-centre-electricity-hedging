# Validation log

> Evidence that the numbers are right.

Each check is logged with date, check, expected, actual, result and notes, and every headline number
in the README is traced to the file that produced it.

| Date | Check | Expected | Actual | Result | Notes |
|---|---|---|---|---|---|
| 2026-11-02 | Re-levelled mean per historical FY (scale and shift) | Equals F after clipping | Matches to 1e-6 before calibration; scale never clips, shift clips 3 (FY22) and 8 (FY23) intervals at the floor | Pass | Cross-check; `relevel_check.csv` |
| 2026-11-02 | Daily-component cost engine vs the brief's 5-minute interval formula | Identical | Max difference 5e-10, with and without the negative-price PPA suspension | Pass | Cross-check |
| 2026-11-02 | Battery dispatch: state of charge, daily cycle, efficiency, look-ahead | SoC 0-40 MWh; at most 40 MWh discharged a day; discharged/charged = 0.88; no use of future prices | All hold; changing later prices leaves earlier dispatch unchanged; hand-checked 2022-06-10, 2023-01-15, 2024-02-20 | Pass | Cross-check |
| 2026-11-02 | Hedge break-even price vs F (FY28) | Close to F by construction | First run $101.45 vs $99.44 (month-edge under-sampling and pool mix); after wrap-around blocks and calibration $99.34 | Fail, fixed | `hedge_breakeven.csv`; decision log |
| 2026-11-02 | Seed sensitivity, FY28, 5,000 years, 20 seeds | Small next to findings | SD: spot expected $0.049M, spot P95 $0.132M, 100% hedge P95 $0.007M, break-even $0.10/MWh | Pass | |
| 2026-11-02 | NPV and equivalent annual cost by hand | Match code | NPV and EAC match the hand calculation | Pass | Cross-check |

