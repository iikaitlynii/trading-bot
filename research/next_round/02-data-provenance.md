# Proposed issue: Specify session-aware immutable research datasets and benchmark provenance

Status: proposed, not created or assigned in GitHub. Agent roles are proposed ownership, not GitHub usernames or launched workers.

Phase tasks: #1 “Check missing, stale, duplicate records”, “Maintain strategy version and comparison history”; #4 benchmark/report prerequisites.

Owner: Data Agent (lead), Testing Agent reviews.

Dependencies: Can start after this verification PR; publish schema contract before tasks 3–5 integrate.

File ownership and conflict reservation: New research/datasets/ and data_contracts/ modules, new tests/test_dataset_contracts.py. Reserve market_data.py for a later explicitly scoped PR; no paper engine/strategy edits in this task.

Acceptance criteria:

- [ ] Provide immutable stock/crypto/BTC daily snapshots with source URL, retrieval time, timezone/session convention, adjustment basis, content hash and dependency/version metadata.
- [ ] Specify exchange holidays and early closes, completed UTC crypto days, omitted sessions, duplicates, mixed as-of dates and corporate-action limitations. Never fill missing data into a sell signal.
- [ ] Document the existing raw-versus-adjusted price mismatch and publish an explicit consumer contract; preserve saved paper records.
- [ ] Deterministic offline tests reject omitted/stale/unfinished or mismatched data and verify hashes/endpoints. No brokerage APIs or live execution.

Use a dedicated branch, link the parent phase issue and exact task, post a plan, and open a separate PR. Run the handbook unittest/compile checks and task-specific tests. Keep trading simulated; no strategy changes, brokerage connections, real orders, automatic merge, issue closure or unchecked-to-checked transitions without merged CI and human acceptance.
