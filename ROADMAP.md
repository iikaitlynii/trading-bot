# Kaitlyn's Trading — shared roadmap

Track the live checklists and evidence in GitHub Issues, not in this static document.

| Phase | Issue | Lead roles | Status |
| --- | --- | --- | --- |
| 1. Strategy validation | [#1](https://github.com/iikaitlynii/trading-bot/issues/1) | Strategy, Data, Testing | To Do / partial code exists |
| 2. Risk management | [#2](https://github.com/iikaitlynii/trading-bot/issues/2) | Risk, Testing | To Do |
| 3. Charts and analysis | [#3](https://github.com/iikaitlynii/trading-bot/issues/3) | Dashboard, Strategy | To Do |
| 4. Dashboard and reports | [#4](https://github.com/iikaitlynii/trading-bot/issues/4) | Dashboard, Reports | To Do |
| 5. Monitoring and automation | [#5](https://github.com/iikaitlynii/trading-bot/issues/5) | Data, Reports, Testing | To Do |
| 6. Advanced research | [#6](https://github.com/iikaitlynii/trading-bot/issues/6) | Strategy, Testing | To Do |

## Workflow
To Do → In Progress (assigned and branch created) → Testing (pull request open and CI running) → Reviewed (CI passed and evidence checked) → Completed (merged, reviewer checked off).

**Important:** This repository currently has issue-based checklists, not a provisioned GitHub Projects kanban board or a fleet of continuously running AI workers. Completion is intentionally manual after verification.

## Existing work to verify
The crypto paper trader now distinguishes `NO_DATA` from `DEFENSIVE`; the stock paper trader skips sessions when data coverage is incomplete; a dashboard compares historical benchmarks. These are code changes, **not yet evidence that the strategies are profitable**. Verify them with regression tests and follow-up reviews before checking off Phase 1.
