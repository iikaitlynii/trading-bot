"""Isolated adapter to existing research_lab.run_variant, never its downloader."""
import argparse
import hashlib
import importlib.metadata
import platform
from pathlib import Path

import numpy as np
import pandas as pd
import research_lab as engine
import strategy_comparison as comparison
from .lab import configuration, digest, encoded, extract, load

# Frozen before running a candidate; positions reset at each boundary.
PERIODS = {'train': (250, 370), 'selection': (370, 490), 'evaluation': (490, 610)}


def synthetic_prices():
    i = np.arange(610)
    # Intentional bull/bear/sideways cycles, no random or downloaded observations.
    return pd.DataFrame({'SYNTH': 100 * np.exp(.00025*i + .13*np.sin(i/31) + .025*np.sin(i/5))},
                        index=pd.date_range('2020-01-01', periods=len(i), freq='D'))


def validate_prices(prices):
    if list(prices.columns) != ['SYNTH'] or len(prices) != 610:
        raise ValueError('prototype accepts only the fixed 610-row synthetic contract')
    comparison.validate_close(prices['SYNTH'])
    if not prices.index.equals(pd.date_range('2020-01-01', periods=610, freq='D')):
        raise ValueError('missing or unexpected synthetic sessions')
    if not prices.equals(synthetic_prices()):
        raise ValueError('only the versioned synthetic fixture is accepted; historical integration pending')


def _run(prices, cfg, start, end):
    warmup = max(cfg['slow'], cfg['regime'])
    if start < warmup:
        raise ValueError('insufficient pre-period warmup')
    return engine.run_variant(prices.iloc[start-warmup:end].copy(), cfg)


def baselines(prices, start, end):
    # Buy at first evaluation close, mark last; same fee/slippage convention.
    factor = (1-engine.COMMISSION)/(1+engine.SLIPPAGE)
    equity = [engine.STARTING] + list(engine.STARTING * factor * prices['SYNTH'].iloc[start:end] / prices['SYNTH'].iloc[start])
    hold = dict(return_pct=round((equity[-1]/engine.STARTING-1)*100, 4),
                max_drawdown_pct=round(engine.max_drawdown(equity), 4))
    # Existing single-asset comparison rules, for the identical 120-session window.
    existing = comparison.calculate('SYNTH', prices['SYNTH'].iloc[:end])
    return dict(cash={'return_pct': 0., 'max_drawdown_pct': 0.}, buy_hold=hold,
                existing_trend={k: v for k, v in existing.items() if k.startswith('trend_')},
                existing_momentum={k: v for k, v in existing.items() if k.startswith('momentum_')},
                existing_current_20_50=_run(prices, engine.VARIANTS[0], start, end))


def evaluate(spec, prices):
    cfg = configuration(spec)
    validate_prices(prices)
    if spec['candidate']['source'].get('synthetic') is not True:
        raise ValueError('prototype evaluation requires synthetic transcript fixtures')
    periods = {}
    for name, (start, end) in PERIODS.items():
        periods[name] = dict(start=str(prices.index[start].date()), end=str(prices.index[end-1].date()),
                             candidate=_run(prices, cfg, start, end), baselines=baselines(prices, start, end))
    # Predeclared one-at-a-time sensitivity checks, never optimize or select by returns.
    sensitivities = []
    start, end = PERIODS['evaluation']
    for scale in (.9, 1.1):
        changed = dict(cfg, fast=max(2, min(cfg['slow']-1, round(cfg['fast']*scale))))
        sensitivities.append(dict(fast=changed['fast'], result=_run(prices, changed, start, end)))
    dd = [periods['evaluation']['candidate']['max_drawdown_pct']] + [r['result']['max_drawdown_pct'] for r in sensitivities]
    # This is stability under an illustrative perturbation, never probability of profit.
    robustness = dict(drawdown_spread_pct=round(max(dd)-min(dd), 4), sensitivity_trials=len(sensitivities),
                      independent_datasets=0, historical_evidence=False, grade='synthetic-only / unvalidated')
    return dict(evidence='illustrative synthetic simulation', spec_sha256=digest(spec), candidate_sha256=digest(spec['candidate']),
                dataset_sha256=hashlib.sha256(prices.to_csv().encode()).hexdigest(),
                evaluator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                engine_sha256=hashlib.sha256(Path(engine.__file__).read_bytes()).hexdigest(),
                comparison_sha256=hashlib.sha256(Path(comparison.__file__).read_bytes()).hexdigest(),
                versions={k: importlib.metadata.version(k) for k in ('pandas', 'numpy', 'yfinance')},
                python=platform.python_version(), periods=periods, sensitivity=sensitivities, robustness=robustness,
                limitations=['Same-close fills are optimistic; not next-open executable results.',
                             'Existing comparison trend/momentum use prior-close fills and full exposure; candidate is capped at 20% or less.',
                             '10 bps fee and 10 bps slippage estimates; no final liquidation.',
                             'Periods reset holdings; no fitting, selection or walk-forward claim.',
                             'Holdout is public synthetic data; no independent market evidence.'])


def research_rank(candidate, result=None):
    """Evidence completeness precedes review, reproducibility and stability; no P/L."""
    completeness = sum(len(v) == 1 for v in candidate['evidence'].values()) / 6
    verified = result is not None and result.get('candidate_sha256') == digest(candidate) and not candidate['uncertainties']
    stability = 1 / (1 + result['robustness']['drawdown_spread_pct']) if verified else 0
    return dict(completeness=round(completeness, 3), unresolved=len(candidate['uncertainties']),
                reproducible_synthetic_evaluation=verified, stability=round(stability, 4),
                score=round(50*completeness + 25*verified + 25*stability, 2),
                grade='synthetic-only / unvalidated' if verified else 'human review required')


def submission(spec, result):
    configuration(spec)
    if result['spec_sha256'] != digest(spec):
        raise ValueError('result/spec hash mismatch')
    return dict(status='blocked_pending_human_integration', target='PR #13 frozen evaluation framework',
                spec_sha256=digest(spec), dataset_sha256=result['dataset_sha256'], simulation_only=True,
                prerequisites=['PR #13 reviewed and integrated with an allowlisted candidate adapter',
                               'PR #15 accepted historical snapshot/session contract',
                               'Human review of specification, fills, risk semantics and independent holdout'],
                note='Queue manifest only. PR #13 currently supports existing fixed rules, not discovered candidates.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).parent
    spec = load(root/'specifications/demo.json')
    result = evaluate(spec, synthetic_prices())
    candidates = [extract(s) for s in load(root/'samples/transcripts.json')]
    report = dict(simulation_only=True, result=result, submission=submission(spec, result),
                  candidates=[dict(candidate=c, quality=research_rank(c, result if c == spec['candidate'] else None)) for c in candidates])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded(report))
    print('Saved synthetic research report:', args.output)


if __name__ == '__main__':
    main()
