# PR #13 historical-validation review fixes

Review: https://github.com/iikaitlynii/trading-bot/pull/13#issuecomment-6392862973

The former truthy `snapshot_acceptance` check was an assertion by the same caller
who supplied the data. It did not verify provenance. A relabelled synthetic CSV
could therefore receive an accepted historical status.

The runner now rejects every `evidence: historical` request before dataset reads,
rule validation or calculation. This includes absent/false/true acceptance values,
review-looking strings/objects, claimed contract metadata, source endpoints and
hashes. The obsolete acceptance field is also rejected for synthetic protocols.
Successful reports always declare synthetic evidence; no accepted-historical
report branch remains. The synthetic protocol's evaluator hash and summary report
have been regenerated; prices, strategy rules and historical dates are unchanged.

## PR #15 boundary

Merged PR #15 main: `0cd6613fbcbe41279d837d4b6e6e75e890789c73`.
Its `data_contracts.load`/`validate` APIs verify immutable canonical snapshots and
session eligibility. They do not prove provider authenticity. Its synthetic
SPY/ETH/BTC fixture archives must never be treated as historical prices simply by
rewriting classification. This runner intentionally does not adopt an incomplete
adapter or modify those modules/archives. Historical evaluation remains unsupported
even for an otherwise valid v1 snapshot. A future reviewed adapter must address
independent provider evidence, per-market calendars, comparison eligibility and
adjustment basis; see `research/validation_protocol.md`.

Compatibility check performed offline against the three actual PR #15 archives:
`data_contracts.load` validated each; in-memory copies with classification changed
to `historical research` also passed `validate`, demonstrating the distinction
between structural eligibility and authenticity. Passing each original/copy as
claimed provenance to a historical protocol was rejected (six cases). No archive
was changed. Their individual validation does not imply that the three snapshots
share a comparison window; a future adapter must use `validate_comparison` too.

## Regression evidence

Five new unittest methods cover relabelled synthetic inputs, acceptance variants,
claimed schema/hash verification, early rejection before price IO/calculation,
rejection of synthetic acceptance flags, and CLI failure without creating or
replacing reports. Before the fix the 12-method validation suite produced nine
assertion failures and one error, including acceptance of relabelled synthetic data.
After the fix all 12 methods pass. Existing byte reproducibility, cost, rule parity,
period-boundary and leakage-mutation tests continue to pass.

Commands executed using Python 3.12.14, pandas 3.1.0, NumPy 2.5.4, yfinance 1.7.0:

```sh
python -m unittest discover -s tests -p test_validation_protocol.py -v
python -m unittest discover -s tests -v
python -m compileall -q paper_trader.py crypto_paper_trader.py strategy_comparison.py research/validation data_contracts tests
python scripts/check_roadmap.py
node --check docs/dashboard.js
node --check docs/performance_reports.js
node tests/performance_dashboard_test.js
```

- Standalone PR #13 branch regression suite: **79 tests passed**.
- Current-main integration suite, including merged PR #15: **98 tests passed**.
- Targeted validation suite: **12 tests passed**.
- Compile, roadmap consistency, dashboard syntax/regression and whitespace checks passed.
- Two complete synthetic evaluations produced identical report bytes. The refreshed
  summary archives the full-report hash and continues to mark history unavailable.
- Every current-main file in the integration workspace matched its GitHub blob hash;
  only PR #13-owned validation files were overlaid. No data-contract changes were
  included in this branch update.

These are local software regression results, not historical performance or provider
verification. CI/review are separate evidence. Everything remains simulated; no
merge, issue closure or roadmap completion is requested or performed.
