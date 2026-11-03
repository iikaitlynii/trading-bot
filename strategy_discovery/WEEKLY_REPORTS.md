# Dashboard weekly research and archive

PR #17 continuation, based on main `4bc18db87c21205d30944ad87740fa9e1b662953`
(includes merged PRs #13–#16). Related phase #6 **“Paper-only strategy experiments”**.
No roadmap evidence or task checkbox is modified.

## Public behavior

The existing dashboard now has a native **Strategy Discovery Lab** navigation
link and section. Portfolio switching, performance reports and the other research
panels retain their original handlers. The lab reads its own same-origin
`strategy-discovery/index.json` and verified per-week JSON files. Reports and
archive selection render inside the dashboard; there is no messaging, alerting,
email, notification, external publication service or additional scheduled job.

The committed index is deliberately empty. **No weekly research activity has
been recorded or invented for this integration.** The old demo report is not
loaded or imported. No sample week or fabricated historical return is published.

- **NOT RUN**: no published weekly report, no simulation, or saved evidence could
  not be verified. Missing/corrupt archive data is unavailable, not a zero result.
- **EMPTY**: an actually generated report has zero recorded fixture reviews, or
  there are no archive entries. An empty index does not claim a research run.
- **UNVALIDATED**: all synthetic simulation and historical evidence. No historical
  validation or profitability badge is available.

Every report shows its actual week (Monday–Sunday UTC) and generation timestamp.
Selecting a previous report does not imply that this week or intervening weeks
ran. Only completed weeks can be archived; current/partial-week publishing is
rejected. The newest recorded week is selected initially, with its dates visible.

Reports contain source-review records and their permission/provenance, candidate
extractions and timestamped quotations, ambiguities, review gates, synthetic
simulation/baseline results when run, and research-quality rankings. Rankings use
the original completeness/reproducibility/sensitivity heuristic, never returns.
The simulator's baseline timing/exposure limitations remain visible. Candidate
parser status remains `needs_human_review`, even when a synthetic test attestation
is used to exercise evaluation. The dashboard cannot grant approval or run code.

## Evidence ledger and publication

The prototype still has **no real YouTube retrieval or authenticated source-review
adapter**. The weekly publisher accepts original synthetic fixture records only.
Changing a source to real, claiming historical evidence, supplying precomputed
performance metrics, omitting source permission, using future activity, duplicating
a source in a week or mismatching a reviewed specification fails closed.

A ledger is a JSON object with `schema_version: 1` and an explicit `reviews` list.
Each record has `reviewed_at` (UTC `Z`), `reviewer` and the complete permissioned
`source` object accepted by `lab.extract`. Optional `specification` must pass the
original hash-bound review gate and exactly match that source. The original
source acquisition and specification review must precede the review activity.
There is no default import of sample sources, no auto-discovery count and no
automatic weekly backfill. Dates/counts are derived from the dated review records,
not the fact that a file or a demo exists.

The report generator reparses sources, computes candidates/ambiguities/rankings,
and **runs the existing isolated synthetic evaluator itself** if a matching
specification is supplied. It refuses caller-supplied result fields. Only records
inside the requested week count. Source and candidate hashes, the ledger and its
hash, specification/dataset/evaluator hashes and the original evaluation
limitations remain attached. A report must exactly match recomputation before
publication.

Example for an explicitly empty completed week, only after an actual review of
whether any evidence records exist:

```sh
python -m strategy_discovery.weekly \
  --ledger strategy_discovery/samples/empty_weekly_ledger.json \
  --week-start 2026-10-19 \
  --archive docs/strategy-discovery
```

This would publish an **EMPTY** report, not claim sources were reviewed. It has
**not been run against the public archive in this PR**. The CLI uses the actual
UTC generation time; it has no backdated-generation option. To demonstrate fixture
activity in tests, run `python tests/discovery_fixtures.py`; those test artifacts
are written to `work/`, never the public archive.

Each weekly file is immutable. A locked writer validates the existing archive,
writes one new week exclusively, hashes its exact bytes and atomically replaces
the index, ordered newest first. Exact-byte API retries are idempotent; a later
CLI rerun with a different generation time refuses to replace that week. There
is no correction/delete command. A future correction protocol requires reviewed
versioning. Unsafe paths, duplicates, missing/corrupt files, symlinks, orphan
files and concurrent writers fail closed. A malformed archive is not silently
rebuilt. Version publication and public data changes require repository review.

Browser checks verify the archive paths, unique chronological weeks, file SHA-256,
schema/classification, counts, dates, source fixtures and states before rendering.
All source/quote/title text uses textContent, never innerHTML. Generation is the
stronger recomputation boundary; a SHA-256 manifest proves consistency, **not an
authenticated reviewer or independent provider authenticity**. A repository writer
can alter source files and index together; normal PR review/access controls remain
required. The offline fixture marker is not proof that a real provider authorized
anything, so real-source and historical publication remain unsupported.

## Tests and operational limits

```sh
python -m unittest discover -s tests -v
python -m compileall -q paper_trader.py crypto_paper_trader.py strategy_comparison.py strategy_discovery
python scripts/check_roadmap.py
node --check docs/dashboard.js
node --check docs/performance_reports.js
node --check docs/research_extensions.js
node --check docs/strategy_discovery.js
python tests/discovery_fixtures.py
node tests/performance_dashboard_test.js
node tests/discovery_dashboard_test.js
# Optional browser dependencies: Playwright and /usr/bin/chromium
python tests/dashboard_browser.py
python tests/discovery_browser.py
```

Existing CI gains new-module compilation, JavaScript syntax and both dashboard
behavior regressions. Browser checks are executed locally with intercepted saved
fixtures (no market/YouTube requests) and remain optional because browser packages
are not repository runtime dependencies.

Merged PR #13 intentionally rejects historical evidence even with asserted
acceptance; merged PR #15 validates structure/session eligibility, not provider
authenticity. Neither authorizes turning these synthetic records into historical
results. Merged PR #14 monitoring and PR #16 Heikin-Ashi research remain unchanged.
Real retrieval, authenticated human review, accepted historical candidate adapter,
independent OOS research, scheduled evidence collection and historical robustness
are still future work. The public archive stays empty until an actual, reviewed
report is published. This PR is code/integration evidence only.
