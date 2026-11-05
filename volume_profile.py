"""Offline candle-approximation research; no signals, orders, or network access."""
import argparse
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from data_contracts.sessions import sessions

ROOT = Path(__file__).resolve().parent
LIMITATIONS = [
    'APPROXIMATE candle volume-at-price, never exact trade-level volume.',
    'Daily volume is spread uniformly across each low–high range; intraday distribution is unknown.',
    'Legacy Yahoo quote snapshot: retrieval time, raw-response archive and corporate-action audit unavailable.',
    'Legacy snapshot may contain substituted missing volume; zero-volume rows are rejected here. Current ingestion rejects missing volume.',
    'Historical window only; no claim of current freshness, predictive power or validated strategy.',
    'Bin count and window change all levels; HVN/LVN are descriptive heuristics, not trade signals.'
]


def profile(frame, *, start, end, bins=24, value_area=.70):
    """Inclusive XNYS session window; reject rather than repair ambiguous inputs."""
    if type(bins) is not int or not 2 <= bins <= 100:
        raise ValueError('bins must be an integer from 2 to 100')
    if isinstance(value_area, bool) or not isinstance(value_area, (int, float)) or not 0 < value_area <= 1:
        raise ValueError('value area must be in (0,1]')
    expected = [d.isoformat() for d in sessions(date.fromisoformat(start), date.fromisoformat(end), 'stock')]
    if not expected or frame.empty or frame.date.tolist() != expected:
        raise ValueError('missing, duplicate, unordered or unexpected sessions in declared window')
    cols = frame[['low', 'high', 'close', 'volume']]
    if any(not pd.api.types.is_numeric_dtype(t) or pd.api.types.is_bool_dtype(t) or
           pd.api.types.is_complex_dtype(t) for t in cols.dtypes):
        raise ValueError('HLCV must be real numeric values')
    values = cols.to_numpy(float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError('prices and volume must be finite and positive; zero volume is ambiguous')
    if ((frame.low > frame.close) | (frame.close > frame.high)).any():
        raise ValueError('invalid candle geometry')
    low, high = float(frame.low.min()), float(frame.high.max())
    if low == high:
        raise ValueError('constant overall range: price bins cannot be resolved')
    edges = np.linspace(low, high, bins + 1)
    if not np.all(np.diff(edges) > 0):
        raise ValueError('price range too narrow for requested bins')
    volumes = np.zeros(bins)
    for row in frame.itertuples():
        if row.low == row.high:
            volumes[min(bins - 1, np.searchsorted(edges, row.low, side='right') - 1)] += row.volume
        else:
            overlap = np.maximum(0, np.minimum(edges[1:], row.high) - np.maximum(edges[:-1], row.low))
            volumes += row.volume * overlap / (row.high - row.low)
    total = float(volumes.sum())
    if not np.isfinite(total) or total <= 0:
        raise ValueError('invalid aggregate volume')
    poc = int(np.argmax(volumes))  # lowest-price bin wins ties
    left = right = poc
    covered = volumes[poc]
    while covered < total * value_area and (left > 0 or right < bins - 1):
        lv = volumes[left - 1] if left else -1
        rv = volumes[right + 1] if right < bins - 1 else -1
        if lv >= rv:
            left -= 1; covered += volumes[left]
        else:
            right += 1; covered += volumes[right]
    # Strict interior local extrema exclude endpoints and flat plateaus.
    hvn = [i for i in range(1, bins-1) if volumes[i] > max(volumes[i-1], volumes[i+1])]
    lvn = [i for i in range(1, bins-1) if volumes[i] < min(volumes[i-1], volumes[i+1])]
    center = lambda i: float((edges[i] + edges[i+1]) / 2)
    return dict(method='uniform_low_high_candle_approximation_v1', evidence='HISTORICAL · APPROXIMATE · UNVALIDATED',
                start=start, end=end, sessions=len(frame), bin_count=bins, value_area_target=value_area,
                value_area_achieved=float(covered/total), total_volume=total,
                poc=center(poc), vah=float(edges[right+1]), val=float(edges[left]),
                hvn=[center(i) for i in hvn], lvn=[center(i) for i in lvn],
                bins=[dict(low=float(edges[i]), high=float(edges[i+1]), volume=float(v),
                           poc=i == poc, value_area=left <= i <= right, hvn=i in hvn, lvn=i in lvn)
                      for i, v in enumerate(volumes)], limitations=LIMITATIONS)


def build(source, output):
    """Generate independent saved-window results; failures remain explicit."""
    raw = source.read_bytes()
    frame = pd.read_csv(source)
    results = []
    for symbol in ('AAPL', 'MSFT', 'NVDA', 'AMZN'):
        data = frame.loc[frame.ticker == symbol]
        for count in (20, 60, 120):
            for bins in (12, 24, 48):
                item = dict(symbol=symbol, window=count, bin_count=bins)
                try:
                    if data.empty:
                        raise ValueError('symbol history unavailable')
                    end = str(data.date.iloc[-1])
                    # Window endpoints derived from the reviewed calendar, not row count.
                    days = sessions(date.fromisoformat(end)-timedelta(days=240), date.fromisoformat(end), 'stock')
                    start = days[-count].isoformat()
                    selected = data.loc[(data.date >= start) & (data.date <= end)]
                    item.update(profile(selected, start=start, end=end, bins=bins), status='AVAILABLE')
                except (ValueError, KeyError, IndexError) as exc:
                    item.update(status='FAILED', error=str(exc))
                results.append(item)
    report = dict(schema_version=1, source=str(source.relative_to(ROOT)), source_sha256=hashlib.sha256(raw).hexdigest(),
                  source_basis='Yahoo daily quote HLCV; legacy provenance incomplete', profiles=results)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT/'research/stock_history.csv')
    parser.add_argument('--output', type=Path, default=ROOT/'docs/volume-profile/report.json')
    args = parser.parse_args()
    report = build(args.source, args.output)
    failures = sum(p['status'] == 'FAILED' for p in report['profiles'])
    print(f'{len(report["profiles"])} profiles; {failures} FAILED')
    raise SystemExit(bool(failures))
