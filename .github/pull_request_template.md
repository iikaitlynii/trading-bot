## Linked roadmap issue and exact task
Closes / relates to #

## What changed?

## Simulation-only safety
- [ ] No live orders, brokerage connections, exchange trading, or credentials introduced
- [ ] Missing market data does not cause a simulated sale
- [ ] No look-ahead in backtests (if applicable)

## Verification
- [ ] `python -m unittest discover -s tests -v`
- [ ] `python -m compileall -q paper_trader.py crypto_paper_trader.py strategy_comparison.py`
- [ ] Evidence attached: logs / before-and-after results / screenshots
- [ ] Relevant limitations explained

## Reviewer decision
- [ ] Tests passed in GitHub Actions
- [ ] Behavior independently reviewed
- [ ] Corresponding issue checkbox updated **after merge**
