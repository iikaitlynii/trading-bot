# Historical recovery v1 — blocked, no accepted corrections

Investigation: November 4, 2026 America/Chicago (November 5 UTC).
Baseline: main `c08ac45f8e9698889f15c022162633be0fab2f27`, including merged PR #23.
Related #20 priority 3 (legacy ledger reconciliation), phase #4 “Realized versus
unrealized P/L” dependency and phase #5 “Stale or missing data alerts”. No checklist
completion, issue closure or merge. These are historical **simulation records**,
not validated investment results.

## Outcome and acceptance boundary

Recovered: exact row origins, saved state/marks/journal/code, parent snapshots,
workflow corroboration, valuation arithmetic and fresh provider rejection evidence.
**Zero market sessions, prices, returns or trades are accepted as corrections.**
No correction manifest or reconciled account view is authorized. `investigation.json`
is an explicitly unresolved evidence inventory, not a migration instruction.
The read-only verifier produces an evidence report; it cannot import data, write
accounts, authorize a mapping or advance a simulation. Existing complete-universe,
source-session replay and ambiguous-ledger gates remain in force. Both accounts
remain blocked. Reports and health warnings are unchanged.

All six original stock/crypto state, journal and performance files remain identical
to baseline main. Original signals, reports and accepted ingestion pointers are
also untouched. Exact original and historical Git blobs are copied into a separate
content-addressed evidence directory; each has SHA-256, Git blob ID, commit and path
in the inventory. No history file was sorted, deduplicated, normalized or backfilled.

## Stock trace and root cause

Physical CSV lines below count the header as line 1. Full source commits, raw row
hashes (including line endings), snapshots and parent links are in
[investigation.json](investigation.json). The GitHub connector independently
confirmed output commit IDs and changed blob IDs; local Git reproduces the bytes.

| Line | Saved label/value | Origin commit | Producer run | Date semantics at that commit |
| --- | --- | --- | --- | --- |
| 25 | September 18 / 9883.03 | `b163470d704e81e467c31a16cda4b696d9712948` | [35290276018](https://github.com/iikaitlynii/trading-bot/actions/runs/35290276018) | UTC wall-clock run date |
| 26 | September 19 / 10029.89 | `1fd8d61514f3846166afc25f83756bc02853546e` | [35408807697](https://github.com/iikaitlynii/trading-bot/actions/runs/35408807697) | UTC wall-clock run date |
| 27 | September 18 / 10053.48 | `30bc3a88ef4290f583e16ef7f3a298a51ee28708` | [35673407133](https://github.com/iikaitlynii/trading-bot/actions/runs/35673407133) | Latest provider index date |

All three commits append exactly one row; their journals are unchanged from their
parents. Cash is 2069.745377657432 with the same four holdings. Saved signal prices
reproduce equity as 9883.032966614384, 10029.886624885465 and 10053.484391604416.
These match the saved rounded valuations. They are distinct mark vectors, so
identical date labels do not establish a repeated identical valuation.

`e87e91d` changed UTC labels to Chicago run dates on September 19; `531669d` then
changed to provider index dates. The third disputed run used the latter version,
checked only equality against the last date, and moved state backward from
September 19 to September 18. It did not enforce strictly increasing sessions.
This mixed date convention and incomplete replay guard explains the duplicate and
ordering defect. It does not identify the underlying market session for the first
two rows. Old code used `dropna()` and did not archive original response indexes or
retrieval clocks; stale last observations could be consumed.

Workflow logs independently confirm each printed label, value, zero new actions
and output commit. [workflow-evidence.json](workflow-evidence.json) contains selected
connector-decoded lines (not original provider bytes), run/head metadata and the
artifact inventory: zero artifacts for each of the three runs. Logs do not contain
original per-symbol provider timestamps or full input histories.

The four later frozen Yahoo responses already archived from run 41954673207
corroborate four-symbol saved mark vectors at **September 16, September 17 and
September 18**, respectively, after matching the original four-decimal mark basis.
[stock-corroboration.json](stock-corroboration.json) pins those response hashes.
`corroborate_stock()` recomputes the matches. This exposes likely stale observations
behind the first two labels, but these later responses cannot prove what exact
indexed inputs were originally downloaded. They are not an independent provider,
and their null November 4 bars mean they are not accepted ingestion bundles.
The third run explicitly claimed September 18 in its code/logs; independent
contemporaneous source authentication is still absent.

**No date reassignment is made.** Assigning the first rows to the matching later
provider dates would also collide with neighboring legacy labels. Whole-account
replay must reconcile earlier valuations and entry labels, not just sort these
three rows. Other weekend labels are August 29, September 5 and September 12.
A current download, commit timestamp, calendar guess or matching rounded mark vector
alone cannot authorize deletion/relabeling or recomputation of P/L.

## Crypto identity, coverage and additional missing observations

Fresh read-only Yahoo chart requests preserve exact HTTP bodies under `evidence/`.
[crypto-probes.json](crypto-probes.json) records endpoints, separate request/retrieval
UTC clocks, HTTP status, SHA-256, provider metadata and coverage diagnostics. Nothing
was placed in accepted snapshots/bundles or used by a trader.

| Requested symbol | HTTP/result | Completed-session coverage |
| --- | --- | --- |
| PEPE-USD | 404 / provider Not Found | No usable observations; provider wording does not prove delisting |
| PEPE24478-USD | 200 / invalid OHLCV | November 4, 2026 bar entirely null |
| DOGE-USD | 200 / invalid OHLCV | November 4, 2026 bar entirely null |
| SHIB-USD | 200 / invalid OHLCV | November 4, 2026 bar entirely null |
| BONK-USD | 200 / invalid OHLCV | November 4, 2026 bar entirely null |

The four 200 responses each have 731 ordered unique timestamps. The completed range
is November 5, 2024–November 4, 2026: 730 calendar slots, 729 finite positive,
range-consistent OHLCV observations through November 3, then a null November 4 bar
at Unix timestamp 1793750400. Completed timestamps are midnight UTC with no interior
calendar gaps. The extra current unfinished observation is not eligible. No prior
close, adjusted close, quote metadata or unfinished bar fills the null session.
Candidate raw closes range about 0.000002–0.000026 USD. This is a provider-internal
range check, **not** an independently synchronized price-consistency verification;
no such independent series or authenticated legacy PEPE responses were obtained.

Identity evidence reviewed through web tools:

- [Yahoo candidate quote](https://finance.yahoo.com/quote/PEPE24478-USD/) identifies
  Pepe USD and describes an Ethereum token; the profile search identifies CCC /
  CoinMarketCap. Existing archived Yahoo search also separates similarly named
  PEPECOIN-USD, PEP-USD and other assets.
- [CoinMarketCap Pepe](https://coinmarketcap.com/currencies/pepe/) identifies UCID
  **24478**, Ethereum/ERC-20 and links to the exact explorer address
  [0x6982508145454ce325ddbe47a25d4ec3d2311933](https://etherscan.io/token/0x6982508145454ce325ddbe47a25d4ec3d2311933).
  That page links [pepe.vip](https://www.pepe.vip/) as the project website.
- The exact explorer link is observable on CoinMarketCap, but the explorer itself
  returned 403. Yahoo profile/history direct web opens returned 429. The history
  search page advertised a one-year date range; this is not coverage proof. Raw
  chart bytes, rather than search snippets, establish the coverage above.

This corroborates the candidate's association with the Ethereum asset, but the
numeric Yahoo suffix is not an authoritative legacy-symbol migration declaration.
The repository's old logical PEPE symbol lacks a frozen chain/contract identity
record. No provider migration announcement or historical continuity comparison was
found. Identity review and independent price continuity remain prerequisites even
if the candidate's missing bar recovers. **No symbol substitution or alias registry
was added.** Provider-side reason and onset for PEPE-USD disappearance remain unknown.

Additional legacy gaps: crypto performance has no August 26 label and stops October
24 while saved signals contain PEPE NO_DATA. This does not prove which source
session, if any, was lost: older labels used wall-clock dates. Four historical exits
use the combined reason `defensive_or_missing_signal`; the label cannot distinguish
which branch caused a sale. No trades are reclassified or regenerated. Current
missing-data protection remains mandatory. Baseline comparison diagnostics also
reject AAPL/MSFT/NVDA/AMZN closes and PEPE history; a fresh report is not fresh data.

## Reproduction and review requirements

`python -m research.reliability.recovery` verifies archive hashes, exact disputed
rows, append-only parent traces, unchanged journals and saved arithmetic, prints a
BLOCKED evidence report and deliberately exits **2**. It does not report a healthy
account merely because the evidence archive verifies. `corroborate_stock()` returns
candidate matches with `verified_market_session: null`.

Seven new regression tests cover saved arithmetic, original duplicate blocking,
archive tampering/unauthorized correction claims, frozen PEPE rejection, exact-symbol
alias rejection, all four frozen null-bar responses and accepted-pointer preservation,
and corroboration without session acceptance. Synthetic fixtures are labeled and
never mistaken for recovered provider data. No production validation rule is relaxed;
there is no independently authenticated reconciled dataset to integrate.

Before a future recovery: obtain contemporaneous indexed inputs or equivalent
independent evidence for all affected valuations/trades, authenticate the logical
crypto asset and provider mapping, compare overlapping timestamped raw prices from
independent sources, require complete latest-session coverage, and submit a separate
versioned correction manifest for review. Pin original row/source hashes, decisions,
rationale and derived output hashes. Preserve the original ledger and replay bounds;
reviewed derived data needs an explicit consumer interface and regression tests.

## Validation

Local final code: **207 Python tests passed**, required compileall and 47-task
roadmap gate passed; all dashboard JavaScript syntax checks and four Node suites
passed. Dashboard, Discovery and all 144 Volume Profile browser combinations passed
using Playwright 1.62.0 with the host Chromium diagnostic override. Copilot pixel
comparisons failed locally with host Chromium 154/fonts differing from the pinned
canonical image; reference screenshots and assertions were not changed. Hosted
PR CI in the digest-pinned image is required for canonical visual acceptance.
All six original account state/journal/performance files were compared byte-for-byte
against main. Whitespace checks passed. Passing software checks does not authenticate
historical sessions, restore provider coverage or establish profitable performance.
