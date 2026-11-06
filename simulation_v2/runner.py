"""Accepted-input adapter; legacy accounts are never imported, reset or written."""
import argparse
import hashlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from data_contracts import load
from data_contracts.ingestion import UNIVERSES
from monitoring.account_health import accepted
from paper_risk import Limits
from .model import advance, assumptions, new_account, stamp
from .store import Store


def legacy_guard(root, market, account_id):
    folder = 'research_lab/forward' if account_id.startswith('forward-') else 'paper' if market == 'stock' else 'crypto_paper'
    if any((root / folder / name).exists() for name in ('state.json', 'performance.csv', 'journal.csv')):
        raise ValueError('BLOCKED: legacy account requires independent data/ledger reconciliation and a separately reviewed migration; no v2 reset or import is authorized')
    inventory = root / 'research/reliability/recovery-v1/investigation.json'
    if inventory.exists():
        raise ValueError('BLOCKED: unresolved historical recovery inventory; v2 activation requires independent review')


def run(market, *, root=Path('.'), account_id=None, now=None, variant=None):
    root = Path(root)
    account_id = account_id or market
    now = now or datetime.now(timezone.utc)
    legacy_guard(root, market, account_id)
    session, input_hash, evidence = accepted(root, market, now)
    # accepted() reproduces snapshots from raw bytes, validates full universe,
    # export, hashes, adjustment and the expected completed market session.
    manifest = json.loads((root / f'research/datasets/ingested/{market}-latest.json').read_bytes())
    attempt = json.loads((root / f'work/ingestion/{market}.json').read_bytes())
    if attempt['status'] not in ('ACCEPTED', 'NO_NEW_DATA') or attempt['as_of'] != manifest['as_of']:
        raise ValueError('latest ingestion attempt missing, blocked or mismatched')
    retrieved = min(stamp(e['retrieved_at']) for e in evidence.values())
    if retrieved > now:
        raise ValueError('future provider retrieval clock')
    histories = {s:load(root / p).bars for s,p in manifest['snapshots'].items()}
    fast, slow, regime = (20, 50, 200 if market == 'stock' else 100)
    if variant:
        fast, slow, regime = (variant[k] for k in ('fast', 'slow', 'regime'))
    from decimal import Decimal
    prices, signals = {}, {}
    for s,bars in histories.items():
        values = [Decimal(str(b.close)) for b in bars]
        if len(values) < regime:
            raise ValueError('insufficient signal history')
        prices[s] = str(values[-1])
        bullish = values[-1] > sum(values[-regime:]) / regime and sum(values[-fast:]) / fast > sum(values[-slow:]) / slow
        signals[s] = 'BULLISH' if bullish else 'DEFENSIVE'
    store = Store(root / 'simulation-v2' / account_id)
    with store.locked():
        if store.prepared():
            raise ValueError('BLOCKED: unpublished v2 transaction; explicit recovery required')
        parent = store.pointer()
        account = store.load()
        code_hash = hashlib.sha256(b''.join((Path(__file__).parent/name).read_bytes() for name in ('model.py','runner.py','store.py'))).hexdigest()
        if account is not None and account.get('code_sha256') != code_hash:
            raise ValueError('execution code differs from frozen v2 model; versioned change required')
        requested_costs = assumptions(os.getenv('SIM_FEE_BPS', '10'), os.getenv('SIM_SLIPPAGE_BPS', '10'), os.getenv('SIM_FIXED_FEE', '0'))
        if account is not None and account['assumptions'] != requested_costs:
            raise ValueError('cost configuration differs from frozen v2 assumptions; versioned change required')
        if account is None:
            account = new_account(market, UNIVERSES[market], '10000' if market == 'stock' else '5000', now.isoformat(),
                                  requested_costs)
            account['code_sha256'] = code_hash
        if variant:
            for s,p in account['positions'].items():
                # Close-triggered stop creates intent; it cannot guarantee the stop price.
                last_buy = next(f for f in reversed(account['fills']) if f['symbol'] == s and f['side'] == 'SIM_BUY')
                if Decimal(prices[s]) <= Decimal(last_buy['execution_price']) * (1 - Decimal(str(variant['stop']))):
                    signals[s] = 'DEFENSIVE'
        limits = Limits.from_env('STOCK_PAPER' if market == 'stock' else 'CRYPTO_PAPER',
                                 variant['weight'] if variant else .2 if market == 'stock' else .1,
                                 .8 if market == 'stock' else .4)
        updated = advance(account, session=session, observed_at=now.isoformat(), retrieved_at=retrieved.isoformat(),
                          prices=prices, signals=signals, input_hash=input_hash,
                          weight=str(limits.position), max_invested=str(limits.exposure),
                          minimum='50' if market == 'stock' else '25', drawdown_warning=str(limits.drawdown_warning))
        store.commit(updated, parent)
        if updated['valuations'][-1]['risk']['limit_breach']:
            print('SIMULATED EXPOSURE WARNING: existing holdings exceed assumed limits; no forced sale.')
        if updated['valuations'][-1]['risk']['drawdown_warning']:
            print('SIMULATED DRAWDOWN WARNING: threshold reached.')
    print('SIMULATION ONLY —', account_id, session, 'PENDING orders:', sum(o['status'] == 'PENDING' for o in updated['orders']))
    return updated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('market', choices=UNIVERSES)
    parser.add_argument('--recover', help='Exact prepared transaction SHA-256; validates before roll-forward')
    args = parser.parse_args()
    if args.recover:
        legacy_guard(Path('.'), args.market, args.market)
        store = Store(Path('simulation-v2') / args.market)
        with store.locked():
            store.recover(args.recover)
    else:
        run(args.market)


if __name__ == '__main__':
    main()
