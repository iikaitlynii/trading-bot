# Forward-only paper execution and accounting v2

Related #20 priorities 2–3; phase #4 exact checkbox “Realized versus unrealized P/L”;
phase #2 exact checkboxes “Configurable simulated position-size limits”,
“Track asset concentration”, “Simulated drawdown warnings” and
“Paper-only pause for unreliable data” (no checkbox completion).
Start: main `47bf243fbc62e668f93cb5cdc845b6600c63871a`, including merged PR #25.
All results described here are simulation software evidence, not investment results.

## Activation boundary and historical safety

`paper_trader.py`, `crypto_paper_trader.py` and `forward_shadow.py` now dispatch to
`simulation_v2.runner`. Existing state, journal or performance files block activation
before input access or account writes. The unresolved recovery inventory also blocks
activation. There is deliberately **no legacy migration, reset switch, correction or
reconciled replacement view** in this PR. Both real repository paper accounts and the
four legacy forward variants remain blocked. All original files, signals, reports
and health warnings are preserved byte-for-byte. Removing files to bypass this gate
is not a recovery process. An independently reviewed migration and data/ledger
requirements must be resolved in a separate change before existing accounts can use v2.

For a genuinely new empty account, the complete required universe must pass the
existing accepted-bundle verifier: archived response hashes, raw reparse, snapshot
contracts, raw-close adjustment, complete exchange sessions, latest completed
session and matching export. The latest ingestion attempt in `work/ingestion/` must
be accepted and match the bundle clock. A failed new attempt cannot fall back to an
older accepted pointer. No provider aliases or universe substitutions are introduced.

## Execution assumptions

- Each accepted daily close generates a signal, its source market/session, price
  timestamp, creation timestamp, input bundle hash and execution code hash. A pending
  `SIM_BUY` or `SIM_SELL` is persisted; the signal close cannot execute that order.
- Only the **latest subsequently observed, validated daily close** can execute it.
  Its market price timestamp and provider retrieval clock must both be strictly after
  order creation. No search through downloaded history for a convenient earlier fill.
  Missed runs therefore fill at the next observed eligible close, potentially several
  sessions later; this is not a next-open model or a guaranteed next-session service.
- Stock price timestamps are XNYS regular/early closes, with the shared 2024–2027
  holiday/DST calendar. Crypto daily closes occur at the next UTC midnight, including
  weekends. No intraday or unfinished daily prices, invented bars or carry-forward
  substitutes. A new defensive signal creates a pending exit; it does not cancel an
  earlier pending intent. Pending orders persist through unavailable inputs.
- Defaults: **10 bps fee, 10 bps adverse slippage, $0 fixed fee per fill**. Configure
  `SIM_FEE_BPS`, `SIM_SLIPPAGE_BPS`, `SIM_FIXED_FEE` when creating a new account.
  Values are illustrative assumptions, not calibrated or verified market costs.
  Assumptions and runner/model/store code hashes freeze at creation; changes fail
  closed and require a separately versioned change, never repricing existing fills.
- Buy execution price = market close × (1 + slippage); sell = close × (1 − slippage).
  Fee = execution notional × fee rate + fixed fee. Buy cash debit includes the entire
  notional and fee; sell cash credit is notional less fee. Buy quantities round down
  to 12 decimal units. Tiny/unaffordable quantities and net-negative sell proceeds
  are rejected explicitly. No negative cash, borrowing or short positions.
- Pending buy budgets reserve cash and aggregate exposure capacity. Existing stock/
  crypto position and exposure environment limits apply. Sizing defaults remain
  20%/80% stock and 10%/40% crypto, minimum all-in budgets $50/$25. Gap fills resize
  units to the reserved cash budget. Existing positions can exceed limits as marks
  change; persisted exposure/drawdown warnings remain visible without forced sales.
  Forward variants retain their signal windows/weights and close-triggered stops;
  stops create pending exits, never guarantee a threshold execution price.

## Accounting and reconciliation

State uses decimal strings; marks use unslipped accepted closes. Open cost basis
includes buy fees and slipped buy price. Realized P/L = net sell proceeds minus
released full-position basis. Unrealized P/L = marked position value minus remaining
basis. Cumulative fees are disclosed separately and are already included in basis/net
proceeds; never subtract them twice. Equity = cash + marked positions = initial
simulated capital + realized P/L + unrealized P/L. No deposits, partial exits, lots,
dividends, splits, interest, taxes, funding, borrow, spread or liquidity calibration
are modeled. Raw-close corporate-action limitations remain. No profitability claim.

Every load/advance replays fills, validates unique order identities/statuses,
causality, signal/input/code linkage, fee/slippage arithmetic, holdings, cash,
realized P/L, every valuation and risk warning. Complete marks are mandatory;
missing valuation evidence is not zero P/L. New sessions are strictly increasing;
repeated sessions return the existing account without another commit or fill.
Input/model/code/configuration hashes are retained in immutable account generations.
The old CSV report model is not extended with v2 rows or mixed with v2 returns.

## Transaction manifest and recovery

`simulation-v2/<account>/generations/<manifest-sha256>/` holds full immutable
`state.json`, `orders.json`, `fills.json`, `valuations.json` and `manifest.json`.
The manifest pins parent generation, session, model, complete account digest and
all four file hashes. Files and directories are fsynced before publication.
`current.json` is the **single atomic publication boundary**. Readers load only its
referenced generation and validate the committed ancestry and append-only extension.
A process-scoped advisory lock and expected-parent check exclude competing writers.
Use `Store.locked()` around mutations; this is a single-checkout POSIX-filesystem
protocol, with the workflows' common publication concurrency group across jobs.

Failure boundaries:

1. Before complete generation rename: `.staging-*` is unreferenced and excluded from
   Git. Readers retain the prior account. Retry safely; no ledger append occurred.
2. After complete rename, before pointer publication: the prior account remains
   visible. A prepared child blocks new advancement. Inspect its exact manifest and
   source evidence. For an eligible new account, run
   `python -m simulation_v2.runner stock --recover <exact-manifest-sha256>`
   (or `crypto`). This verifies hashes, full replay, parent, immutable history and
   the sole prepared candidate before roll-forward. Legacy activation gates still
   apply. Conflicting/corrupt generations require investigation; never guess, delete
   or rewrite published account evidence. Recovery may publish a now-old valuation;
   it does not make that valuation current or confer ACTIVE health.
3. After pointer publication: the transaction is committed. A rerun is idempotent.
   Workflow staging publishes pointer and immutable generations in one Git commit.
   `.lock`, `.staging-*` and temporary pointers are never committed.

`simulation_v2.report` is read-only with respect to account evidence and exports the
Pages disclosure. It cannot grant ACTIVE health. Saved valuations are labeled as
possibly stale; unavailable/blocked accounts have null balances/counts, not zeros.
Pending intents, cost assumptions, positions, fees, realized/unrealized P/L, equity,
warning flags and recent simulated fills appear only with v2 evidence. Legacy
returns and #25's ACTIVE / PAUSED / BLOCKED panel remain independent and unchanged.
V2 account publication/health receipts require a future reviewed integration before
any production v2 account can be represented as ACTIVE.

## Validation

Synthetic temporary accounts only; no fabricated data enter production history.
Regressions cover later-session fills/gaps, missed sessions, missing/invalid bars,
stock holidays/early closes and crypto weekends, fees/slippage sensitivity, full
cash costs, tiny prices, duplicate identities/session replay, realized/unrealized
reconciliation, risk limits, raw-byte corruption/failed ingestion, competing locks,
partial-file failures, prepared recovery and interruption after publication.
Former same-close integration assertions have been replaced with direct data-gate
checks and accepted-input v2 integration checks. Price rejection coverage remains.

Commands:

```sh
python -m unittest discover -s tests -v
python -m compileall -q simulation_v2 paper_trader.py crypto_paper_trader.py strategy_comparison.py
python scripts/check_roadmap.py
python tests/discovery_fixtures.py
# Run node --check on docs/*.js and node tests/*_test.js.
python tests/dashboard_browser.py
python tests/discovery_browser.py
python tests/volume_profile_browser.py
python tests/account_health_browser.py
python tests/simulation_v2_browser.py
python tests/copilot_browser.py
```

Local: 232 Python tests, compilation, roadmap and six Node suites pass. Dashboard,
Discovery, all 144 Volume Profile cases, account-health and v2 Chromium tests pass.
The v2 suite checks safe literal rendering, missing/invalid evidence and 375/1280px
repeat screenshots. Existing Copilot canonical pixel checks differ with host
Chromium 154/fonts, as already documented in recovery v1; no reference, dimension
assertion or tolerance is changed. Hosted CI uses the existing digest-pinned
Playwright image and preserves both existing and new screenshot evidence.
See the PR for final hosted run/status and verdict. Software checks do not resolve
legacy provenance, PEPE identity/coverage or historical ledger blockers.
