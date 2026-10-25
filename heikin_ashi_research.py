"""Offline experimental minute research. No order submission or brokerage imports."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent / 'research/heikin_ashi'
FEE = 10 / 10000
SLIP = 2 / 10000
HALF_SPREAD = 1 / 10000


def validate(frame, start, end):
    """Require exactly the declared completed UTC minutes; never repair inputs."""
    expected = pd.date_range(start, end, freq='min', inclusive='left', tz='UTC')
    if not frame.index.equals(expected) or len(frame) < 201:
        raise ValueError('missing, stale, duplicate, unordered or unaligned minutes')
    columns = frame[['open', 'high', 'low', 'close', 'volume']]
    if any(not pd.api.types.is_numeric_dtype(t) or pd.api.types.is_bool_dtype(t)
           or pd.api.types.is_complex_dtype(t) for t in columns.dtypes):
        raise ValueError('OHLCV must be real numeric values')
    values = columns.to_numpy(float)
    if not np.isfinite(values).all() or (values[:, :4] <= 0).any() or (values[:, 4] < 0).any():
        raise ValueError('invalid OHLCV')
    if ((frame.high < frame[['open', 'close', 'low']].max(axis=1)) |
            (frame.low > frame[['open', 'close', 'high']].min(axis=1))).any():
        raise ValueError('invalid OHLC geometry')
    return frame


def indicators(frame):
    """First HA open is actual (O+C)/2; all recursion uses only past data."""
    close = frame[['open', 'high', 'low', 'close']].mean(axis=1).to_numpy()
    opening = np.empty(len(frame))
    opening[0] = (frame.open.iloc[0] + frame.close.iloc[0]) / 2
    for i in range(1, len(frame)):
        opening[i] = (opening[i-1] + close[i-1]) / 2
    ha = pd.DataFrame({'open': opening, 'close': close}, index=frame.index)
    ha['high'] = np.maximum(frame.high, np.maximum(opening, close))
    ha['low'] = np.minimum(frame.low, np.minimum(opening, close))
    ha['ema'] = frame.close.ewm(span=100, adjust=False, min_periods=100).mean()
    return ha


def signals(frame):
    h = indicators(frame)
    body = h.close - h.open
    span = h.high - h.low
    doji = (span > 0) & (body.abs() <= .1 * span)
    clean = (span > 0) & (body.abs() >= .5 * span)
    # Doji HA range must be no larger than EACH of the prior three ranges.
    contraction = span <= span.shift(1).rolling(3).min()
    out = pd.Series(0, index=frame.index)
    for side in (1, -1):
        pull = clean & (body * side < 0)
        trend = (frame.close - h.ema) * side > 0
        ok = trend & trend.shift(1, fill_value=False) & trend.shift(2, fill_value=False)
        ok &= pull.shift(1, fill_value=False) & pull.shift(2, fill_value=False)
        out.loc[ok & doji & contraction] = side
    out.iloc[:200] = 0
    return out


def simulate(frame, intent, brackets=False):
    """One fixed-size unit; next-open fills, actual OHLC stops, adverse costs."""
    if frame.empty:
        raise ValueError('empty minute history')
    validate(frame, frame.index[0], frame.index[-1] + pd.Timedelta(minutes=1))
    if not intent.index.equals(frame.index) or not intent.isin([-1, 0, 1]).all():
        raise ValueError('invalid or unaligned simulation intent')
    equity = 100000.0
    peak = equity
    drawdown = 0.0
    costs = 0.0
    trades = []
    position = None
    marks = []

    def fill(price, side):
        return price * (1 + side * (SLIP + HALF_SPREAD))

    def finish(raw, stamp, reason):
        nonlocal equity, costs, position
        side, entry, stop, target, entered, entry_raw = position
        exit_price = fill(raw, -side)
        fee = FEE * (entry + exit_price)
        net = side * (exit_price - entry) - fee
        cost = fee + abs(entry-entry_raw) + abs(exit_price-raw)
        costs += cost
        equity += net
        trades.append(dict(entry_time=str(entered), exit_time=str(stamp), side=side,
                           entry=entry, exit=exit_price, stop=stop, target=target,
                           net=net, costs=cost, reason=reason))
        position = None

    for i in range(200, len(frame)):
        row = frame.iloc[i]
        stamp = frame.index[i]
        desired = int(intent.iloc[i-1])
        if position and not brackets and desired != position[0]:
            finish(row.open, stamp, 'signal')
        if position is None and desired and i < len(frame)-1:
            entry = fill(row.open, desired)
            previous = frame.iloc[i-1]
            stop = previous.low - .01 if desired == 1 else previous.high + .01
            risk = desired * (entry - stop)
            # Set target to at least net 1:1 after modeled exit costs and fees.
            stop_fill = fill(stop, -desired)
            loss = desired * (entry-stop_fill) + FEE*(entry+stop_fill)
            target_fill = (loss + desired*entry + FEE*entry) / (desired-FEE)
            target = target_fill / (1-desired*(SLIP+HALF_SPREAD))
            if not brackets or risk > 0:
                position = (desired, entry, stop, target, stamp, row.open)
        if position and brackets:
            side, entry, stop, target, _, _ = position
            if side * (row.open-stop) <= 0:
                finish(row.open, stamp, 'gap_stop')
            elif (side == 1 and row.low <= stop) or (side == -1 and row.high >= stop):
                finish(stop, stamp, 'stop')
            elif (side == 1 and row.high >= target) or (side == -1 and row.low <= target):
                finish(target, stamp, 'target')
        if i == len(frame)-1 and position:
            finish(row.close, stamp, 'window_end')
        marked = equity
        if position:
            side, entry, *_ = position
            exit_price = fill(row.close, -side)
            marked += side*(exit_price-entry)-FEE*(entry+exit_price)
        peak = max(peak, marked)
        drawdown = min(drawdown, marked/peak-1)
        marks.append(marked)
    wins = sum(t['net'] > 0 for t in trades)
    gain = sum(max(t['net'], 0) for t in trades)
    loss = -sum(min(t['net'], 0) for t in trades)
    return dict(trade_count=len(trades), win_rate=wins/len(trades) if trades else None,
                profit_factor=gain/loss if loss else None, net_pnl=equity-100000,
                return_pct=(equity/100000-1)*100, max_drawdown_pct=-drawdown*100,
                costs=costs, trades=trades)


def validate_periods(manifest):
    """Validate the entire temporal split before any historical simulation.

    Roles occur exactly once in development/validation/out-of-sample order.
    Windows are half-open, so adjacent endpoints are allowed; gaps are allowed.
    """
    periods = manifest.get('periods')
    roles = ('development', 'validation', 'out_of_sample')
    if (not isinstance(periods, list) or len(periods) != len(roles)
            or any(not isinstance(p, dict) for p in periods)
            or tuple(p.get('name') for p in periods) != roles):
        raise ValueError('require unique development, validation, out_of_sample roles in order')

    def timestamp(value):
        if not isinstance(value, str):
            raise ValueError('period clocks must be timezone-aware timestamp strings')
        try:
            stamp = pd.Timestamp(value)
        except (ValueError, TypeError) as exc:
            raise ValueError('invalid period clock') from exc
        if pd.isna(stamp) or stamp.tzinfo is None:
            raise ValueError('period clocks must be valid and timezone-aware')
        return stamp.tz_convert('UTC')

    completed_through = timestamp(manifest.get('retrieved_at')).floor('min')
    previous_end = None
    for period in periods:
        start, end = timestamp(period.get('start')), timestamp(period.get('end'))
        if start != start.floor('min') or end != end.floor('min') or start >= end:
            raise ValueError('periods require increasing minute-aligned boundaries')
        if previous_end is not None and start < previous_end:
            raise ValueError('periods overlap, duplicate a window or are chronologically reordered')
        if end > completed_through:
            raise ValueError('unfinished historical window')
        previous_end = end


def run(*, root=ROOT, output_path=None):
    root = Path(root)
    manifest = json.loads((root/'manifest.json').read_text())
    validate_periods(manifest)
    raw = (root/'source.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest['sha256']:
        raise ValueError('source hash mismatch')
    source = json.loads(raw)['chart']['result'][0]
    if source['meta']['symbol'] != 'BTC-USD' or source['meta']['dataGranularity'] != '1m':
        raise ValueError('wrong source identity')
    frame = pd.DataFrame(source['indicators']['quote'][0],
                         index=pd.to_datetime(source['timestamp'], unit='s', utc=True))
    results = []
    for period in manifest['periods']:
        start = pd.Timestamp(period['start']).tz_convert('UTC')
        end = pd.Timestamp(period['end']).tz_convert('UTC')
        subset = frame.loc[(frame.index >= start) & (frame.index < end)]
        try:
            validate(subset, start, end)
        except ValueError as exc:
            results.append(dict(period=period, rejected=str(exc)))
            continue
        close = subset.close
        # Existing strategy_comparison.py formulas adapted explicitly to minute bars.
        trend = ((close > close.rolling(200).mean()) &
                 (close.rolling(20).mean() > close.rolling(50).mean())).astype(int)
        momentum = (close.pct_change(20) > 0).astype(int)
        for name, signal in [('ha_pullback', signals(subset)),
                             ('buy_hold', pd.Series(1, index=subset.index)),
                             ('cash', pd.Series(0, index=subset.index)),
                             ('minute_trend_adaptation', trend),
                             ('minute_momentum_adaptation', momentum)]:
            results.append(dict(period=period, strategy=name,
                                **simulate(subset, signal, name == 'ha_pullback')))
    output = root/'results.json' if output_path is None else Path(output_path)
    output.write_text(json.dumps(results, indent=2, allow_nan=False)+'\n')
    for row in results:
        print({k:v for k,v in row.items() if k != 'trades'})


if __name__ == '__main__':
    run()
