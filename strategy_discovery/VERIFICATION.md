# Verification evidence

Base: main `3a9d20878ab31a267e43cf2b65efe63b441bf75d`.
Shell Git proxy was unavailable. Retrieved the pinned base through the GitHub
connector and verified all 120 blob hashes before testing in an isolated working
copy. Publication uses the same connector and the real main commit as parent.

Local checks (Python 3.12, existing `/workspace/.venvs/trading-bot` dependencies):

- `python -m unittest discover -s tests -v`: **78 passed**, including 11 new
  discovery/dashboard regressions and all 67 base regressions.
- Handbook `compileall` for both traders and comparison: passed; new discovery
  modules/test also compile.
- `python scripts/check_roadmap.py`: passed, 47 unchanged task records.
- Existing dashboard JavaScript syntax checks: passed.
- Report generation and static HTML rendering: passed offline.
- Whitespace check: passed.

New regressions cover metadata search and timestamp provenance, documented
permission requirements, missing/conflicting/negated/untrusted text, hash-bound
review and specification tampering, invalid risk/period/timestamp bounds,
network-free deterministic repeated evaluation, independent hand-calculated entry
costs, exact engine parity, future-price prefix invariance, invalid/external-data
rejection, return-independent ranking and HTML escaping.

Known limits: no real video discovery/transcript retrieval, no authenticated human
approval, no accepted historical data, no independent OOS finding, no completed
submission to PR #13 and no integrated dashboard browser acceptance. Those are
explicit design/integration gates, not passing test claims. Synthetic report
versions may vary across Python/dependency releases; report bytes repeat within
the recorded environment. Every result remains illustrative and unvalidated.
