# Simulation account health dashboard

Related #20 priority 5; phase #5 exact checklist items “Last successful data refresh
indicator”, “Stale or missing data alerts”, “Monitor scheduled GitHub Actions
failures”; phase #4 “Mobile layout and accessibility”. No checkbox completion,
issue closure or merge is requested. Baseline: main f79ef6f, including merged #24.

The plan is to keep health separate from returns, independently check accepted
inputs/account records/publication, publish a structured artifact, and expire it in
the browser. This implementation does not change any historical account files,
trading rules, source universes, fees, assumptions or existing warnings.

## Evidence and status contract

`python -m monitoring.account_health` writes `docs/account-health/status.json`.
Schema v1 contains three account entries, checked-at/expiry timestamps, expected
session, last verified data session, last confirmed advancement, saved valuation
label, freshness, reason codes, explanations, Actions metadata and evidence URLs.
Forward research includes all four named variant accounts. Saved labels are not
represented as authenticated source-session or publication evidence.

ACTIVE requires all of the following, independently:

- Full required universe in the accepted content-addressed bundle, raw responses,
  snapshots and export. Revalidate contracts, source identity, basis and clocks;
  reparse raw bytes and reproduce both snapshots and export. Synthetic-classified
  snapshots are rejected. Every symbol must cover the expected completed session.
- Ordered unique account sessions, state/session/cash/holdings agreement, complete
  finite marks, reconciled marked equity and journal cash/units. Duplicate journal
  rows, invalid actions and overspending fail closed. The legacy crypto wall-clock
  label alone cannot authenticate a price session.
- The latest ingestion status is accepted/no-new-data and is not overdue. Failed
  ingestion cannot hide behind a previously accepted pointer.
- A post-publication receipt binds the accepted bundle and exact four account file
  hashes to a successful simulation and successful push step. The latest main
  Actions run and attempt must match the receipt and be successful. Workflow
  success by itself is insufficient. A changed ledger establishes advancement;
  unchanged valid records yield PAUSED/ALREADY_PROCESSED. Previously confirmed
  advancement is retained on an already-processed receipt.

Unresolved stock recovery inventory is an additional blocker. A documented
operational pause does not override missing or overdue evidence; the implemented
PAUSED path is a verified session already processed. There is no pause switch
that can turn invalid data into a healthy account. Unknowns default to BLOCKED.

The stock calendar is the shared reviewed XNYS 2024–2027 calendar, including DST,
holidays and early closes. Crypto uses completed UTC days, every day. Browser
calendar data is generated from `data_contracts.sessions.session_close` for every
stock session in that supported range. Calendar extensions require regeneration
and review. Status expires at the next completed session or 26 hours after the
check, whichever is earlier. The browser checks expected session independently,
requires complete per-symbol and publication/hash metadata for ACTIVE/PAUSED,
rejects missing/invalid/future/duplicate/expired entries, and rechecks open tabs
once per minute and on visibility changes. Static HTML and JavaScript failure
start BLOCKED. Missing values remain unknown, never zero P/L.

## Publication

Producer workflows capture pre-simulation account hashes. After their existing
publication step, they preserve ingestion status and write a receipt only when
both the simulation and publication steps succeeded and the saved account/input
checks pass. Receipt creation verifies that the account bytes are committed after
the producer's push/rebase. Invalid/failed/skipped attempts remove the current
receipt. Evidence is published in a second commit. Failure of that commit leaves
the run unsuccessful, so it cannot authorize ACTIVE.

`account-health.yml` runs hourly and after the two producer workflows complete.
It checks out main, reads main Actions outcomes, recalculates health, uploads a
run artifact and commits only the Pages health JSON. It shares the existing
market-data publication concurrency group. It executes no trading code. Missing
Actions/API evidence blocks the affected accounts. It does not suppress or change
`research-health.yml`, which continues reporting broader research warnings.

This is the existing repository-hosted GitHub Pages dashboard, not a separate
site or deployment. The panel uses existing colors and typography, semantic
headings, labeled statuses, readable reason explanations, safe text/links and a
single column on mobile. Existing returns and warnings remain visible.

## Verification

- Full Python suite: 227 tests passed, including 20 health/receipt tests.
  New tests use temporary,
  explicitly synthetic accounts and never modify saved production history.
- Required compileall and 47-task roadmap consistency checks passed.
- Five Node suites pass, including health status/expiry/calendar/unknown evidence.
- Chromium health tests cover ACTIVE/PAUSED/BLOCKED, invalid/missing artifacts,
  an overdue open tab, inert hostile text/links and 375/1280 px layouts. Two
  repeated screenshots at each width must match exactly; screenshots are retained.
- Integrated dashboard, Discovery and 144-case Volume Profile Chromium tests pass.
- Existing Copilot canonical screenshot comparisons fail on local host Chromium
  154/font differences (also documented in #24). References/assertions are
  unchanged. Hosted CI uses the existing digest-pinned Playwright image and must
  pass these canonical comparisons. CI also runs the new health tests and uploads
  health screenshots alongside the existing Copilot screenshots.

Reproduce with the repository requirements installed:

```sh
python -m unittest discover -s tests -v
python -m compileall -q paper_trader.py crypto_paper_trader.py strategy_comparison.py monitoring tests
python scripts/check_roadmap.py
python tests/discovery_fixtures.py
node tests/account_health_test.js
python tests/account_health_browser.py
```

Use `BROWSER_EXECUTABLE=/usr/bin/chromium` only for an explicit local diagnostic;
canonical screenshots run in the pinned CI image. No screenshot baselines were
updated or tolerances weakened. CI proves software behavior, not profitability.

## Remaining real-world evidence blockers

Stocks retain ambiguous duplicate/out-of-order historical records and unresolved
original session attribution. Crypto retains unavailable/incomplete provider
coverage and legacy session ambiguity. No accepted corrections or symbol mapping
are introduced. Current receipts are absent until the updated producer workflows
run successfully. These are expected BLOCKED outcomes, not a green-health target.

Forward accounts still use separate ungated downloads. Their health is explicitly
BLOCKED with FORWARD_INPUTS_UNVERIFIED and PUBLICATION_UNCONFIRMED, even if a job
succeeds or a saved valuation is recent. Migrating those engines to accepted inputs
and a reviewed account/publication contract is separate work; this PR does not
assert that the forward inputs are accepted or fabricate advancement timestamps.

The panel is a read-only operational evidence view, not brokerage integration,
live trading, authenticated investment performance or recovery of missing history.
