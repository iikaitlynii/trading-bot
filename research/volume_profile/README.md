# Educational Volume Profile research

Phase #3, exact checkbox: **“Volume and volatility analysis”**. This contribution covers Volume Profile context only; it does not complete the broader checkbox. No issue state/checklist changes. Human acceptance and CI review remain required.

## Data audit performed before implementation

Inspected `market_data.py`, `stock_history_research.py`, daily dataset contracts, saved CSV schemas and the minute-research manifest. `research/stock_history.csv` contains 2,004 rows: AAPL, MSFT, NVDA, AMZN each have 501 ascending sessions, 2024-10-31–2026-10-30. All expected sessions match the repository's reviewed XNYS calendar. No duplicates, missing HLCV values, nonpositive prices/volume, nonfinite values or HLC geometry failures were found. Source SHA-256: `d194c4743eb5331b49c61c91f03d173bec75ad715615471376a8b8aa28a4c6a3`.

This is a structural audit, not independent verification of provider prices or volume. The collector uses Yahoo daily quote HLCV, omits open, drops missing price rows, maps absent volume to zero, and does not retain retrieval time, raw response or adjustment/corporate-action evidence. The module rejects missing sessions and zero volume rather than silently repairing them. Daily volume units are vendor-reported stock share volume, not dollar volume; upstream correctness and split consistency remain unverified. Historical end dates are explicit; no current-freshness claim is made.

Other sources were unsuitable for this initial module: ETF history contains monthly indexed prices without volume; paper chart history has volume ratios rather than absolute volume-at-price; daily dataset fixtures contain synthetic closes only. The BTC minute manifest explicitly identifies aggregate provider volume rather than venue-specific traded size. No repository source inspected supplies actual trade-level volume-at-price. No trade-level/exact mode is claimed.

## Method and uncertainty

`volume_profile.py` distributes each daily candle's volume uniformly across its low–high interval, in proportion to overlap with equally spaced price bins. A zero-width individual candle assigns its volume to its price bin (interior boundaries choose the upper bin; overall maximum chooses the last). An entirely constant price range is rejected. Volume is conserved. These are **illustrative estimates derived from saved historical candles**, not trade-level measurements, backtest returns or simulated live paper records.

POC is the midpoint of the largest bin (lowest-price tie winner). Start value area there, then add the larger adjacent bin until at least 70% of volume is included (ties downward); VAL/VAH are its outer edges. Overshoot is displayed. HVN/LVN are strict interior local maxima/minima without smoothing; endpoints and equal-volume plateaus are excluded. None is a legitimate result. These are documented original heuristic choices, with no proprietary implementation copied. Bin/window sensitivity is exposed through controls, not optimized to outcomes.

The dashboard provides 4 symbols × 3 historical windows (20/60/120 completed daily sessions) × 3 bin counts (12/24/48). Each window is independently checked against the reviewed XNYS calendar; malformed data produces an explicit FAILED item and nonzero generator exit. Missing or invalid UI reports clear metrics/chart. There is no fallback synthetic profile disguised as historical data.

Strategy Discovery Lab links to this explanatory context and back. No candidate is automatically created or approved, no evaluation gate is bypassed, and the Discovery status remains independent. Human-authored hypotheses still need fixed rules, accepted data and independent out-of-sample evaluation. This module changes no paper engine, risk control, monitoring-health computation or execution path. No brokerage or live order connection is added.

## Reproduction and evidence

Install `requirements.txt` in a suitable environment, then run:

```sh
python volume_profile.py
python -m unittest discover -s tests -v
python -m compileall -q paper_trader.py crypto_paper_trader.py strategy_comparison.py volume_profile.py
python scripts/check_roadmap.py
python tests/volume_profile_browser.py  # playwright and /usr/bin/chromium required
python tests/discovery_fixtures.py
node tests/discovery_dashboard_test.js
node tests/performance_dashboard_test.js
```

Generator is offline and deterministic; input hash is embedded in the saved report. Rerunning against changed source bytes updates the hash and profiles for review. No scheduled downloader is introduced. Dashboard profiles remain at the checked-in historical window until explicitly regenerated; their displayed dates must not be read as current market data.

Validation in this branch: 169 Python tests passed (including 5 new synthetic tests); compile and roadmap checks passed; 36 generated profiles, zero failed. Offline Chromium passed every profile selection, uncertainty labels, 320/375/768/1280 widths and corrupt/missing-report clearing. Existing Discovery and performance Node checks passed. Initial full-suite attempt had 8 import errors because yfinance was missing; resolved by installing declared dependencies into a workspace target and rerunning with that target on PYTHONPATH. Initial Discovery Node attempt lacked its generated fixture; passed after fixture generation. Initial browser assertion expected failed Discovery loading but the checked-in archive was legitimately empty; corrected to verify its existing NOT RUN status. No outstanding test failures at final verification.

Browser screenshots: `desktop.png`, `mobile.png`. External requests were blocked during browser acceptance; no live market or order calls were made. Passing tests do not certify upstream volume, strategy profitability or human acceptance.
