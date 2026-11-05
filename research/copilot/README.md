# Simulation-only AI Trading Copilot v1

Related #20 data-availability and causal-evaluation boundaries; phase #3 exact items
**“Explain simulated signals”** and **“Volume and volatility analysis”**. This is a
rule-based educational assistant, not a connected language/vision model. No issue,
checkbox, portfolio, research-health threshold or execution engine is changed.

## Foundation audit

Pinned main: `f2dced5103ed3668b1dd3c0974cb490fc6028686`. GitHub merge metadata and
local `git merge-base --is-ancestor` verify #21 (`a601392`), #18 (`caa2ea6`), and #19
(`f2dced5`). AGENTS.md, ROADMAP.md and #20 were read first. The stock acceptance
pointer is absent in this pinned main. Chart CSVs are independent unverified
consumers; Volume Profile remains HISTORICAL / APPROXIMATE / UNVALIDATED. Legacy
historical adapter, accounting, provider availability and same-close defects in
#20 are not repaired here. Genuine health warnings remain visible and unchanged.

## Implemented data path

`python -m copilot.publish` reads only the #21 stock acceptance pointer. It verifies
the frozen bundle, bounded archive paths, all four stock symbols, full snapshot
contracts, real classification, source/session/clock metadata, raw HTTP success,
and immutable hashes. It **reparses** preserved provider bytes and compares the
entire HLCV export and snapshots with that result. A rehashed but unrelated CSV is
insufficient. No caller indicator values, legacy chart CSV or uploaded screenshot
can bypass this gate. Zero/missing volume, future clocks, unfinished/missing
sessions, stale evidence or any missing symbol block the whole universe.

VERIFIED means accepted collector evidence passes these contracts. It is not an
independent second-provider audit, corporate-action certification or proof of
exchange authenticity. The configured collector/repository are trust boundaries;
raw hashes establish integrity, not provider identity. A compromised publisher can
forge public artifacts; deployers must protect repository write access and CI.

The producer reuses #18's actual JavaScript SMA20/50, simple-window RSI14, ATR14 and
bands through Node, then freezes the input bars and analysis before any subsequent
outcome. Trend SMA20>SMA50 plus RSI14>55 gives BUY SETUP; inverse trend plus RSI14<45
gives SELL SETUP. Otherwise WAIT. The penultimate completed bar forms the setup;
the latest completed bar supplies context. No fills, returns or portfolios are
created. ATR and volume are context, not directional votes. Missing indicator
warmups block directional states. Source timestamps identify session closes;
observation timestamps identify when the producer actually recorded the state.

Expiration is the next XNYS completed-session boundary, including holidays and
early closes. At or beyond expiration the browser forces WAIT, even if a scheduled
refresh failed. Unsupported calendar dates block publication. Browser clocks are
not authoritative secure time; protect the host clock and producer environment.

`docs/copilot/observations/<sha256>.json` is create-only. `latest.json` points to
frozen bytes; the browser checks its path and SHA-256 and recomputes the rules.
Changing a displayed state to WAIT on expiry does not rewrite the record. Rule
version, implementation hash, bundle hash and input bars permit replay. Repeated
identical publication is idempotent; a later timestamp creates a new record.
Archives are public market-derived records, never private screenshots or secrets.
The initial archive truthfully records WAIT/BLOCKED, rather than fabricating data.

A manual, separate Actions workflow publishes observations with the ingestion
publication lock. It makes no provider requests or account changes. Run it after
accepted ingestion. There is no Copilot schedule yet; refresh timing needs human
operational review. If input publication fails, archived evidence remains and the
UI expires to WAIT. Existing ingestion/health workflows remain untouched.

## Interface and screenshots

GREEN ↑ BUY SETUP, RED ↓ SELL SETUP, GRAY ⏸ WAIT use text, icons and accessible
contrast. The panel includes identity, daily timeframe, source and observation
timestamps, quality/reasons, conditions, uncertainty, invalidation and three
hypothetical scenarios. All existing sections and saved stock/crypto values stay.
The matching saved 60-session/24-bin Volume Profile is shown strictly as historical,
**approximate, unvalidated** context, never a direction vote or exact trade volume.
Current accepted Volume Profile confirmation is explicitly missing.

The screenshot picker accepts PNG/JPEG/WebP with signature/type/size checks, pre-decode
header dimension limits, actual browser decoding and bounded dimensions (5 MiB, 16 MP, max side 8192). SVG and other
formats, invalid decoding, tiny/ambiguous dimensions are rejected. Images and
optional user-transcribed labels remain memory-only, use object URLs, and are
cleared/revoked on replacement or the clear button. Notes use plain form values;
no image HTML, metadata, filenames or notes are inserted as executable markup,
network requests, storage, repository files or observation records. Closing the
page clears this feature's memory; browser/OS caches, extensions and screenshots
are outside its control. Image parsing uses the browser's decoder sandbox; this
is not an antivirus or proof that a chart is readable/authentic.

**Not implemented:** automatic visual label extraction, OCR, chart recognition,
price/volume/indicator inference or external vision analysis. The UI states this
explicitly. User-transcribed notes are unverified, do not affect symbols/rules,
and screenshot mode always forces WAIT, even with a valid market observation.
Unreadable notes must remain unknown. No image is sent to any model service.

## Optional alert-ingestion interface — design only, NOT CONFIGURED

GitHub Pages serves static public files; it cannot host a private webhook receiver.
A future separately approved deployment would use:

TradingView HTTPS POST → rate-limited API → authenticated validator → durable
idempotency/observation store → independent provider verification worker →
public-safe market-only observation publisher. Private payloads stay off Pages.

Proposed v1 JSON fields: `schema_version:1`, `event_id` (UUID), `sent_at` (UTC ISO
instant), `symbol` (configured exchange-qualified allowlist), `timeframe` (configured
allowlist, initially 1d), `source_session` (canonical session), `secret` (rotatable
per-sender credential). Strict field/type/length and body-size validation; reject
unknown fields. No indicator claims are accepted as verified. No prices or order
instructions are part of this interface. A receive timestamp is assigned server-side.

Do not claim TradingView natively signs requests. Direct alerts can use a long,
random, per-sender JSON secret over TLS with constant-time comparison, redacted
before logs/storage; never a URL query credential. Where a trusted relay is
configured, HMAC-SHA256 over the exact body plus timestamp and nonce can be used
instead. Neither mechanism authenticates market correctness. Alert timestamps
must be within a configured short window (e.g. ±120 seconds); future/stale alerts
are rejected. Store event ID + sender/body hash atomically before acknowledging;
exact retries return idempotent success, conflicting duplicate IDs reject. Keep
replay keys longer than the acceptance window, including across restarts. Rate
limits must be atomic/shared across instances, per sender and globally; cap body
size before parsing and return 429 on limits. Fixed upstream allowlists prevent
SSRF. No payload-controlled source URLs or filenames. Use TLS, secret management,
rotation, bounded timeouts, minimal CORS, authenticated private read APIs, retention
and audit logs. Do not use IP filtering as the only authentication mechanism.

Receiver acceptance **never** authorizes a directional setup: independently fetch
and validate the completed provider session and indicators, then apply the same
quality gates. Missing upstream evidence means WAIT. No receiver, secret input,
public upload endpoint or backend deployment is included in this PR.

## Hosting and cost

Implemented runtime: static GitHub Pages + existing Actions runner with Python
and Node; no paid infrastructure, paid API, external model or new dependency in
production. Manual publishing consumes normal repository Actions minutes/storage
and public artifact space subject to the account's existing quota. No billing or
services are requested/enabled. Archive growth should be monitored before adding
a schedule. A backend would require separately approved hosting, durable database,
private storage, secrets, monitoring and provider access; its cost depends on
vendor/traffic/retention and is **not provisioned or quoted as a commitment**.

## Evaluation and limitations

All outcomes remain PENDING. No accuracy, false-positive rate, simulated P/L,
drawdown or profitability number is invented. Future evaluation must append
separate results linked to immutable observation hashes, choose horizons before
outcomes, use later verified sessions, enforce causal next-observable fills,
model fees/spread/slippage, distinguish no-data from flat/no-trade, and preserve
original records. Synthetic tests demonstrate software behavior only, not a
historical strategy evaluation. This PR does not complete phase 4 evaluation.

## Reproduction

- `python -m unittest discover -s tests -v`
- `python -m compileall -q paper_trader.py crypto_paper_trader.py strategy_comparison.py copilot`
- `python scripts/check_roadmap.py`
- `python tests/discovery_fixtures.py`
- `node tests/copilot_engine_test.js` and existing performance/discovery/chart suites
- `python tests/copilot_browser.py` (Playwright, Chromium and Pillow)
- Existing `tests/dashboard_browser.py`, `tests/discovery_browser.py`, `tests/volume_profile_browser.py`

Six reviewed synthetic panel screenshots cover BUY/SELL/WAIT at 375/1280 pixels.
Refresh intentionally with `python tests/copilot_browser.py --update`, inspect the
images, then run without that flag. Keep renderer/fonts consistent; pixel changes
require review, never automatic baseline replacement in CI. Tests also exercise
expiry/missing/tampered artifacts, malformed images, local-only privacy behavior,
clearing, keyboard controls and touch targets. No browser test makes market or
performance assertions from synthetic inputs.
