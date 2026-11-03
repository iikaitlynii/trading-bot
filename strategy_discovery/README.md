# Strategy Discovery Lab prototype

Related phase issue #6, exact checklist item **“Paper-only strategy experiments”**.
This additive prototype does not mark that item complete. Evidence is **illustrative
synthetic simulation**, not historical market research, live-paper records or
profitability evidence. No orders, credentials, paid APIs or network access are
needed. No existing engine or saved account file is changed. The PR continuation integrates
the public dashboard, weekly archive and frontend CI checks; see [weekly reports](WEEKLY_REPORTS.md).

## Run offline

From repository root, with the existing requirements installed:

```sh
python -m strategy_discovery.evaluate --output work/discovery-report.json
python -m strategy_discovery.dashboard work/discovery-report.json --output work/discovery.html
python -m unittest discover -s tests -v
python -m compileall -q paper_trader.py crypto_paper_trader.py strategy_comparison.py
```

Open the generated HTML locally. The committed `dashboard_preview.html` and
`demo_report.json` provide a reviewable saved example. Both can be regenerated
with the above commands, substituting their paths. No browser JavaScript, remote
fonts or external assets are required. The dashboard escapes all displayed text.
Dependency/Python versions are recorded, so cross-version report bytes can differ.

## Prototype flow and boundaries

1. `discover(metadata, query)` searches saved public-metadata-shaped records,
   retaining original URLs and provenance. The fixtures are fictional; no real
   video or creator endorsement is asserted.
2. `load` reads a local transcript export. `extract` requires a documented
   authorization basis/reference, canonical YouTube URL, retrieval time and
   ordered segment timestamps. Original text, metadata, permission record and
   canonical JSON SHA-256 travel with the candidate. Timestamped quotes accompany
   each extracted field. Missing captions are missing evidence, never inferred.
3. The conservative parser accepts **six complete, explicit sentences** covering
   timeframe, indicators, entry, exit, risk and execution. It supports only daily,
   long-only SMA regime rules matching the existing research engine. Every extra,
   conflicting, unsupported or incomplete sentence blocks approval. This is a
   narrow controlled-language prototype, not general natural-language extraction.
   The vague fixture deliberately remains unresolved. Parse completeness is not
   factual confidence; every candidate initially needs human review.
4. A reviewer reads full source/quotes, resolves ambiguity in a new documented
   source version, and supplies an explicit decision, identity, time, rationale
   and candidate hash. `approve` reparses the source and refuses changed or
   unresolved candidates. `configuration` revalidates the entire specification
   before evaluation. Changes invalidate review. `specifications/demo.json`
   contains a **synthetic test attestation**, not human acceptance. These local
   records are not authenticated identities: real approvals must be enforced by
   repository review/access controls before historical integration.
5. Isolated JSON specifications select only the fixed `sma_regime_v1` template.
   No executable strategy code is generated, imported from transcripts, evaluated
   or dynamically loaded. Added `code` fields and unknown templates fail closed.
   A new indicator/template would require a separate reviewed implementation and
   tests. Keep future generated code quarantined outside import/search paths,
   with static review and explicit human approval; this prototype needs none.
6. `evaluate` uses **existing** `research_lab.run_variant` on fixed synthetic
   prices with disjoint 120-session train, selection and evaluation windows,
   each preceded by SMA warmup. Holdings reset at each boundary. No tuning or
   automatic approval occurs; “selection” is only a frozen partition name.
   The public synthetic holdout demonstrates plumbing, not an independent OOS
   research result. The input must match the versioned fixture exactly. Missing,
   corrupt, shortened or external historical prices fail closed.
7. Compare each partition against cash, entry-costed buy-and-hold, the existing
   portfolio `current_20_50` variant, and existing trend/momentum through
   `strategy_comparison.calculate`. The report retains engine/rule/evaluator,
   dataset/specification hashes and dependency versions.
8. `submission` produces a queue manifest with **blocked_pending_human_integration**.
   This is not a completed submission to PR #13. That runner currently freezes
   existing comparison rules and its universe; it cannot consume discovered
   specifications without a separately reviewed adapter extension.

## Simulation semantics and comparisons

The existing portfolio engine buys at the signal close with 10 bps adverse
slippage and 10 bps commission, caps initial per-asset allocation at the specified
weight, exits on fast < slow, price < regime or a close below its entry-fill stop.
A close-based stop can gap beyond its threshold. Same-session exit/reentry is
permitted by that engine and explicitly disclosed in the source rules; a stop
can exit and immediately reenter if indicators remain positive. Weight is an
entry allocation cap, not continuously enforced exposure or risk-at-stop sizing.
Positions are marked at the end without forced liquidation. These assumptions
must be reviewed before any historical use. The report does not alter them.

Buy-and-hold uses the first evaluated close and the same entry costs, full initial
allocation and no terminal exit. Existing trend/momentum expose the entire account
using previous-close signals/fills, unlike the capped candidate with same-close
fills. Their return and risk numbers are context, **not evidence of relative skill**.
The old engine's internal `benchmark_return_pct` omits costs; use the separately
labeled costed baseline. JSON preserves original drawdown signs; the dashboard
shows positive loss magnitudes consistently. Sharpe/CAGR/profit factor are legacy
engine outputs on artificial daily fixtures, not statistical evidence.

Research score = 50 × parsed-field completeness + 25 × reproducible synthetic
reviewed evaluation + 25 × sensitivity stability. Stability = 1 / (1 + drawdown
spread in percentage points), using predeclared ±10% fast-SMA perturbations on
the synthetic holdout. Rank never consumes return, win rate or profit factor.
This is a transparent triage heuristic, not a validated robustness statistic.
Every evaluated candidate remains “synthetic-only / unvalidated”; zero independent
market datasets means no historical robustness claim. Do not tune the score or
parameters on the eventual independent holdout.

## Permitted discovery and transcript design

The offline interfaces are the first implementation; **no live YouTube client or
caption downloader is included**. A later opt-in adapter may ingest official
YouTube Data API `search.list`/`videos.list` responses, or permissioned public
metadata exports, retaining video/channel IDs, URL, title, retrieval time, query,
provider and original-response hash. Handle pagination, duplicate video IDs,
quota exhaustion, removed/private videos and unavailable transcripts explicitly;
cache only under applicable policy. API availability is not transcript permission.

Retrieve captions only via authorized owner/editor OAuth access to official
captions APIs, creator-provided licensed exports, or documented explicit creator
permission. Public visibility and a caption button do not alone authorize copying.
No scraping, access-control bypass, embedded-description code execution or
unofficial transcript endpoints. Persist permission scope/reference, acquisition
method, language, auto/manual status, timestamps, license/retention restrictions
and withdrawal/deletion status. Keep unavailable or revoked sources blocked and
invalidate affected approvals. Authenticated authorization/retention enforcement,
real API clients and natural-language extraction are future work, not test claims.

## Coordination with merged work (updated October 29, 2026)

PRs #13–#16 are now merged in the integration base. The initial boundaries below
remain preserved; historical evaluation in #13 still fails closed, and #15 does
not authenticate provider evidence. Weekly integration is described in
[WEEKLY_REPORTS.md](WEEKLY_REPORTS.md).

| PR | Ownership preserved | Integration gate |
| --- | --- | --- |
| [#13](https://github.com/iikaitlynii/trading-bot/pull/13) | `research/validation/**`, protocol and tests | Add a reviewed candidate exposure/portfolio adapter after the frozen evaluator is accepted; preserve frozen protocol/version hashes, OOS policy and baseline semantics. Do not feed new rules into the current fixed-rule runner silently. |
| [#14](https://github.com/iikaitlynii/trading-bot/pull/14) | monitoring modules, workflow and tests | Later report missing discovery evidence as unavailable, not healthy; no new schedule or external health integration here. |
| [#15](https://github.com/iikaitlynii/trading-bot/pull/15) | `data_contracts/**`, `research/datasets/**`, tests | Require accepted immutable snapshot hash, session/calendar coverage, adjustment basis and benchmark window agreement before enabling historical evaluation. |

The continuation additionally edits dashboard navigation/markup/CSS, adds isolated
discovery JavaScript and archive data, adds weekly/frontend tests, and extends CI
checks under the user’s explicit dashboard-integration scope. Performance report
logic, monitoring, data contracts, validation, PR #16 research and roadmap evidence
remain unchanged. Branch is `agent/strategy-discovery-lab`;
integration remains sequential and human reviewed. No merges, issue closure or
checklist changes are requested.

## Dashboard design

The original standalone HTML preview remains a synthetic developer artifact.
The public `docs/index.html` dashboard now includes the lab and weekly archive;
see [WEEKLY_REPORTS.md](WEEKLY_REPORTS.md).
Its sections cover research queue, source/permission/timestamp evidence,
uncertainty, review gate, held-out comparisons, blocked submission dependencies
and reproducibility. Semantic headings, keyboard-operable details, table captions,
column headers, high-contrast text and responsive table scrolling support review.
No button claims to approve a strategy or launch research in this static preview.

For future integrated UI: provide filters for source/indicator/timeframe/review
state, side-by-side original transcript and extracted rule evidence, explicit
reviewer resolutions, revision history and hash-bound approval. Separate
“needs review”, “approved for simulation”, “blocked dataset”, “queued” and
“evaluated” states; show review as pending until authenticated acceptance.
Surface sample size, exposure/timing differences, fee assumptions, leakage checks,
parameter sensitivity, regime/asset coverage and uncertainty before ranking.
No “profitable” badge or one-click deployment. Historical comparisons stay disabled
until PR #13/#15 integration is accepted. The continuation runs integrated browser regression checks for saved/empty/missing
archives, source text safety, mobile layout and existing dashboard functionality.
Human acceptance and real evidence integration remain future work.
