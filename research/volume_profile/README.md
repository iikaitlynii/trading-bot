# Educational Volume Profile research

Phase #3, exact checkbox: **“Volume and volatility analysis”**. This contribution covers Volume Profile context only; it does not complete the broader checkbox. No issue state/checklist changes. Human acceptance and CI review remain required.

## Data audit performed before implementation

Inspected `market_data.py`, `stock_history_research.py`, daily dataset contracts, saved CSV schemas and the minute-research manifest. `research/stock_history.csv` contains 2,004 rows: AAPL, MSFT, NVDA, AMZN each have 501 ascending sessions, 2024-11-04–2026-11-03. All expected sessions match the repository's reviewed XNYS calendar. No duplicates, missing HLCV values, nonpositive prices/volume, nonfinite values or HLC geometry failures were found. Source SHA-256: `e7b7ad16c0843d1b8bed5c31b50b1cdf0c287abc12cf6b766f3b3e39877cc705`.

This is a structural audit, not independent verification of provider prices or volume. The legacy collector that produced this saved snapshot used Yahoo daily quote HLCV, omitted open, dropped missing price rows, mapped absent volume to zero, and did not retain retrieval time, raw response or adjustment/corporate-action evidence. PR #21 now rejects missing prices/volume and archives immutable provider responses before complete-universe publication; it does not retroactively certify this legacy snapshot. Volume Profile remains an offline legacy consumer and does not claim manifest-backed acceptance. The module rejects missing sessions and zero volume rather than silently repairing them. Daily volume units are vendor-reported stock share volume, not dollar volume; upstream correctness and split consistency remain unverified. Historical end dates are explicit; no current-freshness claim is made.

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

Integration validation against main `caa2ea6128e6c82c4be40af6630f6d4c2ea26ec0` (PRs #18 and #21 merged): 187 Python tests pass, including synthetic Volume Profile and ingestion protections; compilation and roadmap checks pass (47 tasks, no completion changes). All dashboard JavaScript syntax checks and the performance, Discovery and chart-indicator Node suites pass. Existing dashboard and Discovery Chromium suites pass, preserving charts, upload clearing, permission-aware video export intake, saved portfolios, research-health alerts, keyboard navigation and mobile layouts. Volume Profile Chromium checks cover all 36 symbol/window/bin combinations at 320/375/768/1280 widths (144 combinations), saved values, unique IDs, explicit approximation labels, missing/malformed report clearing and no JavaScript errors. The approximation status is fixed UI text; even a report claiming exactness cannot relabel it.

The existing PR branch is updated through a merge of main; there were no textual conflicts. Only Volume Profile integration files and its CI wiring differ from main; ingestion, market intelligence implementations and AI Copilot work are untouched. Profiles were explicitly regenerated from main's saved CSV through November 3, 2026, replacing the older October 30 snapshot. All 36 profiles are available and byte-identical on regeneration. No accepted manifest lineage or raw-response evidence is claimed for this CSV consumer. Browser dependencies and the declared research dependencies were supplied from the environment's installed runtime/venv. An initial fixture command without the dependency path failed and passed when rerun with it. The sandbox initially blocked browser/local-server sockets; permitted test execution passed. A preliminary reproduction against the older saved report correctly differed after main's source refresh; explicit regeneration resolved that mismatch. Whitespace checks against main pass; inherited CSV CRLF from main is preserved. Hosted CI and mergeability are checked separately after pushing.
Browser screenshots: `desktop.png`, `mobile.png`. External requests were blocked during browser acceptance; no live market or order calls were made. Passing tests do not certify upstream volume, strategy profitability or human acceptance.
