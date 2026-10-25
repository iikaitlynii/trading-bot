# Proposed issue: Monitor scheduled workflow outcomes and stale research outputs

Status: proposed, not created or assigned in GitHub. Agent roles are proposed ownership, not GitHub usernames or launched workers.

Phase tasks: #5 “Monitor scheduled GitHub Actions failures”, “Last successful data refresh indicator”, “Stale or missing data alerts”, “Automated strategy quality checks”.

Owner: Testing Agent (lead), Data Agent and Reports Agent review.

Dependencies: Can implement workflow-state fixtures immediately; use task 2's session contract for final freshness acceptance.

File ownership and conflict reservation: New monitoring/ and tests/test_monitoring.py; new .github/workflows/research-health.yml. CI owner alone edits agent-ci.yml. Dashboard integration deferred to task 5 to avoid docs/index.html conflict.

Acceptance criteria:

- [ ] Distinguish failed, cancelled, never-run, in-progress, successful-with-old-data and genuinely refreshed runs using immutable workflow IDs and source timestamps.
- [ ] Use stock session and crypto daily freshness rules; an all-missing comparison run must not make old CSVs appear newly successful.
- [ ] Persist read-only health evidence and deterministic failure/recovery tests; document alert state and deduplication. Do not send email/messages or add account credentials.
- [ ] Keep refresh status separate from performance quality and strategy profitability; no trading-policy changes.

Use a dedicated branch, link the parent phase issue and exact task, post a plan, and open a separate PR. Run the handbook unittest/compile checks and task-specific tests. Keep trading simulated; no strategy changes, brokerage connections, real orders, automatic merge, issue closure or unchecked-to-checked transitions without merged CI and human acceptance.
