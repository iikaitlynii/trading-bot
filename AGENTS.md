# Kaitlyn's Trading — AI agent handbook

This repository is an **educational, simulated trading research project**. No real orders, brokerage APIs, exchange order submission, secrets, or live execution. Treat any request for such features as out of scope.

## Shared coordination
- The source of truth is GitHub Issues [#1–#6](https://github.com/iikaitlynii/trading-bot/issues), pull requests, CI checks, and commits—not chat claims.
- Each agent takes a checklist item from its phase issue, posts a plan, works on a dedicated branch, and opens a pull request linked to the issue. Avoid simultaneous edits to the same file.
- Work may proceed in parallel on **independent branches**, but integration is sequential and reviewed.
- Checkboxes remain unchecked until the relevant pull request is merged, CI passes, and a human reviewer confirms the evidence. A commit alone is not sufficient.
- Never automatically close an issue merely because an agent generated code.
- A failed or missing test is **not** success. Missing historical prices are **not** sell signals.

## Agent roles
| Role | Primary ownership |
| --- | --- |
| Project Manager | Scope, task assignment, integration review, issue status |
| Strategy Agent | Signal logic, benchmarks, out-of-sample research |
| Risk Agent | Simulated exposure limits, drawdown, risk evaluation |
| Data Agent | Price quality, timestamps, missing values, provenance |
| Dashboard Agent | UI, accessibility, research presentation |
| Testing Agent | Deterministic regression tests, CI, backtest leakage checks |
| Reports Agent | P/L reconciliation, weekly and monthly summaries |

## Required change checklist
1. Reference the phase issue and exact checkbox item.
2. Describe expected behavior and how it is tested.
3. Include regression tests for any bot logic change.
4. Run `python -m unittest discover -s tests -v` and `python -m compileall -q paper_trader.py crypto_paper_trader.py strategy_comparison.py`.
5. Document whether results are historical backtests, simulated live paper records, or illustrative estimates.
6. Preserve the simulation-only invariant.
7. Wait for review and successful CI before marking completion.

## Parallelism
GitHub Issues do **not** create running ChatGPT agents. Independent ChatGPT chats also do not coordinate automatically. Codex or another coding-agent service may work on separate issues/branches only if connected and explicitly launched with repository access. GitHub Actions runs automated checks, not autonomous research agents.
