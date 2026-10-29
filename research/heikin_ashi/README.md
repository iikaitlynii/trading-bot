# Experimental HA pullback v1 — historical simulation only

References phase #1: “Evaluate on out-of-sample periods”, “Compare strategies against buy-and-hold and cash”, “Model fees and slippage”, “Check missing, stale, duplicate records”, and “Maintain strategy version and comparison history”. No completion or issue-state changes. This is a standalone offline experiment, with no connection to the paper engines or any brokerage.

## Deterministic interpretation

No video URL or transcript was supplied, so these are assumptions translating the supplied rules, not a claim of exact video reproduction. Rules were not optimized against these results.

- Compute HA close = (actual O+H+L+C)/4; first HA open = (actual O+C)/2; later HA open = (prior HA open + prior HA close)/2. HA high/low include actual high/low and current HA open/close. Recursion is forward only.
- EMA100 uses actual close, alpha 2/101, first-close initialization. Suppress trading for the first 200 bars of each independent daily window. EMA is a level filter; no extra slope requirement.
- Long: actual closes of the doji and preceding two bars are strictly above their contemporaneous EMA100. Short mirrors this below EMA100.
- At least the immediately preceding two HA candles must be opposite color to the proposed trade. “Clean” means nonzero range and body >=50% of HA range. Longer runs qualify via their last two candles. Equality of HA open/close is neither pullback color.
- Confirmation is the completed HA doji: nonzero HA range and absolute body <=10% of range. Doji range must be <= each of the immediately preceding three HA ranges. This fixes the subjective “previous 1–3” choice to three, with contraction rather than expansion. No additional breakout candle is assumed.
- A signal at the end of bar t may enter only at actual open of t+1. One unit of BTC per position; at most one position, long or simulated short, no pyramiding or signal exits for HA. Signals while holding are ignored. No entry on the final window bar. Initial reference capital $100,000 per independent window; fixed quantity, no compounding.
- Long stop = doji's **actual** low minus $0.01; short stop = actual high plus $0.01. Reject entries whose actual next-open adverse fill is on the wrong side of the stop. No synthetic HA price is ever a fill or a stop.
- Reward target is calculated from actual entry and stop, extended so a normal target exit earns at least the loss at a normal stop, including modeled costs (1:1 net). Gaps can exceed planned risk. The $0.01 stop buffer is an assumption, not a venue tick-size claim.
- Every fill incurs adverse 2 bps slippage plus 1 bp half-spread, and a 10 bps fee on fill notional. Costs include entry and exit fee/slippage/spread. These are estimates, not observed quotes.
- Test actual bar-open gap through stop first, fill at that open adversely; then actual high/low stop touch before target touch. If both touched, stop wins. A favorable gap target receives only the target price. Intrabar OHLC cannot identify true event order. Entry-bar stops/targets are allowed after entry at its open. Positions remaining at window end exit at the last actual close with costs; this is a predeclared end-of-study liquidation.

## Data provenance and rejection contract

`source.json` is the exact public Yahoo Finance chart response, SHA-256 pinned in `manifest.json`, including endpoint, symbol, retrieval clock, raw price basis and minute timestamp convention. It was genuinely downloaded, not synthesized. The first query1 request returned HTTP 429; the documented query2 request succeeded. This provider is an aggregator, not an exchange execution feed; authenticity here means preserved provider historical observations, not independent venue certification.

The offline runner checks the source hash, symbol and interval. Each declared [start,end) UTC window must contain every exact minute exactly once, in order, with finite positive real OHLC, finite nonnegative real volume and valid OHLC geometry. Nulls, omissions, duplicate timestamps, misaligned bars, bad geometry, incomplete endpoints and stale-to-window-end observations reject the whole window. No sorting, deduplication, interpolation or forward filling is performed. End must precede retrieval's last completed minute. Historical age is measured against the declared historical window, never today's clock. These are crypto 24/7 windows; this contract must not be used for equity sessions.

Before reading source data or running any simulation, the runner validates the entire period declaration: exactly one `development`, `validation`, and `out_of_sample` role, in that order, with timezone-aware minute-aligned start/end clocks and positive durations. Windows must be chronological and disjoint; touching endpoints and gaps are allowed. Duplicated windows, overlaps, reordered dates, missing/extra/duplicate/unknown roles, and unfinished windows fail the entire run without writing results. Clocks are normalized to UTC; invalid later periods cannot leave earlier simulations accepted.

The original response includes extra days and an irregular trailing provider observation. Only the three declared complete days are eligible; extra rows are preserved for audit but never used. Zero-volume rows are permitted provider observations, not fabricated replacements. The source-wide null/zero-volume counts and environment versions are in `environment.json`. In particular, aggregate crypto volume is often zero and many minute candles have narrow or zero ranges; zero-range HA candles cannot confirm a signal. No volume or liquidity inference is made.

## Historical results and limitations

Dates: October 19 development, October 20 validation, October 21 held-out evaluation, 2026 UTC. Each is an independent full day including 200 warmup minutes. Dates and thresholds were fixed before running the evaluator, but downloaded source metadata was inspected first. This is a **retrospective temporal holdout**, not prospective or externally preregistered validation. No fitting or model selection occurs. All three days pass the minute contract.

[Full metric table](metrics.md) reports net win rate, net profit factor, marked-equity drawdown, trade count and estimated costs. [Machine-readable results](results.json) include every executed trade, actual entry/exit prices, stop, target, times, costs and reason. PF is null when there are no losses (including cash); win rate is null with no trades. Drawdown includes unrealized close marks after estimated liquidation costs and initial capital, but cannot measure within-minute excursions.

HA: 2/2/4 trades across the three windows. The held-out day loses $899.20 after $870.61 estimated costs; 0% win rate, PF 0, 0.899% drawdown. Cash outperforms the experimental strategy. Eight total trades over three adjacent days on one asset cannot establish robustness, profitability or broad market behavior.

Comparators share the same warmup, evaluation bars, one-unit sizing, next-open execution and costs. Cash and buy-and-hold are included. The trend and momentum formulas from `strategy_comparison.py` are explicitly **minute adaptations**: SMA20>SMA50 and close>SMA200 (BTC is outside MEMECOINS), and positive 20-bar return. Exposure from completed bar t fills at t+1 open; both remain long-only. Existing daily strategy engines and their records are unchanged. This is not an apples-to-apples claim against the existing daily multi-asset portfolio: no accepted 230-day input exists in this minute snapshot, so unchanged daily performance over these minute windows is unavailable. Separate daily provenance/OOS integration remains with PRs #15/#13.

Other limitations: short borrowing/financing/funding, liquidation risk, order size/participation limits, latency, actual bid/ask, venue ticks and liquidity are unmodeled. Fixed one BTC (~$80k) is a scale choice, not a sizing recommendation. Fees dominate many small moves; higher costs could worsen results. Aggregator revisions, timestamp semantics and short provider retention limit replication by redownload; the frozen bytes enable exact offline reproduction. A broader multi-month/multi-asset study and venue-calibrated cost sensitivity remain necessary before making performance conclusions.

## Reproduce and verify

From repository root with requirements installed:

```
python heikin_ashi_research.py
python -m unittest discover -s tests -v
python -m compileall -q paper_trader.py crypto_paper_trader.py strategy_comparison.py heikin_ashi_research.py
python scripts/check_roadmap.py
```

Local verification on latest main 3a9d208 plus these new files: 73 tests passed (67 existing, six new); compilation and roadmap consistency passed. Tests independently cover HA arithmetic, prefix/future perturbation invariance, exact mirrored signal examples, invalid/minute rejection, next-open fills, stop-first collisions, gaps, bad entry rejection, net 1:1 cost arithmetic, exact frozen historical reproduction and cost/P&L reconciliation. Synthetic unit fixtures are not presented as historical evidence. Initial test collection failed because yfinance was missing; installing requirements into a workspace virtual environment resolved that environment failure before the successful full run.

Integration-review verification against main `6bd6dff4f59fdabe0d5b9bddfc5abba863d90ccd` (includes PRs #13 and #15): **113 tests passed**, including nine added period-contract tests; compilation, roadmap consistency, dashboard JavaScript syntax and whitespace checks passed. CI now explicitly covers `heikin_ashi_research.py` and `research/heikin_ashi/**` in main/master push source paths (PR checks remain unfiltered), and compiles the research module. Tests call `run(output_path=...)` using temporary files, comparing exact historical bytes while leaving the archived `results.json` unchanged; invalid-period tests also preserve preexisting output and assert no simulator calls.

The archived environment metadata describes the original historical run; it is intentionally preserved. The reviewed runner's SHA-256 is `3c29a9ef71f460cdb17a996f25db1d40b5cfabca76ccd8f724f28cfb0d8452fd`. Its temporary-output replay exactly reproduces archived result SHA-256 `58a8f49c2ec7a3c020081c3888750bb83b00e25bb50456027e59532b7d7fc3c2`. The default CLI still writes the archive for an intentional research rerun. Temporal separation prevents accidental period reuse but does not turn the original retrospective dates into prospective or preregistered evidence; the small-sample, provider and estimated-cost limitations above remain.

Coordination: reviewed file lists and posted ownership notes to phase #1 and PRs #13/#15. Only `heikin_ashi_research.py`, `tests/test_heikin_ashi_research.py` and `research/heikin_ashi/**` are owned by this work. No shared contracts, daily runner or roadmap files edited. Human review and CI remain required; no merge or task checkoff is authorized.
