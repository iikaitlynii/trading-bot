# Strategy comparison regression audit

Relates to issue #1: “Compare strategies against buy-and-hold and cash”, “Model
fees and slippage”, “Check missing, stale, duplicate records”, and signal timing
under “Audit stock and crypto entry/exit logic”. These are partial verification
results; leave issue and roadmap checkboxes unchecked pending CI, review, and merge.

## Scope and evidence

All new fixtures are fixed synthetic prices. No market downloads, real orders,
paper-account updates, or profitability research were performed. Tests prohibit
unexpected `yf.download` calls. Files owned by Data Agent PR #7 were not changed;
coordination is recorded in that PR's conversation.

Twelve new unittest methods cover:

- Prior-session signal timing: a final jump cannot earn its own return; changing
  the last price cannot change prior exposures. An independent scalar ledger
  recomputes stock 200-day and crypto 100-day regime signals from past prices,
  momentum, entry/exit/re-entry, compounded equity, and drawdown.
- Hypothetical fees and slippage, separately and together: each contributes an
  adverse 10 bps per unit of turnover, including opening positions. Flat
  buy-and-hold returns -0.20%, with one entry and no terminal liquidation fee.
  Exits are charged even when exposure becomes zero.
- Buy-and-hold includes the first evaluation day's return from the preceding
  close; equity starts at 1 before that return, including for drawdown. Cash
  returns zero, with zero exposure and turnover.
- Invalid prices (including interior/warm-up rows), NaNs, infinities, nonpositive
  values, text, booleans, complex values, short histories, malformed indices,
  duplicate/reversed dates, multiple observations on a day, and invalid shapes.
- Downloader ticker selection for both yfinance MultiIndex orientations, keeping
  missing observations visible. Main records invalid assets in its missing CSV;
  an entirely missing run raises and writes no new outputs.
- Identical input produces identical metrics and output CSV bytes, without input
  mutation. Fixed fixtures and patched downloads make these checks offline.

Baseline main failed the new suite with 21 assertion failures and 19 errors
(including parameterized subtests). The patched implementation passes all 15
repository tests: 12 new comparison tests and 3 existing paper-safety tests.
An in-memory mutation removing both signal lags produced 4 failures and no errors,
confirming the suite detects same-session leakage. No mutation was saved.

Validation on Python 3.12.14, pandas 3.1.0, NumPy 2.5.4, yfinance 1.7.0:

```sh
python -m unittest discover -s tests -v
python -m compileall -q paper_trader.py crypto_paper_trader.py strategy_comparison.py
git diff --check
```

## Fixes

`strategy_comparison.py` now rejects corrupt histories, preserves missing rows
instead of dropping them, selects the requested ticker, and adds explicit cash
metrics. It keeps the existing additive fee/slippage model and lagged signal
rules, with their valuation boundary and execution assumptions documented.
No persisted comparison results were regenerated.

## Limits and reviewer follow-up

- These are illustrative close-to-close estimates: observing close t-1 and filling
  at that same close is an optimistic execution assumption even with a lagged
  exposure. Next-open fills require open prices and a separately specified model.
- Costs are additive return deductions, not a share/cash fill ledger, and use fixed
  hypothetical bps without spread, liquidity, impact, or terminal liquidation.
- Validation detects missing values present in returned rows, not omitted sessions,
  stale final dates, unfinished daily bars, holidays, corporate-action errors, or
  mixed as-of dates across assets. No calendar repair or forward fill is applied.
  Historical calculations intentionally do not require a current final date.
- The rolling trailing window is not an out-of-sample model selection protocol.
  Existing signals and asset selection are not validated for profitability.
- Byte repeatability applies to identical inputs and dependencies. Live Yahoo
  history can change; this work does not add immutable price snapshots, dependency
  locks, dataset hashes, or strategy-version archives.
- An all-missing invocation raises without removing older result files. Consumers
  must check process success and as-of dates; stale-output lifecycle is follow-up.
- Hosted CI and independent human review are separate evidence from local tests.
