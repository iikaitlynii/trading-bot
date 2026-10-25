# Proposed issue: Build reproducible held-out validation and risk-impact research protocol

Status: proposed, not created or assigned in GitHub. Agent roles are proposed ownership, not GitHub usernames or launched workers.

Phase tasks: #1 “Audit stock and crypto entry/exit logic”, “Identify assets and signals causing the largest losses”, “Evaluate on out-of-sample periods”, “Maintain strategy version and comparison history”; #2 “Measure risk-control impact on returns”; #6 “Walk-forward validation”.

Owner: Testing Agent (lead), Strategy Agent and Risk Agent reviewers.

Dependencies: Task 2's frozen dataset/session contract. Draft protocol can proceed independently; evaluate only after snapshot acceptance.

File ownership and conflict reservation: New research/validation_protocol.md, research/validation/ and tests/test_validation_protocol.py. Any strategy_comparison.py changes require a separate future scope decision; do not edit paper traders or strategy rules.

Acceptance criteria:

- [ ] Freeze asset universe, rule versions, train/selection/test dates and cost assumptions before evaluation; archive dataset/code hashes and environment versions.
- [ ] Evaluate existing unmodified rules against cash and buy-and-hold with explicit same-close execution limits; propose realistic fill studies separately rather than silently changing rules.
- [ ] Add leakage/future perturbation, independent cost accounting and reproducibility checks; report asset/signal loss attribution and cap impact with unavailable/insufficient-data states.
- [ ] Document historical versus synthetic evidence and avoid profitability assertions from CI pass status.

Use a dedicated branch, link the parent phase issue and exact task, post a plan, and open a separate PR. Run the handbook unittest/compile checks and task-specific tests. Keep trading simulated; no strategy changes, brokerage connections, real orders, automatic merge, issue closure or unchecked-to-checked transitions without merged CI and human acceptance.
