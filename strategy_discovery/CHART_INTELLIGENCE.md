# Chart intelligence and permission-aware discovery

Related #3 **“Explain simulated signals”**, **“Volume and volatility analysis”**
and #6 **“Paper-only strategy experiments”**. This additive work changes no
checklist, account, strategy execution, historical gate, health alert or archive.
No proprietary code, branding or indicators are used. No live orders exist.

## Dashboard chart

`docs/chart_intelligence.js` draws native SVG OHLC candles, observed volume and
20/50-bar simple moving averages. The initial **TEACHING FIXTURE / SYNTHETIC /
UNVALIDATED** example is deterministic artificial OHLCV, unrelated to portfolio
holdings. The 30/90-bar selector changes the visible range, not bar aggregation
or indicator warmup. Latest ten bars are also available in an accessible table.

Calculations are independently implemented from these public definitions:

- [Simple moving average](https://en.wikipedia.org/wiki/Moving_average#Simple_moving_average): arithmetic mean of the last N closes.
- [Relative strength index](https://en.wikipedia.org/wiki/Relative_strength_index): simple-window mean positive/negative changes over 14 changes, **not Wilder-smoothed RSI**. Zero gains/losses yields 50; no losses yields 100.
- [Average true range](https://en.wikipedia.org/wiki/Average_true_range): arithmetic mean of 14 true ranges using previous closes, **not Wilder smoothing**.
- [Bollinger bands](https://en.wikipedia.org/wiki/Bollinger_Bands): SMA20 ± twice the population standard deviation of 20 closes. These are descriptive bands; no price probability is asserted.

Directional votes: SMA20 vs SMA50 and RSI14 >55 / <45, otherwise neutral. ATR and
volume are non-directional context. Counts distinguish agreement, disagreement,
neutral and missing evidence. Any missing component blocks the setup. A defensive
setup is an educational exposure-review cue, never a short order. Signals use the
penultimate supplied bar and cannot change when the final context bar changes.
No returns, fill claims, calibrated confidence or profit probabilities are computed.
Two correlated votes are not independent evidence or guaranteed profitability.

Local upload contract (maximum 2 MB / 5,000 bars):

```json
{
  "schema_version": 1,
  "symbol": "EXAMPLE",
  "evidence": "historical-unvalidated",
  "provenance": {
    "source": "Document the authorized provider/export URL here",
    "retrieved_at": "2026-10-30T12:00:00Z",
    "adjustment": "raw OHLC; document split/dividend treatment",
    "session_convention": "Document completed sessions/timezone/calendar"
  },
  "bars": [
    {"session":"2026-10-29","open":100,"high":102,"low":99,"close":101,"volume":null}
  ]
}
```

Allowed evidence is `synthetic` or `historical-unvalidated`; no verified class is
accepted. Prices must be finite, positive, ≤10¹², ordered and internally consistent;
volume is nonnegative, ≤10¹⁸, or explicitly null. Numeric bounds prevent overflow. Empty/short histories remain missing;
invalid uploads clear the chart and signals. No sorting, gap filling, fabricated
volume or conversion of close-only data into candles occurs. Calendar completeness,
finished-session status, adjustment correctness and provider authenticity are
**not verified by this viewer**. Local uploads are ephemeral; reload resets them.

The existing `data_contracts` snapshot has **close only**. The chart envelope is
an isolated display contract, not an extension/bypass of that historical boundary.
An accepted OHLCV/session/provenance adapter is future work. Existing saved account
charts, trade history and all other sections remain separate and preserved.

## Metadata discovery and candidate review

`strategy_discovery.metadata` consumes authorized saved responses from official
YouTube Data API v3 `search.list` / `videos.list`, or documented permissioned public
metadata exports. It makes no network request and accepts no credentials. Official
API references: [search.list](https://developers.google.com/youtube/v3/docs/search/list),
[videos.list](https://developers.google.com/youtube/v3/docs/videos/list),
[caption download authorization](https://developers.google.com/youtube/v3/docs/captions/download).
Live discovery is visibly **BLOCKED**, since no authorized API client/credential is
configured and this environment's network policy excludes the YouTube API host.
This implements export ingestion/search, not live query/pagination fetching.

Envelope fields:

```json
{
  "provider": "youtube-data-api-v3",
  "interface": "search.list",
  "retrieved_at": "2026-10-30T12:00:00Z",
  "permission": {
    "basis": "authorized API response",
    "reference": "Operator's documented authorization/policy reference",
    "scope": "metadata",
    "status": "active"
  },
  "response": {"items": []}
}
```

Supply the unmodified authorized API response as `response`. For licensed exports,
use provider `permissioned-metadata-export` and basis `licensed metadata export`
or `creator permission`. Preserve applicable license/retention restrictions as
additional permission fields. Never place credentials in an export or repository.
Permission declarations are local assertions, not authenticated grants. The
operator must honor provider terms, retention/deletion and revoked permissions.

```sh
python -m strategy_discovery.metadata work/authorized-export.json \
  --query 'daily sma' --output work/metadata-queue.json
# Optional: authorized local transcript array in the existing source format:
python -m strategy_discovery.metadata work/authorized-export.json \
  --query 'daily sma' --transcripts work/authorized-transcripts.json \
  --output work/metadata-queue.json
```

The manifest retains **all supplied records**, query matches, video/channel IDs,
canonical URLs, title, publication time (or missing), acquisition time, original
response/envelope, permission details and SHA-256 provenance. Query matching uses
title/description tokens; it does not infer rules. A next-page token produces an
explicit partial state; missing next-page tokens establish only the end of the
supplied response. Duplicate IDs require operator reconciliation. API errors,
non-video IDs and invalid/future/naive retrieval times fail. Unknown providers,
inactive rights and private/unavailable records stay visibly blocked, including
records excluded from text matches. No metadata export is automatically published.

Optional transcripts require **separate active** `creator permission` or `owned
captions`, a reference, a matching video URL and timezone-aware acquisition time
no earlier than metadata acquisition. No caption download, restricted transcript
scraping, third-party transcript endpoint or natural-language rule invention is
included. The existing controlled parser keeps timestamped quotes and missing
rules unresolved. `candidate_for` binds original metadata to the source and
returns `needs_human_review`; `lab.approve` and `configuration` reparse and
revalidate that binding. Changed/revoked attached rights invalidate acceptance.
Human review still requires the candidate hash, reviewer, decision, timestamp and
rationale, enforced by repository review/access controls. Bridged reviews require
a timezone-aware timestamp after acquisition and no later than the current time. Local attestation files
are not authenticated human identities; an offline artifact cannot detect a later
provider withdrawal. Reacquire/check rights before reuse and remove withdrawn
local artifacts under applicable policy.

Upload the generated manifest in **Strategy Discovery Lab → Video strategy
discovery** to inspect sources, permission assertions, hashes, rule quotes and
uncertainties. The browser treats every local file as unvalidated, uses inert text
and canonical source links, and has no approval or execution control. Displayed
hashes are assertions; authoritative recomputation/review uses the Python bridge.

Non-synthetic sources remain rejected by `strategy_discovery.evaluate`, even with
a locally approved specification. Existing historical verification, frozen OOS
periods, warmup, fee/slippage and comparison safeguards remain unchanged. The lab's
10 bps commission plus 10 bps adverse slippage are illustrative, potentially
inadequate for illiquid assets, and same-close fills are optimistic. No historical
integration or realistic venue calibration is claimed by this change.

Weekly reports and archives stay inside the existing dashboard, with unchanged
hash/schema/evidence checks. Imported metadata is neither a completed weekly
review nor a historical evaluation and is never relabeled as synthetic evidence.
Health monitoring is untouched; loading a chart/export cannot turn an alert green.

## Verification

```sh
python -m unittest discover -s tests -v
python -m compileall -q paper_trader.py crypto_paper_trader.py strategy_comparison.py
python scripts/check_roadmap.py
python tests/discovery_fixtures.py
node tests/performance_dashboard_test.js
node tests/discovery_dashboard_test.js
node tests/chart_intelligence_test.js
python tests/dashboard_browser.py
```

New regressions cover hand-calculated indicators, warmups, flat/mixed/missing
states, prefix/lag invariance, invalid OHLCV, metadata identity/provenance, revoked
rights, partial/empty exports, malformed API responses, human-review/hash binding,
incomplete rules and rejection of real-source evaluations. Browser checks cover
candles/volume/ranges, failed-upload signal clearing, synthetic reset, inert source
titles, canonical links and all existing account/navigation/mobile checks.

## Integration after merged PR #21

PR #18 was updated from main `d6ee522` (including merged PR #21) by a normal merge;
there were no main-branch conflicts. PR #21 ingestion, immutable response/export
hash checks, unique atomic staging files, scheduled ingestion/publication workflows,
saved portfolios, reports and monitoring files remain byte-identical to that main.
No provider requests, backfills, portfolio advancement or alert overrides were run.
The imported OHLCV viewer remains separate from the close/HLCV ingestion boundary;
PR #21 does not supply opens, validate local chart uploads or enable historical
candidate evaluations. Metadata permission and human-review gates are unchanged.

Compatibility was checked against PR #19 head `93384fe` using a disposable detached
worktree. The original shared HTML/CSS/script insertion points conflicted; PR #18's
additive chart section, local intake block, scoped CSS and deferred script tags
were relocated to independent anchors. The resulting three-way merge is clean,
without importing Volume Profile into PR #18 or changing PR #19's branch. Browser
checks now allow that optional extra panel and derive Back-navigation expectations
from actual navigation order, while still requiring every baseline panel.

Validation on the updated branch:

- **182 Python tests passed**, including PR #21 stale/partial universe, raw/export
  corruption, atomic writer isolation and no-download-fallback regressions.
- All three frontend suites, all six JavaScript syntax checks, required compilation
  and the 47-task roadmap consistency gate passed.
- Both Chromium suites passed: saved Stocks/Crypto values; chart/volume/range and
  invalid-upload clearing; video source safety; populated/empty/missing archives;
  responsive/keyboard navigation; unavailable portfolio data; no-JavaScript links.
- New browser assertions preserve saved missing-price flags and findings across
  chart/video interactions, including the warning against treating missing data
  as a sell signal. Monitoring regression tests continue to reject stale/missing
  evidence rather than declaring it healthy.

The disposable PR #18 + #19 integration passed **187 Python tests**, all three
frontend suites, the integrated dashboard browser suite and PR #19's browser suite
(all 36 profiles, responsive layout and failed-report clearing). Regenerating the
36 profiles against main's stock CSV succeeded twice with identical output bytes.
These are software/compatibility checks, not historical strategy validation.
PR #19's checked-in snapshot is not silently refreshed; its legacy provenance,
volume approximation and regeneration limitations still apply. Its old statement
that the collector substitutes missing volume describes the pre-#21 collector;
PR #21 now rejects missing volume. No report, account, health evidence, issue or
roadmap checkbox was changed by this integration work.
