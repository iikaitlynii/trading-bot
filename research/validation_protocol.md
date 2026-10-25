# Frozen-period, simulation-only validation protocol

Relates to Phase #1 “Evaluate on out-of-sample periods”, “Compare strategies
against buy-and-hold and cash”, “Model fees and slippage”, “Identify assets and
signals causing the largest losses”, and “Maintain strategy version and comparison
history”; #2 “Measure risk-control impact on returns”; #6 “Walk-forward validation”.
Scope follows `research/next_round/03-oos-validation.md`. No task is marked complete.

## Evidence and prerequisites

This PR supplies **synthetic demonstration evidence only**. It does not establish
historical out-of-sample performance or profitability. The accepted Task 2 frozen
dataset/session contract was not supplied. Historical evaluation must wait for it.
The runner rejects historical configs without `snapshot_acceptance`; that field
must reference genuine human acceptance evidence, and is not itself authentication.
Do not relabel the synthetic fixture as historical. The existing historical summary
CSVs are not daily price snapshots and cannot substitute for accepted inputs.

Base main: `3a9d20878ab31a267e43cf2b65efe63b441bf75d`. Existing paper traders,
risk controls and `strategy_comparison.py` are unchanged. The evaluated strategies
are specifically the comparison module's **trend** and **momentum** rules, not a
replay of the stock/crypto paper-account engines or their risk controls.

## Freeze before examining evaluation results

Commit a protocol JSON and immutable daily CSV before execution. Archive its commit,
input SHA-256, rule SHA-256, evaluator SHA-256 (checked before each run), provenance,
asset universe, session list, adjustment basis, dependency environment and all dates.
Any revised rule, universe, cost, or period requires a new protocol/version and a
fresh untouched evaluation period; never overwrite evidence to select a winner.
The input hash prevents accidental snapshot replacement; it does not establish
source correctness or prove the research was preregistered.

The universe is frozen to AAPL, MSFT, NVDA, AMZN, DOGE-USD, SHIB-USD, PEPE-USD and
BONK-USD. The fixed rules use 20/50-session means, a 200-session stock or 100-session
memecoin regime mean, and positive 20-session momentum. Exposures lag one session.
Cash and buy-and-hold are reported for every asset and period. There is no fitted
model, hyperparameter search, candidate selection or optimization. “Train” is a
design/diagnostic period; “selection” is a separate diagnostic period that selects
nothing. All candidates appear in evaluation. Future work introducing selection
must implement and test a training-only selection function and reserve new dates.

The checked-in artificial fixture declares these inclusive periods:

| Period | Start | End | Purpose |
| --- | --- | --- | --- |
| Training | 2020-11-18 | 2021-05-18 | Rule diagnostics, no fitting |
| Selection | 2021-05-19 | 2021-11-02 | All candidates retained |
| Evaluation | 2021-11-03 | 2022-07-12 | Held-out calculation demonstration |

There are 230 preceding synthetic observations before training. Indicators may use
past observations across boundaries, but no period carries portfolio capital or
positions from another period. Dates are validated as ordered and disjoint, with
exact endpoints present. The JSON is authoritative; do not infer date ranges from
“last N days”. Rolling or expanding walk-forward research requires multiple
predeclared configs with distinct evaluation blocks. This PR supplies a single
holdout protocol, not a completed walk-forward profitability study.

## Accounting and costs

Each period starts with capital 1 at the close preceding its first return. A signal
formed at that close determines the first return's exposure. Initial entry is
charged even if the signal was active during training. Fees and adverse slippage
are each estimated at 10 bps per unit of absolute exposure change (20 bps combined),
including entry, exit and reentry. Ending holdings are marked to market with no
forced liquidation. Cash earns zero interest. No leverage or short selling occurs.
These are the existing comparison assumptions. They are illustrative estimates,
not venue-calibrated fill measurements: 20 bps may be conservative for liquid stocks
and seriously inadequate for thin memecoins. A separate frozen cost sensitivity
protocol and spread/volume data are required before drawing economic conclusions.

Daily net return equals exposure times close-to-close return minus fee and slippage
return deductions. This additive model preserves the existing rules/accounting;
it is not a self-financing share/cash execution ledger. The report independently
recomputes compounded wealth in a scalar loop and records fee/slippage in units
of initial capital, scaling each day's deduction by prior equity. Costs cannot
be inferred by subtracting gross and net compounded returns alone.

**Execution limitation:** observing close t and assuming a fill at the same close
is optimistic, even though exposures are lagged relative to earned returns.
Lag tests detect future data use; they cannot validate executable fills. A future
fill study needs open/bid/ask prices and a separately reviewed execution model.
No next-open assumptions or strategy-rule changes are silently introduced here.

## Dataset contract and unavailable states

CSV columns are `date` followed by the frozen ordered asset universe. Prices must
be finite, positive, daily, unique and increasing. Every expected session must be
present, every asset must cover it, and the dataset hash must match. There is no
filling, dropping invalid rows, or missing-data sale. Omitted sessions are rejected
against the supplied session list. Correctness of that list requires Task 2's
accepted holiday, early-close, UTC completed-day and corporate-action contract.
The included fixture uses artificial weekdays for both stocks and crypto; it is
not a market calendar. The current rectangular adapter therefore cannot directly
represent stock holidays alongside seven-day crypto calendars without an accepted
common-session policy. A per-market session adapter is future integration work.
Source staleness, unfinished bars and adjustment validity require accepted external
provenance; presence of a metadata string does not validate them.

`results` reports net/gross return, drawdown from initial capital, turnover, invested
sessions, losing sessions and estimated costs separately by asset/signal/period.
`daily` exposes each gain, loss and cost for audit. Compare **evaluation rows**
within the same asset and period to cash/buy-and-hold; never pool train returns
into held-out performance. These are stand-alone per-asset accounts, not portfolio
weights or causal signal attribution. Losing rows on synthetic prices illustrate
accounting only. Historical asset/signal loss attribution is unavailable until
snapshot acceptance. Portfolio cap impact is explicitly `unavailable`: no accepted
weights, risk-control replay or cap contract exists in this scope. Low trade counts
and short periods require an insufficient-data assessment before inference; no
confidence intervals or statistical significance claims are supplied.

## Reproduce offline

From repository root with its research dependencies installed:

```sh
python -m research.validation.evaluate research/validation/fixture/protocol.json --output work/oos-report.json
python -m unittest discover -s tests -v
python -m compileall -q paper_trader.py crypto_paper_trader.py strategy_comparison.py
```

Use a disposable output path and check process success before consuming a report;
a failure writes nothing and does not delete an older output. The report records
Python, pandas, NumPy and yfinance versions. Equal bytes are expected for identical
inputs, code and dependency versions, not across arbitrary package upgrades.
`make_fixture.py` regenerates artificial inputs for tests; do not regenerate a
historical frozen protocol. `synthetic_summary.json` archives all period metrics
and a hash of the full daily report without checking in the large daily ledger.

Tests compare all eight assets with the unchanged reference implementation, check
entry/exit/reentry costs with hand-calculated values, reject corrupt hashes/periods/
missing prices/session mismatches, verify repeated report bytes and input immutability,
and prohibit downloads. Future perturbations and truncated prefixes must preserve
past exposures; a deliberate unlagged future-signal mutation must fail. Full-price
validation is allowed to reject corrupt future rows; it must not trade on them.

Local evidence: 74 unittests passed, handbook compile check passed, roadmap evidence
check passed. This is software correctness evidence; hosted CI and independent human
review remain separate. No issues were closed, no roadmap checkboxes were changed,
and nothing was merged.
