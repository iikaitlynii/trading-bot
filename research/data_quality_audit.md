# Paper-trader market-data audit

Relates to issue #1, specifically **“Separate missing price data from defensive
sell signals”** and **“Check missing, stale, duplicate records”**. These items
remain unchecked pending PR review, CI, and merge.

This audit uses deterministic synthetic daily prices and temporary simulated
accounts. It is regression evidence, not a historical backtest, real market
performance, or evidence of strategy profitability. No brokerage, exchange
execution, credentials, or real orders are involved. Existing research outputs
and saved paper accounts are unchanged.

## Findings and behavior

| Case | Original safeguard or gap | Audited behavior |
| --- | --- | --- |
| Missing/short stock history or download exception | Entire session skipped | Preserved; no state, signals, journal, or performance writes |
| Missing held crypto price | Entire account held rather than selling | Preserved; `NO_DATA` diagnostics may update, account/journal/performance stay unchanged |
| Missing unheld crypto price | `NO_DATA`, not `DEFENSIVE` | Preserved; healthy assets can still participate |
| NaN, infinity, nonpositive, nonnumeric prices | Loaders dropped some rows; infinity and malformed inputs could reach calculations | Reject affected history without deleting bad completed rows or substituting an older quote |
| Duplicate, unordered, NaT, non-datetime labels or wrong response shape | Not reliably checked; some cases crashed | Reject before any simulated account update |
| Wrong symbol in a multi-column download | First closing-price column selected | Select the requested ticker explicitly; missing/ambiguous columns are unavailable |
| Stale/future quotes | Crypto had a two-day age check; stocks had none | Bound stock age to four calendar days and crypto age to two; reject future labels |
| Unfinished daily bar | Could be treated as a closing price | Exclude today's stock bar before 16:00 New York time and today's UTC crypto bar |
| Inconsistent latest sessions | Stocks already held; crypto mixed dates | Both skip the entire session when otherwise usable assets disagree |
| Missing interior crypto day | Rolling averages silently spanned a gap | Require contiguous daily crypto history |
| Stock weekend label | Accepted as a market session | Reject weekend session labels |
| Held stock outside the configured universe | Valued at entry price | Skip the session; valuation requires an actual validated quote for every holding |
| No usable crypto data and no holdings | Could consume the daily run and append empty-account performance | Emit `NO_DATA` diagnostics without advancing account state/performance |
| Earlier stock session than saved state | Could replay an older session | Reject session regression |
| Stock price rounded to zero for accounting | Tiny positive prices could cause division by zero | Keep full validated price precision in simulated trades and valuation; round only display signals |

Healthy increasing and decreasing price histories still produce `SIM_BUY` and
`SIM_SELL` respectively, and a repeated session does not duplicate records.
Crypto signal rows include `price_session` to distinguish the source UTC daily
bar from the legacy `date_utc` column, which remains the Central run date.

## Validation

Run from the repository with its Python 3.12 dependencies installed:

```sh
python -m unittest discover -s tests -v
python -m compileall -q paper_trader.py crypto_paper_trader.py strategy_comparison.py
```

The suite contains 20 tests (including parameterized corruption cases). The new
tests patch the clock and downloader, run each account in a temporary directory,
and check persisted state, journals, signals, performance, and repeat runs.
Tests also cover a Friday close on Monday morning, pre-close stock execution,
and the UTC/Central date boundary for crypto. The original missing-data tests
remain; the stock fixture now uses business days so it reaches the intended
missing-symbol check.

## Limits and follow-up

- Stock freshness is a documented four-calendar-day tolerance, **not** an exact
  exchange calendar. It can accept a recently missing weekday session, does not
  detect every interior missing stock session, and conservatively waits until
  16:00 on early-close days. Holiday/early-close calendars and provider publication
  delays need a separate explicit policy before asserting exact-session freshness.
- Crypto keeps its existing Central run-date idempotency policy, rather than
  migrating persisted account dates to UTC sessions. A two-day-old common quote
  can still qualify under the retained freshness tolerance. This audit does not
  redesign scheduling or backfill historical simulated records.
- Validation is intentionally conservative across the returned completed history:
  an old malformed value or missing crypto day can hold an asset even outside the
  moving-average window. There is no silent repair, forward fill, or fallback to
  entry prices. Unfinished current bars are excluded before price validation.
- This audit does not validate corrupt account/performance files, corporate-action
  adjustments, provider price accuracy, outliers, or fees/slippage.
- Live Yahoo downloads and hosted GitHub CI are separate checks; offline tests do
  not establish provider availability or a successful hosted CI run.
