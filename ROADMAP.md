# Kaitlyn's Trading — shared roadmap

Track the live checklists and evidence in GitHub Issues, not in this static document.

| Phase | Issue | Lead roles | Status |
| --- | --- | --- | --- |
| 1. Strategy validation | [#1](https://github.com/iikaitlynii/trading-bot/issues/1) | Strategy, Data, Testing | Partial; 3 tasks await human acceptance; #1 closed with unchecked tasks |
| 2. Risk management | [#2](https://github.com/iikaitlynii/trading-bot/issues/2) | Risk, Testing | 4 controls implemented; human acceptance pending |
| 3. Charts and analysis | [#3](https://github.com/iikaitlynii/trading-bot/issues/3) | Dashboard, Strategy | Task-specific acceptance unverified |
| 4. Dashboard and reports | [#4](https://github.com/iikaitlynii/trading-bot/issues/4) | Dashboard, Reports | 3 tasks await human acceptance; yearly/PDF partial |
| 5. Monitoring and automation | [#5](https://github.com/iikaitlynii/trading-bot/issues/5) | Data, Reports, Testing | Partial warnings/UI; monitoring acceptance unverified |
| 6. Advanced research | [#6](https://github.com/iikaitlynii/trading-bot/issues/6) | Strategy, Testing | Task-specific acceptance unverified |

## Workflow
To Do → In Progress (assigned and branch created) → Testing (pull request open and CI running) → Reviewed (CI passed and evidence checked) → Completed (merged, reviewer checked off).

**Important:** This repository currently has issue-based checklists, not a provisioned GitHub Projects kanban board or a fleet of continuously running AI workers. Completion is intentionally manual after verification.

## Verification after PRs #7–#11

Audit of main `af90a9f11dc273dc16cbbe1c93297709e342b94a`, October 24, 2026 (America/Chicago): all five PRs merged; main regression (62 tests), backtest/stress and Pages build/deployment succeeded. **No task checkbox changed**: AGENTS.md requires explicit human evidence confirmation, and submitted review lists are empty. Ten task implementations await that confirmation; partial and unverified tasks stay unchecked.

[Full 47-task audit, evidence and limitations](research/roadmap_verification.md) · [machine-readable evidence](research/roadmap_evidence.json) · [next five priorities and separate issue proposals](research/next_round/README.md).

Phase 1 issue #1 was already closed with all eight checkboxes unchecked. PM must reconcile that status with a human; this update changes no issue state. Monthly reports do not complete monthly **and yearly** scope, and CSV does not complete CSV **and PDF** scope. Browser acceptance of the integrated reporting panel is pending. Passing checks are not profitability evidence.

Run `python scripts/check_roadmap.py` to reject inconsistent or premature completion metadata. It never modifies GitHub issues and cannot authenticate remote human-review evidence. Completion remains a manual review decision.
