# Paper simulation reliability investigation

Evidence collected November 4, 2026 (America/Chicago; remote runs use UTC).
Baseline: main `5db7112`, following `f2dced5`. Read AGENTS.md, ROADMAP.md and
issue #20 first. Separate branch; PR #22's branch is untouched.
Related #20 and phase #5 exact items “Monitor scheduled GitHub Actions failures”,
“Last successful data refresh indicator”, “Stale or missing data alerts”; phase #4
“Realized versus unrealized P/L” is an accounting audit dependency, not completed.
No checklist changes, merges or issue closures. All results are simulation software
evidence, not authenticated historical investment performance.

## Confirmed operational causes

- [Stock run 41954673207](https://github.com/iikaitlynii/trading-bot/actions/runs/41954673207),
  job 127006596702: dependency installation succeeds; complete-input validation
  raises `MISSING_SYMBOLS: AAPL, AMZN, MSFT, NVDA`; trader and research steps skip.
  All four raw responses committed by this run have exactly one bad observation:
  November 4 close is null, although H/L/volume exist. This is genuine missing
  provider data, not an ingestion parser or calendar defect. No previous close,
  quote metadata, adjusted close or synthetic value can fill it. Regression tests
  reparse these exact archived bytes and require rejection.
- [Latest crypto run 41764758528](https://github.com/iikaitlynii/trading-bot/actions/runs/41764758528),
  job 126360420985: Yahoo reports PEPE-USD “No data found, symbol may be delisted”;
  completed-history validation reports insufficient history; account explicitly
  pauses, while the old workflow exits successfully. Performance ends October 24.
  This run predates the merged ingestion gate; the current workflow validates the
  complete universe before invoking the engine. A successful old job did not prove
  a new valuation or trade. No evidence establishes delisting or the onset's exact
  provider-side cause.
- [Health run 41954725006](https://github.com/iikaitlynii/trading-bot/actions/runs/41954725006),
  job 127006771583: ATTENTION is justified. Saved stock signals and shadow streams
  end November 2; stock history ends November 3; crypto has NO_DATA; comparison is
  INVALID; smart-money scores are EMPTY. Installation and artifact upload succeed.
  The empty wallet watchlist is unconfigured research, not evidence of RPC failure.
  Regenerating reports does not refresh underlying observations. Warnings remain.

Independent read-only Yahoo probes in this environment:

| Symbol | HTTP | Contract result | Raw SHA-256 |
| --- | --- | --- | --- |
| PEPE-USD | 404 | Provider Not Found; instrument support undetermined | f0b5f9feeac9f1fc93c31b1edc03fbc1fda4acb3ec5e233ebb39d6f8b66e1769 |
| DOGE-USD | 200 | Invalid/null OHLCV | e82cc5c43812536376c59e6a9d5ad482fe9a8b51149b93aa5fb9cb96d47dd224 |
| AAPL | 200 | Valid through November 4 | e89af888629a6551488160a75bc90f04b50f991eb8e9cde3122142f558749b8a |

These moving responses differ from the frozen stock failure. AAPL recovery proves
availability can change, not that every stock or crypto asset has recovered.
Probe bytes stayed in ignored-by-staging scratch space, outside accepted bundles.
PEPE remains required; no alias, replacement provider or asset removal occurred.
Next provider investigation needs an independently authenticated instrument mapping
and retained source evidence; a ticker substitution alone is not sufficient.

## Implemented safeguards

1. Crypto session identity now follows the completed UTC price session, not Chicago
   run date. Previously a rerun spanning Chicago midnight could process one source
   twice, while a new UTC source on the same Chicago date could be skipped. New
   performance/journal dates use source identity; new state records
   `last_price_session`. Legacy rows are untouched; their last run date acts as a
   conservative lower bound, never a claimed source mapping.
2. Both engines validate saved performance date sequences before account mutation.
   Duplicate, unordered, malformed, unreadable and older evidence fails closed.
   Stock no longer catches ledger read failures as an empty processed-date set or
   silently changes state to “normalize” a legacy duplicate. Repeated sessions do
   not append journals or performance. A missing ledger remains valid for a new
   account; this guard does not claim full crash-transaction recovery.
3. Ingestion prints each symbol's rejection reason in Actions logs, in addition to
   preserving the existing detailed status artifact. It still checks full coverage.
4. Crypto output publication runs even after a failed validation, preserving raw
   provider evidence like the stock workflow. Existing ingestion outcome/artifact
   steps still run and the job remains failed. Account outputs are staged only if
   the simulation step succeeds; failed/skipped simulations publish evidence only.
   No failed input is accepted.

The stock ledger contains two September 18 rows and September 19 → September 18
out-of-order dates. The new guard therefore also blocks stocks after provider
recovery. This is intentional: reconciliation must establish which observations
belong to which source sessions. Preserve originals and publish a separate,
reviewed correction manifest with original row hashes, source evidence, rationale
and derived replacement view. Do not delete, relabel, sort or deduplicate the
original account files to make validation pass.

## Execution and accounting audit

| Path | Timing | Costs | Consequence |
| --- | --- | --- | --- |
| Stock/crypto paper | Signal includes close t; fill at close t | No fee/slippage deductions | Optimistic simulation; not executable performance |
| Forward shadow | Same-close signal/fill | No fee/slippage deductions | Same limitation; separate ungated downloads also remain |
| Bot/lab | Same-close assumptions | Generally 10 bp fee + 10 bp slippage | Costs do not cure causal bias |
| Strategy comparison | Shifted exposure, prior signal-close fill assumption | Estimated costs | Still optimistic; incomplete PEPE coverage invalidates comparison |
| Archived HA experiment | Next observed open after signal | Adverse fee/slippage/spread model | Separate experiment, not a migrated paper account |

Paper buys subtract `amount` and add `amount / close` units; sells add
`units * close`; equity is cash plus units times marks. With zero costs a same-price
round trip leaves equity unchanged. Daily P/L subtracts the prior saved valuation;
across missing observations it is an observation-to-observation change, not verified
daily performance. Saved equity is rounded to cents; state holdings remain full
precision. No deposits, dividends, splits/corporate-action adjustments, funding,
borrow, fee ledger or tax-lot realized/unrealized reconciliation are recorded.
Raw-close histories can introduce corporate-action distortions. Existing holdings
may exceed entry risk limits; current warnings do not force liquidation.

Remaining engineering work: a separately versioned forward-only accounting model
with persisted signal timestamp/session and pending simulated intent; fill only at
a validated observable price strictly after the signal (not retroactively selected
from today's history); adverse side-specific slippage, fee debits and explicit
cash/units/fee/equity reconciliation. Use full cash cost to size buys, mark holdings
at unslipped market prices, retain per-fill costs, and test gaps, missing fill bars,
round trips, cash limits, replay and crashes. Persist account/model/input hashes.
Daily-close stops are observations, not guaranteed stop-price execution. Coefficients
must be labeled assumptions and sensitivity-tested, not claimed calibrated costs.
Do not silently change the economic meaning of existing journals or recalculate
historical profits. Multi-file state/journal/performance writes remain non-atomic;
a transaction manifest and recovery protocol are still required.

## Recommended dashboard health panel

One row per stock, crypto and each forward-shadow account, separate from returns:

- **ACTIVE**: full required universe accepted for the expected completed session,
  valid account ledger and successful account publication for that session.
- **PAUSED**: explicitly disabled or valid inputs contain no new source session;
  display “already recorded”, not fresh valuation. After the next completed session
  becomes due, stale/missing evidence becomes BLOCKED.
- **BLOCKED**: missing/invalid/stale prices, PEPE unavailability, ambiguous ledger,
  unknown outcome, failed publication or missing status. Fail closed on unknowns.

Include checked-at UTC (render Chicago with timezone), expected source session,
per-symbol source sessions, last accepted input timestamp/hash, last recorded
valuation session, last actual account advancement, job outcome and run URL,
publication outcome, reason codes and readable explanation. Preserve last known
valuation with a stale label; never display missing valuation as flat P/L or zero.
Job success and freshly generated reports are not ACTIVE evidence. Status expires
at the next expected completed session using the shared calendar. Keep research
health warnings visible independently. Suggested current states: stocks BLOCKED
(provider observations at failure plus ambiguous legacy ledger); crypto BLOCKED
(PEPE and observed DOGE data); shadow accounts BLOCKED while source evidence stale.
This PR recommends the panel; it does not add UI or claim an integrated health feed.

## Verification

Offline tests cover the real frozen stock rejection, missing-universe pointer
preservation and visible diagnostics; crypto replay across Chicago midnight and
new UTC sessions on the same Chicago date; ledger duplicates, order, canonical
labels, read errors, backward sessions and unchanged stock state/journals.
Run the full Python suite, required compileall, roadmap gate and hosted PR checks.
Local validation: all 195 Python tests passed, including execution of the workflow
publication script with success/failure/skipped outcomes and a recording Git stub.
Required compilation, roadmap consistency and whitespace checks passed.
Hosted CI proves software behavior, not recovered provider coverage or profitability.
