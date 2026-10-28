# Raw data

Read-only. Never edit these files; cleaned data goes to `data/processed/`. Raw files are not committed.

- **Price and demand:** AEMO Aggregated Price and Demand, NSW1, July 2021-June 2024
  ([AEMO aggregated data](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/aggregated-data)).
  Reproduced by a fetch script [TBD: script path once built].
- **Solar:** 5-minute dispatch of an existing NSW utility-scale solar farm (AEMO dispatch data).
  Only a normalised 0-1 output factor is committed, in `data/processed/`.
- **Downloaded on:** [TBD: record when the fetch script runs]
- **Licence:** [TBD: confirm AEMO copyright permissions during the data audit]
