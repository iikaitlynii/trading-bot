# Simulated forward performance reporting

Related to Phase 4 issue #4: “Monthly and yearly performance reports” (monthly portion), “Realized versus unrealized P/L”, “CSV and PDF exports” (CSV portion). Yearly summaries and PDF are outside this change. Checkboxes require merged CI evidence and human review.

Run `python performance_reports.py` from any directory to regenerate `reports/{stocks,crypto}.json`, daily/monthly CSVs, and summary CSVs. The module uses only Python's standard library, reads saved files, makes no network calls, and never writes account state, journals, or signals. `python paper_report.py` renders the same stock calculations into the existing stock health report. A separate daily workflow refreshes only `reports/`; no trading workflow or engine is changed. Dashboard report and export links resolve on main after merge. CSV links may open in-browser on cross-origin hosts; Save downloads the file.

## Audit and calculations

- Existing stock health output used journal FIFO realized P/L but labeled the residual “unrealized/other”. The dashboard duplicated this calculation. Crypto lacked a matching health report. The old residual card is now explicitly unclassified; the new report panel displays reconciled values from the shared calculation.
- Total change is latest recorded equity minus configured launch capital ($10,000 stock / $5,000 crypto). This assumes no external flows, which the engines do not record. This is portfolio change, not automatically trading profit.
- FIFO realized gains use positive finite quantities/prices, known simulated actions, chronological journal order, and matched sells. Missing/malformed journals, unknown actions, unmatched sells, and journals ahead of the valuation suppress realized and unrealized values; an empty correctly headed journal is distinct from a missing journal.
- Unrealized gains equal recorded equity minus recorded cash minus remaining FIFO cost. This requires matching state date, journal-derived cash, state/performance cash (two-cent tolerance for stored rounding), and held quantities. Reconciliation failure exposes the unclassified residual instead of calling it unrealized. Realized values remain journal-derived before fees; unrealized values depend on the saved equity mark, which is not independently repriced here.
- Nonfinite, invalid, or future valuations are excluded. ALL rows on duplicate dates are excluded; no arbitrary winner is selected. Out-of-order records are sorted with a warning. The saved stock snapshot has two 2026-09-18 rows and weekend valuation labels; the module warns without rewriting history. Calendar gaps, old snapshots, and impossible cash are also disclosed. Exchange holiday completeness is not inferred.
- Maximum recorded drawdown includes launch capital and only unambiguous retained valuations; gaps/duplicates may understate the true drawdown. No annualized Sharpe/CAGR or daily win-rate is inferred from irregular records.
- Monthly summaries use the previous recorded month's closing equity (launch capital for the first observed month). They are portfolio changes including open holdings, with launch/current/uncertain coverage labels. They do not claim full calendar-month observations or monthly realized trade profits.

## Benchmark provenance and limits

Cash is an explicitly assumed **zero-interest** balance, with no inflation/fees. It is not a verified savings or Treasury yield. Buy-and-hold uses exact same start/end recorded dates as the portfolio comparison return, avoiding launch-versus-first-observation mismatches. Excess is in percentage points. Launch return is shown separately.

Stock buy-and-hold is a fixed equal-weight initial allocation to AAPL, MSFT, NVDA and AMZN, fully invested without rebalancing. Prices come from `research/stock_history.csv` (`date,ticker,close`) whose collector, `stock_history_research.py`, reads Yahoo's public daily chart endpoint. This verifies schema, finite positive prices, unique symbols/dates, and exact endpoints in available repository data; it is not independent provider verification. Raw closes omit dividends/corporate-action adjustments and execution costs. It is not an S&P 500 or risk-matched benchmark. Monthly indexed ETF research is deliberately not substituted for daily dates.

Crypto's predefined benchmark is BTC-USD. No dated crypto historical snapshot exists in the audited repository, so its return and excess are **Unavailable**, never zero or a fabricated comparison. A future data-agent supplied `research/crypto_history.csv` must have `date,ticker,close` with positive daily raw closes and documented provider provenance reviewed before use. No prices are fetched or invented by reporting. Missing/duplicate exact endpoints suppress comparisons; no interpolation, nearest-day substitution, or forward fill is used.

## Validation and coordination

`python -m unittest discover -s tests -v` includes deterministic FIFO, stock/crypto schema, missing/invalid data, reconciliation, benchmark alignment, monthly boundary, CSV round-trip, and dashboard Node runtime tests. Node is required for the compatibility test (available on GitHub's Ubuntu runners). The runtime harness checks account switching, stale requests, missing reports, unsupported versions, download targets, HTML IDs, and safe unavailable rendering; it is not a visual-browser audit.

Run the handbook compile checks plus `python -m compileall -q performance_reports.py paper_report.py` and `node --check docs/performance_reports.js`.

Ownership was posted on issues #4 and #2. Risk controls, engine state and schemas are unchanged; the report's drawdown is descriptive only. No issue closure, merge, or completion marking is automated by this work.
