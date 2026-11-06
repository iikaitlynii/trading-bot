"""Deterministic decimal accounting for newly started simulation accounts only."""
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal, ROUND_DOWN
import hashlib
import json
from pathlib import Path

from data_contracts.sessions import aware, session_close, latest_completed

MODEL = 'paper-execution-v2'
ASSUMPTION = 'Illustrative assumptions, not verified market costs: later observed daily close, adverse slippage and fees.'


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def dec(value):
    if isinstance(value, bool):
        raise ValueError('invalid number')
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError('nonfinite number')
    return result


def stamp(value):
    return aware(datetime.fromisoformat(value.replace('Z', '+00:00')))


def positive(value):
    result = dec(value)
    if result <= 0:
        raise ValueError('positive number required')
    return result


def assumptions(fee_bps='10', slippage_bps='10', fixed_fee='0'):
    result = dict(fee_bps=str(dec(fee_bps)), slippage_bps=str(dec(slippage_bps)), fixed_fee=str(dec(fixed_fee)), label=ASSUMPTION)
    if not 0 <= dec(fee_bps) < 10000 or not 0 <= dec(slippage_bps) < 10000 or dec(fixed_fee) < 0:
        raise ValueError('invalid execution assumptions')
    return result


def new_account(market, symbols, cash, created_at, costs=None):
    if market not in ('stock', 'crypto') or not symbols or len(set(symbols)) != len(symbols):
        raise ValueError('invalid account universe')
    stamp(created_at)
    costs = costs or assumptions()
    if costs != assumptions(costs['fee_bps'], costs['slippage_bps'], costs['fixed_fee']):
        raise ValueError('invalid assumptions')
    return dict(model=MODEL, simulation_only=True, market=market, symbols=list(symbols),
                initial_cash=str(positive(cash)), created_at=created_at, assumptions=costs,
                cash=str(positive(cash)), positions={}, realized_pnl='0', fees='0',
                orders=[], fills=[], valuations=[], last_session=None)


def identity(account, session, symbol, side):
    return digest([MODEL, account['market'], account['created_at'], session, symbol, side])


def execute(order, market_price, session, observed_at, input_hash, account):
    """Full budget buys, full-position sells; no borrowing or partial order fills."""
    price = positive(market_price)
    costs = order['assumptions']
    slip = dec(costs['slippage_bps']) / 10000
    rate = dec(costs['fee_bps']) / 10000
    fixed = dec(costs['fixed_fee'])
    side = order['side']
    execution_price = price * (1 + slip if side == 'SIM_BUY' else 1 - slip)
    if side == 'SIM_BUY':
        budget = min(dec(order['budget']), dec(account['cash']))
        if budget <= fixed:
            return None
        units = ((budget - fixed) / (execution_price * (1 + rate))).quantize(Decimal('0.000000000001'), rounding=ROUND_DOWN)
        if units <= 0:
            return None
    else:
        units = positive(order['units'])
        if order['symbol'] not in account['positions'] or units != dec(account['positions'][order['symbol']]['units']):
            raise ValueError('sell holdings mismatch')
    gross = units * execution_price
    fee = gross * rate + fixed
    cash_delta = -(gross + fee) if side == 'SIM_BUY' else gross - fee
    if side == 'SIM_SELL' and cash_delta < 0:
        return None
    return dict(order_id=order['id'], side=side, symbol=order['symbol'], session=session,
                signal_session=order['signal_session'], signal_at=order['signal_at'], created_at=order['created_at'],
                price_at=session_close(date.fromisoformat(session), account['market']).isoformat(),
                observed_at=observed_at, input_sha256=input_hash, market_price=str(price),
                execution_price=str(execution_price), units=str(units), gross=str(gross), fee=str(fee),
                slippage_cost=str(units * abs(execution_price - price)), cash_delta=str(cash_delta),
                assumptions=costs, execution_code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), simulation_only=True)


def apply_fill(account, fill):
    symbol = fill['symbol']
    units, gross, fee = (dec(fill[k]) for k in ('units', 'gross', 'fee'))
    if fill['side'] == 'SIM_BUY':
        if symbol in account['positions']:
            raise ValueError('duplicate position')
        account['positions'][symbol] = dict(units=str(units), cost_basis=str(gross + fee))
    else:
        position = account['positions'].pop(symbol)
        if dec(position['units']) != units:
            raise ValueError('sell quantity mismatch')
        account['realized_pnl'] = str(dec(account['realized_pnl']) + gross - fee - dec(position['cost_basis']))
    account['cash'] = str(dec(account['cash']) + dec(fill['cash_delta']))
    account['fees'] = str(dec(account['fees']) + fee)
    if dec(account['cash']) < 0:
        raise ValueError('cash overspent')


def valuation(account, marks):
    value = sum((dec(p['units']) * positive(marks[s]) for s, p in account['positions'].items()), Decimal(0))
    basis = sum((dec(p['cost_basis']) for p in account['positions'].values()), Decimal(0))
    unrealized = value - basis
    equity = dec(account['cash']) + value
    if abs(equity - dec(account['initial_cash']) - dec(account['realized_pnl']) - unrealized) > Decimal('1e-18'):
        raise ValueError('equity reconciliation failed')
    return dict(cash=account['cash'], position_value=str(value), cost_basis=str(basis),
                realized_pnl=account['realized_pnl'], unrealized_pnl=str(unrealized),
                fees=account['fees'], total_equity=str(equity))


def risk_metrics(account, metrics, prices, weight, cap, threshold, peak):
    equity = positive(metrics['total_equity'])
    peak = max(peak, equity)
    weights = {s:str(dec(p['units']) * positive(prices[s]) / equity) for s,p in account['positions'].items()}
    exposure = dec(metrics['position_value']) / equity
    drawdown = (peak - equity) / peak
    return dict(weights=weights, exposure=str(exposure), peak_equity=str(peak), drawdown=str(drawdown),
                limit_breach=exposure > cap or any(dec(w) > weight for w in weights.values()),
                drawdown_warning=drawdown >= threshold)


def advance(saved, *, session, observed_at, retrieved_at, prices, signals, input_hash,
            weight='0.2', max_invested='0.8', minimum='50', drawdown_warning='0.1'):
    """Use only the latest accepted observation, never search history for a fill."""
    reconcile(saved)
    account = deepcopy(saved)
    now, retrieved = stamp(observed_at), stamp(retrieved_at)
    close_at = session_close(date.fromisoformat(session), account['market'])
    if (close_at is None or close_at > retrieved or retrieved > now or session != latest_completed(now, account['market']).isoformat()
            or now < stamp(account['created_at']) or not isinstance(input_hash, str) or len(input_hash) != 64
            or any(c not in '0123456789abcdef' for c in input_hash)):
        raise ValueError('invalid session, clock or input evidence')
    if set(prices) != set(account['symbols']) or set(signals) != set(prices):
        raise ValueError('complete universe required')
    for s in prices:
        positive(prices[s])
        if signals[s] not in ('BULLISH', 'DEFENSIVE'):
            raise ValueError('missing or invalid signal')
    if account['valuations'] and now < stamp(account['valuations'][-1]['observed_at']):
        raise ValueError('observation clock moved backward')
    if account['last_session'] and session < account['last_session']:
        raise ValueError('session replay')
    if session == account['last_session']:
        return account
    weight, cap, minimum = dec(weight), dec(max_invested), positive(minimum)
    if not 0 <= weight <= 1 or not 0 <= cap <= 1:
        raise ValueError('invalid exposure limits')
    for order in account['orders']:
        if order['status'] != 'PENDING':
            continue
        # A later retrieval of a price that existed at creation is still ineligible.
        if session <= order['signal_session'] or close_at <= stamp(order['created_at']) or retrieved <= stamp(order['created_at']):
            continue
        fill = execute(order, prices[order['symbol']], session, observed_at, input_hash, account)
        if fill is None:
            order['status'] = 'REJECTED_COST_OR_QUANTITY'
        else:
            apply_fill(account, fill)
            account['fills'].append(fill)
            order['status'] = 'FILLED'
    metrics = valuation(account, prices)
    threshold = dec(drawdown_warning)
    if not 0 <= threshold <= 1:
        raise ValueError('invalid drawdown threshold')
    peak = max([dec(account['initial_cash'])] + [dec(v['total_equity']) for v in account['valuations']])
    risk = risk_metrics(account, metrics, prices, weight, cap, threshold, peak)
    pending = {o['symbol'] for o in account['orders'] if o['status'] == 'PENDING'}
    reserved = sum((dec(o['budget']) for o in account['orders'] if o['status'] == 'PENDING' and o['side'] == 'SIM_BUY'), Decimal(0))
    for symbol in account['symbols']:
        if symbol in pending:
            continue
        held = account['positions'].get(symbol)
        side = 'SIM_SELL' if held and signals[symbol] == 'DEFENSIVE' else 'SIM_BUY' if not held and signals[symbol] == 'BULLISH' else None
        if side is None:
            continue
        budget = min(dec(metrics['total_equity']) * weight, dec(account['cash']) - reserved,
                     dec(metrics['total_equity']) * cap - dec(metrics['position_value']) - reserved)
        if side == 'SIM_BUY' and budget < minimum:
            continue
        order = dict(id=identity(account, session, symbol, side), symbol=symbol, side=side, status='PENDING',
                     signal_session=session, source_market=account['market'], signal_at=close_at.isoformat(),
                     created_at=observed_at, input_sha256=input_hash, assumptions=deepcopy(account['assumptions']),
                     budget=str(budget) if side == 'SIM_BUY' else '0', units=held['units'] if held else '0',
                     signal=signals[symbol], simulation_only=True)
        order['execution_code_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        account['orders'].append(order)
        if side == 'SIM_BUY':
            reserved += budget
    account['last_session'] = session
    account['valuations'].append(dict(session=session, observed_at=observed_at, retrieved_at=retrieved_at,
                                      input_sha256=input_hash, execution_code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                      sizing_assumptions=dict(weight=str(weight), max_invested=str(cap), minimum=str(minimum), drawdown_warning=str(threshold)), risk=risk, signals=dict(signals), marks={s:str(positive(p)) for s,p in prices.items()}, **metrics))
    reconcile(account)
    return account


def reconcile(account):
    """Recompute cash, lots, realized P/L and every valuation from the fill ledger."""
    if account['model'] != MODEL or account['simulation_only'] is not True:
        raise ValueError('unsupported account model')
    replay = new_account(account['market'], account['symbols'], account['initial_cash'], account['created_at'], account['assumptions'])
    orders = {o['id']: o for o in account['orders']}
    if len(orders) != len(account['orders']):
        raise ValueError('duplicate orders')
    for o in orders.values():
        close = session_close(date.fromisoformat(o['signal_session']), account['market'])
        if (o['id'] != identity(account, o['signal_session'], o['symbol'], o['side']) or o['symbol'] not in account['symbols']
                or o['side'] not in ('SIM_BUY', 'SIM_SELL') or o['status'] not in ('PENDING', 'FILLED', 'REJECTED_COST_OR_QUANTITY')
                or close is None or stamp(o['signal_at']) != close or stamp(o['created_at']) < close
                or stamp(o['created_at']) < stamp(account['created_at']) or o['assumptions'] != account['assumptions']
                or o['source_market'] != account['market'] or o['simulation_only'] is not True):
            raise ValueError('invalid order provenance')
    filled = set()
    valuation_by_session = {v['session']:v for v in account['valuations']}
    for o in orders.values():
        v = valuation_by_session[o['signal_session']]
        if (o['execution_code_sha256'] != v['execution_code_sha256'] or o['input_sha256'] != v['input_sha256'] or o['created_at'] != v['observed_at']
                or o['signal'] != v['signals'][o['symbol']] or dec(o['budget']) < 0 or dec(o['units']) < 0
                or (o['side'] == 'SIM_BUY' and (o['signal'] != 'BULLISH' or dec(o['budget']) <= 0))
                or (o['side'] == 'SIM_SELL' and (o['signal'] != 'DEFENSIVE' or dec(o['units']) <= 0))):
            raise ValueError('order signal/evidence mismatch')
    sessions = [v['session'] for v in account['valuations']]
    if sessions != sorted(set(sessions)) or account['last_session'] != (sessions[-1] if sessions else None):
        raise ValueError('valuation session replay')
    if [f['session'] for f in account['fills']] != sorted(f['session'] for f in account['fills']):
        raise ValueError('unordered fills')
    previous_clock = stamp(account['created_at'])
    peak = dec(account['initial_cash'])
    for v in account['valuations']:
        close = session_close(date.fromisoformat(v['session']), account['market'])
        observed, retrieved = stamp(v['observed_at']), stamp(v['retrieved_at'])
        if (close is None or not close <= retrieved <= observed or observed < previous_clock
                or latest_completed(observed, account['market']).isoformat() != v['session']
                or set(v['signals']) != set(account['symbols'])
                or any(s not in ('BULLISH', 'DEFENSIVE') for s in v['signals'].values())):
            raise ValueError('valuation clock/session/signal mismatch')
        previous_clock = observed
        if set(v['marks']) != set(account['symbols']):
            raise ValueError('missing valuation marks')
        for f in (f for f in account['fills'] if f['session'] == v['session']):
            o = orders[f['order_id']]
            if (f['order_id'] in filled or o['status'] != 'FILLED' or f['session'] <= o['signal_session']
                    or stamp(f['price_at']) <= stamp(o['created_at']) or stamp(f['observed_at']) < stamp(f['price_at'])
                    or f['observed_at'] != v['observed_at'] or retrieved <= stamp(o['created_at'])):
                raise ValueError('duplicate or noncausal fill')
            expected = execute(o, f['market_price'], f['session'], f['observed_at'], f['input_sha256'], replay)
            if expected != f or f['market_price'] != v['marks'][f['symbol']] or f['input_sha256'] != v['input_sha256']:
                raise ValueError('fill cost/evidence reconciliation failed')
            apply_fill(replay, f)
            filled.add(f['order_id'])
        sizing = v['sizing_assumptions']
        risk = risk_metrics(replay, valuation(replay,v['marks']), v['marks'], dec(sizing['weight']), dec(sizing['max_invested']), dec(sizing['drawdown_warning']), peak)
        if risk != v['risk']:
            raise ValueError('risk reconciliation failed')
        peak = dec(risk['peak_equity'])
        if any(v[k] != value for k,value in valuation(replay, v['marks']).items()):
            raise ValueError('valuation reconciliation failed')
    if filled != {o['id'] for o in orders.values() if o['status'] == 'FILLED'} or len(filled) != len(account['fills']):
        raise ValueError('orphan fill')
    for k in ('cash', 'positions', 'realized_pnl', 'fees'):
        if replay[k] != account[k]:
            raise ValueError('account reconciliation failed: ' + k)
    pending = [o for o in orders.values() if o['status'] == 'PENDING']
    if len({o['symbol'] for o in pending}) != len(pending):
        raise ValueError('duplicate pending symbol')
    if sum((dec(o['budget']) for o in pending if o['side'] == 'SIM_BUY'), Decimal(0)) > dec(account['cash']):
        raise ValueError('pending orders exceed cash')
    return True
