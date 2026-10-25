# Proposed issue: Complete yearly reports and PDF exports with integrated dashboard verification

Status: proposed, not created or assigned in GitHub. Agent roles are proposed ownership, not GitHub usernames or launched workers.

Phase tasks: #4 “Monthly and yearly performance reports”, “CSV and PDF exports”, “Realized versus unrealized P/L”, “Mobile layout and accessibility”.

Owner: Reports Agent (calculation lead), Dashboard Agent (UI/browser owner), Testing Agent reviews.

Dependencies: Task 2's accepted benchmark schema for crypto comparisons; task 4's health schema for freshness UI. Yearly/PDF fixtures and browser harness can begin earlier.

File ownership and conflict reservation: performance_reports.py, docs/performance_reports.js, docs/index.html, docs/dashboard.css, docs/reporting/README.md, tests/test_performance_reports.py, tests/dashboard_browser.py. Reports and Dashboard work sequentially on these shared files; CI changes reserved to Testing Agent.

Acceptance criteria:

- [ ] Add yearly aggregates with previous-year boundary, partial launch/current-year coverage, missing data and cross-year reconciliation tests.
- [ ] Add PDF exports matching CSV/JSON totals and warning/classification text for both accounts; show unavailable benchmarks rather than fabricate prices.
- [ ] Run Chromium on the combined #9/#11/new panel at seven widths; test keyboard/focus, account switching, stale responses, downloads and failure paths. Extend the browser fixture response types for JSON as needed.
- [ ] Document benchmark provenance, saved-mark limits and unavailable P/L. Require human acceptance; do not rewrite account history or claim full WCAG certification.

Use a dedicated branch, link the parent phase issue and exact task, post a plan, and open a separate PR. Run the handbook unittest/compile checks and task-specific tests. Keep trading simulated; no strategy changes, brokerage connections, real orders, automatic merge, issue closure or unchecked-to-checked transitions without merged CI and human acceptance.
