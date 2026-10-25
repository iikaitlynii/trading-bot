# Data provenance verification

Base: latest main `3a9d20878ab31a267e43cf2b65efe63b441bf75d` (rechecked before publication). Branch: `agent/data-provenance`.

Scope: phase #1 “Check missing, stale, duplicate records” and “Maintain strategy version and comparison history”, following `research/next_round/02-data-provenance.md`. Additive research contract only; no paper-engine, strategy, saved account, roadmap or issue-state changes. Schema and consumer limitations are in [README.md](README.md).

## Local results

- Full handbook `python -m unittest discover -s tests -v`: **86 passed**, comprising 67 existing and 19 new deterministic dataset/calendar tests. Existing reporting DOM regression also passed through this suite.
- `python -m compileall -q paper_trader.py crypto_paper_trader.py strategy_comparison.py data_contracts tests`: passed.
- `python scripts/check_roadmap.py`: passed, all 47 tasks remain subject to authentic human review.
- `node --check docs/dashboard.js` and `node --check docs/performance_reports.js`: passed.
- `git diff --cached --check`: passed.
- Known live-order/credential-pattern scan of paper traders and new modules: passed. The new module has no network/trading calls.

Tests used `/workspace/.venvs/trading-bot/bin/python` with the existing research dependencies. Shell Git fetch could not connect to its configured proxy; no alternate network route or credentials were introduced. All 120 base files were fetched through the GitHub connector at the pinned SHA. Their Git blob hashes were verified and the reconstructed source tree exactly matched main tree `556393b3812f39188cfdb297b1c37044af5e388a`. The PR commit is created against that actual main parent through GitHub's Git-data API, not against the unrelated pre-existing local audit branch.

All new prices are synthetic illustrative fixtures. No fresh provider data, historical profitability, provider authenticity, publication latency, consumer adoption or live-paper run is claimed. The bounded XNYS calendar supports 2024–2027; reviewed extensions and future exceptional closures remain necessary. Original saved paper records were not executed or rewritten. Hosted CI results are reported on the pull request; local success does not substitute for hosted checks or human acceptance. No merge or roadmap completion is authorized by these results.
