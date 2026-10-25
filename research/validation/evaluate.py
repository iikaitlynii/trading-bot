"""Offline frozen-period research. Never downloads prices or changes paper accounts."""
import argparse
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd
import strategy_comparison as rules

ROOT = Path(__file__).resolve().parents[2]
RULE_SHA256 = hashlib.sha256((ROOT / 'strategy_comparison.py').read_bytes()).hexdigest()
UNIVERSE = rules.STOCKS + rules.MEMECOINS
HISTORICAL_STATUS = 'unavailable: historical evaluation unsupported; verified daily data-contract adapter required'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def exposures(asset, close):
    """Exact signal formulas from the pinned comparison; parity is regression tested."""
    close = rules.validate_close(close)
    fast, slow = close.rolling(20).mean(), close.rolling(50).mean()
    regime = close.rolling(100 if asset in rules.MEMECOINS else 200).mean()
    return pd.DataFrame({
        'cash': pd.Series(0., index=close.index),
        'buy_hold': pd.Series(1., index=close.index),
        'trend': ((close > regime) & (fast > slow)).astype(float).shift(1).fillna(0),
        'momentum': (close.pct_change(20, fill_method=None) > 0).astype(float).shift(1).fillna(0),
    })


def ledger(close, held, fee_bps, slippage_bps):
    """Initialize at preceding close, charge entry, mark end without liquidation."""
    returns = close.pct_change(fill_method=None).loc[held.index]
    turnover = held.diff().abs().fillna(held.iloc[0])
    fee = turnover * fee_bps / 10000
    slippage = turnover * slippage_bps / 10000
    gross = returns * held
    net = gross - fee - slippage
    equity = (1 + net).cumprod()
    frame = pd.DataFrame(dict(exposure=held, turnover=turnover, gross_return=gross,
                              fee_return=fee, slippage_return=slippage,
                              net_return=net, equity=equity))
    # Independent scalar accounting, including equity-scaled dollar costs.
    wealth, fees, slips = 1., 0., 0.
    previous = 0.
    for date, weight in held.items():
        traded = abs(float(weight) - previous)
        fees += wealth * traded * fee_bps / 10000
        slips += wealth * traded * slippage_bps / 10000
        i = close.index.get_loc(date)
        wealth *= 1 + float(weight) * (float(close.iloc[i]) / float(close.iloc[i-1]) - 1) - traded * (fee_bps + slippage_bps) / 10000
        previous = float(weight)
    if not np.isclose(wealth, equity.iloc[-1], rtol=1e-12, atol=1e-12):
        raise AssertionError('independent cost reconciliation failed')
    summary = dict(net_return_pct=float((wealth-1)*100),
                   gross_return_pct=float(((1+gross).prod()-1)*100),
                   max_drawdown_pct=float((equity/equity.cummax().clip(lower=1)-1).min()*100),
                   turnover=float(turnover.sum()), invested_sessions=int(held.sum()),
                   fee_per_initial_dollar=fees, slippage_per_initial_dollar=slips,
                   losing_sessions=int((net < 0).sum()))
    return summary, frame


def load_inputs(config_path):
    config_path = Path(config_path)
    raw = config_path.read_bytes()
    cfg = json.loads(raw)
    # PR #15 validates integrity/session eligibility, not provider authenticity.
    # This rectangular CSV runner has no reviewed adapter for those snapshots.
    # Fail before dataset IO or computation regardless of self-asserted metadata.
    if cfg.get('evidence') == 'historical':
        raise ValueError(HISTORICAL_STATUS)
    if cfg.get('evidence') != 'synthetic':
        raise ValueError('unknown evidence type; only synthetic evaluation is supported')
    if 'snapshot_acceptance' in cfg:
        raise ValueError('snapshot_acceptance is unsupported; metadata cannot verify provenance')
    if cfg['universe'] != UNIVERSE:
        raise ValueError('universe must match the frozen existing comparison universe')
    if cfg['rule_sha256'] != RULE_SHA256:
        raise ValueError('rule version mismatch')
    if cfg['evaluator_sha256'] != digest(Path(__file__).read_bytes()):
        raise ValueError('evaluator version mismatch')
    for cost in ('fee_bps', 'slippage_bps'):
        if not isinstance(cfg[cost], (int, float)) or isinstance(cfg[cost], bool) or not np.isfinite(cfg[cost]) or not 0 <= cfg[cost] < 5000:
            raise ValueError('invalid cost assumption')
    for field in ('source', 'retrieved_at', 'session_convention', 'adjustment_basis'):
        if not cfg.get(field):
            raise ValueError('missing provenance: ' + field)
    dates = []
    for period in ('train', 'selection', 'evaluation'):
        start, end = map(pd.Timestamp, cfg['periods'][period])
        if start > end:
            raise ValueError('reversed period')
        dates.extend([start, end])
    if any(a >= b for a, b in zip(dates[1::2][:-1], dates[2::2])):
        raise ValueError('periods overlap or are not chronological')
    data = (config_path.parent / cfg['dataset']).read_bytes()
    if digest(data) != cfg['dataset_sha256']:
        raise ValueError('dataset hash mismatch')
    import io
    df = pd.read_csv(io.BytesIO(data), index_col='date', parse_dates=['date'])
    if list(df.columns) != UNIVERSE:
        raise ValueError('missing, extra or reordered assets')
    if df.index.strftime('%Y-%m-%d').tolist() != cfg['expected_sessions']:
        raise ValueError('session contract mismatch (no filling or dropping allowed)')
    for asset in UNIVERSE:
        rules.validate_close(df[asset])
    for date in dates:
        if date not in df.index:
            raise ValueError('period endpoint missing')
    if df.index.get_loc(dates[0]) < 229:
        raise ValueError('need 230 observations through first training session')
    if dates[-1] != df.index[-1]:
        raise ValueError('snapshot must end at evaluation endpoint')
    return cfg, df, digest(raw)


def evaluate(config_path):
    cfg, data, config_hash = load_inputs(config_path)
    rows, daily = [], []
    for asset in UNIVERSE:
        close = data[asset]
        signal = exposures(asset, close)
        for period, (start, end) in cfg['periods'].items():
            for name in signal:
                summary, frame = ledger(close, signal.loc[start:end, name], cfg['fee_bps'], cfg['slippage_bps'])
                rows.append(dict(asset=asset, signal=name, period=period, **summary))
                for date, row in frame.iterrows():
                    daily.append(dict(asset=asset, signal=name, period=period,
                                      date=str(date.date()), **row.to_dict()))
        # Every prefix retains its exposures after adversarial future changes.
        for cut in (cfg['periods']['train'][1], cfg['periods']['selection'][1], cfg['periods']['evaluation'][0]):
            changed = close.copy()
            changed.loc[changed.index > cut] *= 17
            pd.testing.assert_frame_equal(signal.loc[:cut], exposures(asset, changed).loc[:cut])
            pd.testing.assert_frame_equal(signal.loc[:cut], exposures(asset, close.loc[:cut]))
    return dict(schema_version=1, evidence='synthetic',
                historical_status=HISTORICAL_STATUS,
                config_sha256=config_hash, dataset_sha256=cfg['dataset_sha256'],
                rule_sha256=RULE_SHA256, evaluator_sha256=digest(Path(__file__).read_bytes()),
                periods=cfg['periods'], universe=UNIVERSE,
                assumptions=dict(fee_bps=cfg['fee_bps'], slippage_bps=cfg['slippage_bps'],
                                 execution='prior-close signal and same-close assumed fill; optimistic',
                                 selection='none: fixed rules, all candidates reported; no tuning', cash_interest=0,
                                 terminal_liquidation=False),
                environment=dict(python=platform.python_version(), **{p: importlib.metadata.version(p) for p in ('pandas','numpy','yfinance')}),
                checks=dict(future_perturbation='passed', prefix_invariance='passed', independent_cost_accounting='passed'),
                cap_impact=dict(status='unavailable', reason='no accepted portfolio weights, cap contract or risk-control replay; per-asset rules only'),
                attribution_status='synthetic illustration only',
                results=rows, daily=daily)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = evaluate(args.config)  # Validate fully before writing any output.
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(encoded(result))


if __name__ == '__main__':
    main()
