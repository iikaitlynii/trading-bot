# Phase 2 simulated-account risk audit

Relates to issue #2, exact items: “Configurable simulated position-size limits”,
“Track asset concentration”, “Simulated drawdown warnings”, and
“Paper-only pause for unreliable data”. These items remain unchecked pending
review, successful CI and merge. No issue closure is requested.

## Baseline reviewed

Based on main d187d9b, including merged PR #7 (daily data validation), #8
(deterministic strategy comparison regressions), and #9 (dashboard accessibility).
Stocks previously sized new positions to 20% of current equity, constrained by
cash but without an explicit portfolio cap. Crypto sized entries to 10% and
limited total invested capital to 40%, but could trade healthy symbols when an
unheld asset's feed failed. Neither account tracked persisted equity peaks or
reported concentration and drawdown warnings. Existing holdings were not resized.

## Configuration and behavior

Environment variables are read each run; no credentials are involved. Values
are finite fractions from 0 to 1 inclusive. Invalid values raise before signals,
account writes or trades; there is no fallback to an unsafe configuration.

| Variable suffix | STOCK_PAPER_ default | CRYPTO_PAPER_ default |
| --- | --- | --- |
| MAX_POSITION_WEIGHT | 0.20 | 0.10 |
| MAX_EXPOSURE | 0.80 | 0.40 |
| DRAWDOWN_WARNING | 0.10 | 0.10 |

For example `STOCK_PAPER_MAX_POSITION_WEIGHT=0.15` and
`STOCK_PAPER_MAX_EXPOSURE=0.60` allow entries up to 15% of marked equity and total
invested capital up to 60%. Crypto defaults preserve its 60% cash reserve;
changing its exposure setting changes that reserve. A zero entry/exposure limit
blocks purchases. Zero warning threshold warns even at zero drawdown.

Entry budget = max(0, min(cash, equity × position limit,
equity × exposure limit − current invested value)). Each purchase consumes the
remaining exposure budget, in existing ticker order. Minimum purchases remain
$50 stocks / $25 crypto. These are entry controls: price moves or reduced limits
can leave existing positions above caps. Such breaches produce warnings and
prevent purchases beyond the aggregate cap; they do not force liquidation.
Healthy defensive signals still produce simulated exits.

Each successfully processed session saves `peak_equity` and a `risk` object in
its existing state JSON: equity, invested value, fractional per-asset weights,
aggregate exposure, drawdown, warning and limit-breach flags. Drawdown is
(peak − equity) / peak, with an inclusive warning threshold. The peak persists
across runs. Legacy accounts initialize the peak from the greater of starting
cash and current equity: older historical peaks are not reconstructed. Warnings
are printed and saved in account state, not added to legacy CSV schemas or UI.

Both accounts require every configured and held asset to have reliable,
compatible completed-session prices before trading. Crypto now pauses the
entire session on any missing configured feed, including an unheld asset; its
NO_DATA signal diagnostics are retained. No buy, defensive sell, valuation,
peak update, or run-date consumption occurs on a pause. Stocks retain PR #7's
full-session hold. Pauses are automatically retried on a later invocation with
healthy data; they are not manual persistent locks. Existing same-date
idempotency guards still apply. Unknown held symbols also prevent valuation.

## Evidence and limitations

Tests use synthetic, offline prices and fixed clocks for the new account tests.
They validate illustrative simulated account arithmetic and safety, not realized
returns or profitability. No historical backtest or live market experiment was
run. No broker/exchange integration, real orders, or real-money functionality
was added; stored research and paper records were not regenerated.

The accounts remain independent; there is no combined stock/crypto exposure
budget, correlation, sector risk, liquidity or volatility sizing. Caps do not
model fees, slippage or fractional-fill rounding. Positions are long-only;
negative/nonfinite cash, quantities or prices fail validation. Persisted files
are assumed structurally valid; concurrent writers, interrupted writes, manual
cash flows and account recovery need separate work. Drawdown samples completed
sessions only; intraday losses and legacy peaks may be missed. Warnings are
advisory and do not pause for drawdown. Data pauses cannot guarantee vendor
correctness; PR #7's calendar/freshness tolerances still apply. Pauses have
console/signal evidence but no separate durable incident log or dashboard alert.

Stop-loss/trailing-exit evaluation, return-impact measurement and strategy risk
scorecards remain unimplemented Phase 2 work. Parameter defaults preserve prior
entry behavior, except the intentional full-session crypto data pause. There is
no evidence here that any risk threshold improves returns.

## Local verification

Python 3.12.14:
- `python -m unittest discover -s tests -v`: **42 tests passed** in 0.528s,
  including 10 new risk tests and updated partial-feed expectations.
- `python -m compileall -q paper_trader.py crypto_paper_trader.py strategy_comparison.py paper_risk.py tests`: passed.
- `git diff --check`: passed.

The first test attempt failed with three module import errors because yfinance
was absent. Installing the declared requirements resolved this; the full suite
then passed. Hosted CI and independent review remain separate requirements.
