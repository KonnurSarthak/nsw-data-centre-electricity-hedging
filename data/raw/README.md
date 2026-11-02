# Raw data

Treated as read-only; cleaned data goes to `data/processed/`. Raw files are not committed.

- **Price and demand:** AEMO Aggregated Price and Demand, NSW1, July 2021-June 2024
  ([AEMO aggregated data](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/aggregated-data)).
  Reproduce with `python -m src.fetch_aemo` (script: `src/fetch_aemo.py`), which saves the monthly CSVs to `data/raw/aemo/`.
- **Solar:** 5-minute dispatch of an existing NSW utility-scale solar farm (AEMO dispatch data).
  Only a normalised 0-1 output factor is committed, as `data/processed/solar_factor_5min.csv.gz`.
- **Local xlsx exports:** the data-audit notebook also reads two Excel files from this folder (a price and demand export, and the solar farm dispatch
  data). They are not committed, so the notebook's reconciliation and solar cells cannot be re-run from a fresh clone.
- **Downloaded on:** 28 Oct 2026 (AEMO monthly CSVs)
- **Licence:** [AEMO Copyright Permissions](https://www.aemo.com.au/privacy-and-legal-notices/copyright-permissions)
  allow anyone to use AEMO material for any purpose, with accurate attribution to AEMO as its author.
