# Roadmap verification after PRs #7–#11

Audit date: October 24, 2026 (America/Chicago). Source main: `af90a9f11dc273dc16cbbe1c93297709e342b94a`.
Read AGENTS.md and ROADMAP.md before reviewing code, all five PR diffs, all 47 issue tasks and their completion rules.

## Completion decision

**Zero task checkboxes changed.** Ten tasks have implementation and automated evidence suitable for human acceptance, but none has recorded human evidence confirmation. GitHub's submitted-review lists for #7–#11 were empty; PR descriptions retain pending human-review decisions. Merge authorship alone is not a confirmation of task evidence. AGENTS.md explicitly requires “the relevant pull request is merged, CI passes, and a human reviewer confirms the evidence.” This audit is agent verification, not that human confirmation.

Issues #1–#6 retain their existing checklist and state. Issue #1 was already **closed/completed while all eight tasks were unchecked** when read; this is an inconsistency, not proof of completion. Project Manager should reconcile it with a human; this PR does not reopen or close any issue.

Acceptance criteria in the phase issues consist of task names plus generic PR/test/reviewer rules; there are no more detailed task-specific criteria to silently assume. The table distinguishes bounded implementation from full task acceptance. “Implemented pending review” is never completed.

## Merged changes and evidence

| PR | Actual implementation reviewed | Automated evidence |
| --- | --- | --- |
| [#7](https://github.com/iikaitlynii/trading-bot/pull/7) | market_data.py rejects bad prices/session labels; paper engines require completed compatible prices; missing data never becomes a defensive sell | tests/test_market_data_quality.py; tests/test_paper_safety.py |
| [#8](https://github.com/iikaitlynii/trading-bot/pull/8) | strategy_comparison.py validates histories/ticker selection; explicit cash baseline; lagged exposures and fixed additive turnover costs | 12 deterministic comparison tests, independent scalar ledger, future perturbation and cost checks |
| [#9](https://github.com/iikaitlynii/trading-bot/pull/9) | desktop/mobile section navigation, skip/focus controls, responsive tables and portfolio context | documented Chromium run and seven viewport widths in research/dashboard_verification.md; browser script outside unittest discovery |
| [#10](https://github.com/iikaitlynii/trading-bot/pull/10) | paper_risk.py validates caps, budgets and risk snapshots; both engines persist exposure/peak warnings; crypto now holds the entire account on any missing configured feed | 10 risk tests; updated full-feed pause regressions |
| [#11](https://github.com/iikaitlynii/trading-bot/pull/11) | read-only FIFO/reconciled reporting, monthly summaries, CSV/JSON, dashboard panel and reporting workflow | 20 reporting tests including Node DOM harness; no yearly or PDF implementation |

PR #10 supersedes #7's allowance for trading healthy crypto symbols when an unheld feed is missing. Assess the integrated code, not the older audit's partial-feed behavior.

## Verification results

- Main [regression run 40154933802](https://github.com/iikaitlynii/trading-bot/actions/runs/40154933802): success; job log confirms **62 tests passed** (0.745s), syntax and known live-order-pattern checks passed.
- Main [backtest run 40154933828](https://github.com/iikaitlynii/trading-bot/actions/runs/40154933828): success; backtest and stress steps passed. This workflow runs bot.py/stress_test.py, not an out-of-sample validation of every engine or comparison.
- Main [Pages run 40154933714](https://github.com/iikaitlynii/trading-bot/actions/runs/40154933714): build, report-build-status and deploy succeeded. Deployment is not browser/accessibility acceptance.
- PR head regression runs: #7 40150207133; #8 40150742079; #9 40150916816; #10 40152600433; #11 40153746893 — all success.
- Local verification: all **62 existing tests passed** in 0.612s with the declared-dependency virtual environment. Handbook compilation plus paper_risk.py, performance_reports.py, paper_report.py and tests passed. Both dashboard JavaScript syntax checks passed.
- Initial default-interpreter discovery failed with two missing-yfinance imports. It is not counted as success; the dependency-equipped interpreter produced the passing run.
- Integrated Chromium rerun **blocked**: Playwright is absent in the environment. No current browser pass is claimed. Prior #9 browser evidence predates #11's panel; #11's DOM harness passes but cannot establish layout or screen-reader behavior.
- Shell Git fetch failed because its configured proxy was unavailable. Changed files were read at the pinned main SHA through the GitHub connector and overlaid into an isolated local verification copy; the original checkout/account records were not edited. Local tests are corroboration of changed modules; hosted main CI provides the exact-checkout evidence.

All regression inputs are synthetic illustrative estimates; reports are simulated forward paper records. Historical backtest success is not evidence of profitability. No market-provider calls, trader runs against saved accounts, or live orders were used for this audit.

## Every roadmap task

Each entry maps to the exact checkbox text in issues #1–#6. All remain unchecked. Test paths and PR evidence are also machine-readable in [roadmap_evidence.json](roadmap_evidence.json).

| ID / phase issue | Exact task | Assessment | Evidence / what remains |
| --- | --- | --- | --- |
| P1-1 / #1 | Audit stock and crypto entry/exit logic | partial | PR #7, PR #8; Missing-data and comparison timing audited; complete paper-engine entry/exit audit and human acceptance remain. Same-close execution assumptions are not executable-fill evidence. |
| P1-2 / #1 | Separate missing price data from defensive sell signals | implemented pending review | PR #7, PR #10; Human evidence confirmation required; PR #10 supersedes #7 by pausing all crypto trading on any unavailable configured feed. |
| P1-3 / #1 | Identify assets and signals causing the largest losses | partial | PR #11; Aggregate FIFO and winning/losing sell counts exist; no verified per-asset/signal largest-loss attribution. |
| P1-4 / #1 | Check missing, stale, duplicate records | partial | PR #7, PR #8, PR #11; Trader corruption checks work; exact stock holiday/early-close calendar, comparison omitted/stale/unfinished sessions and provider/corporate-action verification remain. |
| P1-5 / #1 | Compare strategies against buy-and-hold and cash | implemented pending review | PR #8, PR #11; Human acceptance required for illustrative fixed-cost comparison versus buy-and-hold and zero-interest cash. Forward crypto benchmark unavailable; no profitability claim. |
| P1-6 / #1 | Model fees and slippage | implemented pending review | PR #8; Human acceptance required for fixed 10bps fee + 10bps slippage estimates. No realistic liquidity/impact ledger or paper-engine transaction costs. |
| P1-7 / #1 | Evaluate on out-of-sample periods | unverified | PR #8; Rolling 120-session comparison is not a frozen out-of-sample selection/evaluation protocol. |
| P1-8 / #1 | Maintain strategy version and comparison history | unverified | PR #8; Identical-input repeatability exists; immutable datasets, dependency locks, strategy versions and comparison archives do not. |
| P2-1 / #2 | Configurable simulated position-size limits | implemented pending review | PR #10; Entry-only configurable caps; drift is warned, not liquidated. Human acceptance required. |
| P2-2 / #2 | Evaluate stop-loss and trailing exits | unverified | No task-specific implementation and acceptance evidence verified in PRs #7–#11. |
| P2-3 / #2 | Track asset concentration | implemented pending review | PR #10; Per-asset weights and aggregate exposure persisted; independent accounts. Human acceptance required. |
| P2-4 / #2 | Simulated drawdown warnings | implemented pending review | PR #10; Inclusive advisory threshold and persisted peaks verified; legacy peaks not reconstructed. Human acceptance required. |
| P2-5 / #2 | Paper-only pause for unreliable data | implemented pending review | PR #10; All configured/held feeds required before account mutation; retry remains available. Human acceptance required. |
| P2-6 / #2 | Measure risk-control impact on returns | unverified | No task-specific implementation and acceptance evidence verified in PRs #7–#11. |
| P2-7 / #2 | Risk scorecard per strategy | unverified | No task-specific implementation and acceptance evidence verified in PRs #7–#11. |
| P3-1 / #3 | Indicators alongside paper trade markers | unverified | No task-specific implementation and acceptance evidence verified in PRs #7–#11. |
| P3-2 / #3 | Multiple chart timeframes | unverified | No task-specific implementation and acceptance evidence verified in PRs #7–#11. |
| P3-3 / #3 | Explain simulated signals | unverified | No task-specific implementation and acceptance evidence verified in PRs #7–#11. |
| P3-4 / #3 | Side-by-side asset comparison | unverified | No task-specific implementation and acceptance evidence verified in PRs #7–#11. |
| P3-5 / #3 | Volume and volatility analysis | unverified | No task-specific implementation and acceptance evidence verified in PRs #7–#11. |
| P3-6 / #3 | Market-regime dashboard | unverified | No task-specific implementation and acceptance evidence verified in PRs #7–#11. |
| P3-7 / #3 | Signal history timeline | unverified | No task-specific implementation and acceptance evidence verified in PRs #7–#11. |
| P3-8 / #3 | Downloadable research charts | unverified | No task-specific implementation and acceptance evidence verified in PRs #7–#11. |
| P4-1 / #4 | Navigation sidebar | implemented pending review | PR #9; Human acceptance required. Prior PR browser evidence exists; current browser rerun blocked by missing Playwright. |
| P4-2 / #4 | Stocks, Crypto, Research and Reports sections | implemented pending review | PR #9; Native section links and portfolio controls implemented. Human acceptance and integrated browser rerun required. |
| P4-3 / #4 | Monthly and yearly performance reports | partial | PR #11; Monthly only; yearly summaries and cross-year tests absent. |
| P4-4 / #4 | Strategy comparison leaderboard | partial | PR #8, PR #9; Asset benchmark table exists; no task-specific verified ranked strategy leaderboard and missing/stale eligibility policy. |
| P4-5 / #4 | Realized versus unrealized P/L | implemented pending review | PR #11; FIFO and reconciled unrealized values verified; unavailable crypto breakdown is correctly suppressed. Human acceptance required; saved marks are not independently repriced. |
| P4-6 / #4 | CSV and PDF exports | partial | PR #11; Daily/monthly/summary CSV implemented; PDF absent. |
| P4-7 / #4 | Mobile layout and accessibility | partial | PR #9, PR #11; PR #9 targeted seven-width/keyboard evidence predates new report panel. Current browser rerun blocked by missing Playwright; integrated report-panel browser and accessibility acceptance remain. |
| P4-8 / #4 | Trading terminology glossary | unverified | No task-specific implementation and acceptance evidence verified in PRs #7–#11. |
| P5-1 / #5 | Monitor scheduled GitHub Actions failures | unverified | No task-specific implementation and acceptance evidence verified in PRs #7–#11. |
| P5-2 / #5 | Last successful data refresh indicator | partial | PR #9, PR #11; Saved as-of labels exist; not a verified last-successful-refresh indicator tied to workflow outcome. |
| P5-3 / #5 | Stale or missing data alerts | partial | PR #7, PR #10, PR #11; Holds and report warnings exist; no verified durable alert lifecycle/operational notification. |
| P5-4 / #5 | Optional research email summaries | unverified | No task-specific implementation and acceptance evidence verified in PRs #7–#11. |
| P5-5 / #5 | Weekly family performance summaries | partial | PR #9; Existing weekly UI is smoke-tested; independent weekly reconciliation and delivery acceptance unverified. |
| P5-6 / #5 | Research-condition alerts | partial | PR #9; Existing on-page saved-observation filters are smoke-tested; no task-specific condition/threshold/staleness acceptance. |
| P5-7 / #5 | Automated strategy quality checks | partial | PR #7, PR #8, PR #10, PR #11; CI regressions verify mechanics; do not establish automated strategy quality gates for fresh, held-out performance. |
| P5-8 / #5 | Strategy change audit log | unverified | No task-specific implementation and acceptance evidence verified in PRs #7–#11. |
| P6-1 / #6 | Walk-forward validation | unverified | No task-specific implementation and acceptance evidence verified in PRs #7–#11. |
| P6-2 / #6 | Trend versus mean-reversion research | unverified | No task-specific implementation and acceptance evidence verified in PRs #7–#11. |
| P6-3 / #6 | Bull, bear and sideways regime analysis | unverified | No task-specific implementation and acceptance evidence verified in PRs #7–#11. |
| P6-4 / #6 | Cross-asset correlation analysis | unverified | No task-specific implementation and acceptance evidence verified in PRs #7–#11. |
| P6-5 / #6 | Diversified ETF benchmark | unverified | No task-specific implementation and acceptance evidence verified in PRs #7–#11. |
| P6-6 / #6 | Crypto liquidity and volatility research | unverified | No task-specific implementation and acceptance evidence verified in PRs #7–#11. |
| P6-7 / #6 | Paper-only strategy experiments | unverified | No task-specific implementation and acceptance evidence verified in PRs #7–#11. |
| P6-8 / #6 | Evaluate ML against simple baselines | unverified | No task-specific implementation and acceptance evidence verified in PRs #7–#11. |

Phase 3 and Phase 6 have pre-existing research/UI code, but these PRs supply no task-specific end-to-end acceptance evidence for their checklist items. Unverified means unverified in this audit, not an assertion that no code exists.

## Automated completion checks

`python scripts/check_roadmap.py` validates all 47 stable task IDs, phase counts, unique names, referenced test paths, PR evidence and completion prerequisites. Negative tests reject an attempted completion without human confirmation, failed CI, unmerged PR evidence, and missing task verification. It never edits GitHub checkboxes or issue states.

This is a local evidence-consistency gate, not remote evidence authentication. A human must check the linked review, task scope and CI SHA before updating the live issue. A URL or JSON field is not itself proof. No AI agent may fabricate human-review metadata.

The updated branch passes **67 tests** (62 existing plus five completion-gate tests). The evidence checker, expanded compilation, JavaScript syntax and changed-file whitespace checks pass.

Agent CI adds the gate, reporting syntax/JavaScript checks and missing reporting/roadmap push paths. Browser testing remains explicitly pending; no optional dependency failure is hidden.

## Next round

See [coordination plan](next_round/README.md) and five separate proposed issue bodies. No new issues or running agents are created by these proposals. Integration and GitHub issue completion remain human-reviewed.
