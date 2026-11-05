"""Evidence-backed simulation health. Read-only account inspection; no repairs."""
import argparse
import csv
import io
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
from datetime import datetime, timedelta, timezone

from data_contracts import load, validate, canonical
from data_contracts.ingestion import UNIVERSES, atomic, parse
from data_contracts.sessions import latest_completed, session_close, VERSION
from monitoring.health import collect_actions, VARIANTS
from paper_sessions import recorded_sessions, canonical_session

REPO = 'iikaitlynii/trading-bot'
BASE = 'https://github.com/' + REPO
CONFIG = {'stock': ('paper', 'paper-trading.yml'),
          'crypto': ('crypto_paper', 'crypto-paper-trading.yml')}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def instant(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('timestamp must include timezone')
    return result.astimezone(timezone.utc)


def number(value, *, positive=False):
    if isinstance(value, bool) or not math.isfinite(float(value)) or float(value) < 0 or (positive and float(value) == 0):
        raise ValueError('invalid numeric account record')
    return float(value)


def next_close(now, market):
    day = latest_completed(now, market) + timedelta(days=1)
    while True:
        close = session_close(day, market)
        if close is not None:
            return close
        day += timedelta(days=1)


def account_files(market):
    folder = CONFIG[market][0]
    return [f'{folder}/{name}' for name in ('state.json', 'performance.csv', 'journal.csv', 'latest_signals.csv')]


def account(root, market):
    folder = root / CONFIG[market][0]
    sessions = recorded_sessions(folder / 'performance.csv')
    if not sessions:
        raise ValueError('missing account ledger')
    state = read(folder / 'state.json')
    session = canonical_session(state.get('last_price_session') if market == 'crypto' else state.get('last_run_date'))
    if session != sessions[-1]:
        raise ValueError('state/ledger session mismatch or unknown legacy crypto session')
    number(state['cash'])
    positions = state['positions']
    if not isinstance(positions, dict) or set(positions) - set(UNIVERSES[market]):
        raise ValueError('unknown account position')
    quantity = 'units' if market == 'crypto' else 'shares'
    for position in positions.values():
        number(position[quantity], positive=True)
        number(position['entry_price'], positive=True)
    with (folder / 'performance.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        number(row['paper_value'], positive=True)
        number(row['cash'])
        if not float(row['open_positions']).is_integer() or number(row['open_positions']) > len(UNIVERSES[market]):
            raise ValueError('invalid position count')
    last = rows[-1]
    if abs(float(last['cash']) - state['cash']) > .011 or int(last['open_positions']) != len(positions):
        raise ValueError('state/ledger balances mismatch')
    with (folder / 'latest_signals.csv').open() as stream:
        signals = list(csv.DictReader(stream))
    marks = {r['ticker']: r for r in signals}
    if len(marks) != len(signals) or set(marks) != set(UNIVERSES[market]):
        raise ValueError('incomplete account marks')
    for row in signals:
        if row['price_session'] != session or row['signal'] == 'NO_DATA':
            raise ValueError('invalid account mark session')
        number(row['close'], positive=True)
    value = state['cash'] + sum(p[quantity] * float(marks[s]['close']) for s, p in positions.items())
    if abs(value - float(last['paper_value'])) > .011:
        raise ValueError('state/marks equity mismatch')
    with (folder / 'journal.csv').open() as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not {'date_utc', 'ticker', 'action', 'price', quantity}.issubset(reader.fieldnames):
            raise ValueError('invalid journal schema')
        journal = list(reader)
    if len({json.dumps(r, sort_keys=True) for r in journal}) != len(journal):
        raise ValueError('duplicate journal records')
    previous = ''
    replay_cash = 5000.0 if market == 'crypto' else 10000.0
    replay_positions = {}
    for row in journal:
        day = canonical_session(row['date_utc'])
        if day < previous or day > session or row['ticker'] not in UNIVERSES[market] or row['action'] not in ('SIM_BUY', 'SIM_SELL'):
            raise ValueError('invalid journal identity/order')
        number(row['price'], positive=True)
        number(row[quantity], positive=True)
        amount = float(row['price']) * float(row[quantity])
        symbol = row['ticker']
        if row['action'] == 'SIM_BUY':
            replay_cash -= amount
            replay_positions[symbol] = replay_positions.get(symbol, 0) + float(row[quantity])
        else:
            replay_cash += amount
            replay_positions[symbol] = replay_positions.get(symbol, 0) - float(row[quantity])
        if replay_cash < -.02 or replay_positions[symbol] < -1e-8:
            raise ValueError('journal overspends cash or holdings')
        previous = day
    if abs(replay_cash - state['cash']) > .02 or any(
            not math.isclose(replay_positions.get(symbol, 0), positions.get(symbol, {}).get(quantity, 0), abs_tol=1e-8)
            for symbol in set(replay_positions) | set(positions)):
        raise ValueError('journal/state reconciliation mismatch')
    return session


def accepted(root, market, now):
    path = root / f'research/datasets/ingested/{market}-latest.json'
    manifest = read(path)
    bundle = path.parent / 'bundles' / (digest(path) + '.json')
    if bundle.read_bytes() != path.read_bytes() or manifest['market'] != market:
        raise ValueError('invalid accepted bundle hash/market')
    if instant(manifest['as_of']) > now:
        raise ValueError('future accepted evidence')
    universe = set(UNIVERSES[market])
    if set(manifest['snapshots']) != universe or set(manifest['symbols']) != universe:
        raise ValueError('incomplete accepted universe')
    expected = latest_completed(now, market).isoformat()
    export_rows = []
    for symbol in UNIVERSES[market]:
        snapshot = load(root / manifest['snapshots'][symbol])
        if validate(snapshot):
            raise ValueError('accepted snapshot contract invalid')
        p = snapshot.provenance
        if (p.symbol != symbol or p.market != market or p.end != expected
                or p.as_of != manifest['as_of'] or p.classification != 'historical research'
                or p.adjustment != 'raw_close'):
            raise ValueError('stale, synthetic or mismatched accepted snapshot')
        evidence = manifest['symbols'][symbol]
        raw = root / evidence['raw_path']
        if (raw.name != digest(raw) + '.response' or evidence['source_session'] != expected
                or evidence['status'] != 'VALIDATED' or evidence['http_status'] != 200):
            raise ValueError('invalid raw source evidence')
        reparsed, raw_rows = parse(raw.read_bytes(), symbol, market, instant(p.as_of), instant(p.retrieved_at), p.code_version)
        export_rows.extend(raw_rows)
        if canonical(reparsed) != canonical(snapshot):
            raise ValueError('raw bytes do not reproduce accepted snapshot')
    export = root / manifest['export']
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(('date', 'ticker', 'close', 'high', 'low', 'volume'))
    writer.writerows(export_rows)
    if export.read_bytes() != output.getvalue().encode() or export.name != digest(export) + '.csv':
        raise ValueError('invalid accepted export hash')
    return expected, digest(path), manifest['symbols']


def row(root, market, now, actions):
    folder, workflow = CONFIG[market]
    result = dict(id=market, label=market.upper(), status='BLOCKED', reason_codes=[],
                  explanations=[], expected_session=None, last_verified_data_session=None,
                  last_successful_account_advancement=None, last_recorded_valuation=None,
                  checked_at=now.isoformat(), expires_at=None, data_fresh=False,
                  workflow=actions.get(workflow, {'status': 'UNKNOWN'}),
                  evidence=[BASE + '/blob/main/research/reliability/README.md',
                            BASE + f'/blob/main/{folder}/performance.csv'])
    def block(code, explanation):
        result['reason_codes'].append(code)
        result['explanations'].append(explanation)
    try:
        result['expected_session'] = latest_completed(now, market).isoformat()
        result['expires_at'] = min(next_close(now, market), now + timedelta(hours=26)).isoformat()
    except ValueError as exc:
        block('CALENDAR_UNSUPPORTED', str(exc))
    try:
        with (root / folder / 'performance.csv').open() as stream:
            result['last_recorded_valuation'] = list(csv.DictReader(stream))[-1]['date_utc']
    except (OSError, ValueError, KeyError, IndexError):
        pass
    bundle_hash = None
    try:
        session, bundle_hash, symbols = accepted(root, market, now)
        result.update(last_verified_data_session=session, data_fresh=True, symbols=symbols)
    except Exception as exc:
        block('DATA_MISSING_INVALID_OR_STALE', str(exc))
        try:
            manifest = read(root / f'research/datasets/ingested/{market}-latest.json')
            old_session, _, symbols = accepted(root, market, instant(manifest['as_of']))
            result.update(last_verified_data_session=old_session, symbols=symbols)
        except Exception:
            pass
    try:
        session = account(root, market)
        if session != result['expected_session']:
            raise ValueError('account has not processed expected completed session')
    except Exception as exc:
        block('ACCOUNT_INVALID_OR_STALE', str(exc))
    if market == 'stock':
        inventory = root / 'research/reliability/recovery-v1/investigation.json'
        if inventory.exists():
            try:
                historical = read(inventory)
                if historical.get('schema_version') != 1 or historical.get('stock_rows'):
                    block('HISTORICAL_RECONCILIATION_REQUIRED', historical.get('reason', 'Unresolved historical stock evidence.'))
                result['evidence'].append(BASE + '/blob/main/research/reliability/recovery-v1/README.md')
            except Exception as exc:
                block('HISTORICAL_EVIDENCE_INVALID', str(exc))
    receipt = None
    try:
        receipt = read(root / f'monitoring/account_receipts/{market}.json')
        run = result['workflow']
        if (receipt['schema_version'] != 1 or receipt['session'] != result['expected_session']
                or receipt['bundle_sha256'] != bundle_hash or receipt['publication'] != 'CONFIRMED'
                or receipt['simulation'] != 'success' or receipt['outcome'] not in ('ADVANCED', 'ALREADY_PROCESSED')
                or instant(receipt['checked_at']) > now
                or run['status'] != 'SUCCESS' or run['run_id'] != receipt['run_id']
                or run['run_attempt'] != receipt['run_attempt']
                or run['url'] != BASE + '/actions/runs/' + str(receipt['run_id'])
                or set(receipt['files']) != set(account_files(market))
                or any(digest(root / p) != h for p, h in receipt['files'].items())):
            raise ValueError('publication receipt does not match current files, session and successful run')
        result['evidence'].append(BASE + f'/blob/main/monitoring/account_receipts/{market}.json')
        result['last_successful_account_advancement'] = receipt.get('last_advancement')
    except Exception as exc:
        block('PUBLICATION_UNCONFIRMED', str(exc))
    # Explicit latest-ingestion failure must not be masked by an older accepted pointer.
    try:
        attempt = read(root / f'monitoring/ingestion/{market}.json')
        if instant(attempt['as_of']) > now or attempt['status'] not in ('ACCEPTED', 'NO_NEW_DATA'):
            raise ValueError(attempt.get('reason', 'latest ingestion failed'))
        if latest_completed(instant(attempt['as_of']), market).isoformat() != result['expected_session']:
            raise ValueError('latest ingestion status is overdue')
    except Exception as exc:
        block('INGESTION_UNKNOWN_OR_BLOCKED', str(exc))
    if not result['reason_codes']:
        result['status'] = 'ACTIVE' if receipt['outcome'] == 'ADVANCED' else 'PAUSED'
        result['reason_codes'] = ['ACCOUNT_PUBLISHED' if result['status'] == 'ACTIVE' else 'ALREADY_PROCESSED']
        result['explanations'] = ['Complete accepted inputs and matching account publication verified.' if result['status'] == 'ACTIVE'
                                  else 'Expected completed session already recorded; no overdue session.']
    return result


def build(root, now, actions):
    root = Path(root)
    rows = [row(root, market, now, actions) for market in CONFIG]
    children = []
    for variant in VARIANTS:
        saved = None
        try:
            state = read(root / 'research_lab/forward/state.json')
            saved = state[variant]['last_session']
        except Exception:
            pass
        children.append(dict(id=variant, last_recorded_valuation=saved, status='BLOCKED',
                             reason_codes=['FORWARD_INPUTS_UNVERIFIED', 'PUBLICATION_UNCONFIRMED']))
    rows.append(dict(id='forward', label='FORWARD RESEARCH', status='BLOCKED',
                     reason_codes=['FORWARD_INPUTS_UNVERIFIED', 'PUBLICATION_UNCONFIRMED'],
                     explanations=['All four forward accounts use separate downloads without accepted input or publication receipts. Saved valuations remain historical and unverified.'],
                     checked_at=now.isoformat(), expires_at=rows[0]['expires_at'],
                     expected_session=rows[0]['expected_session'], last_verified_data_session=None,
                     last_successful_account_advancement=None, last_recorded_valuation=None,
                     data_fresh=False, accounts=children, workflow=actions.get('paper-trading.yml', {'status':'UNKNOWN'}),
                     evidence=[BASE + '/blob/main/research_lab/forward/performance.csv',
                               BASE + '/blob/main/research/reliability/recovery-v1/README.md']))
    return dict(schema_version=1, simulation_only=True, checked_at=now.isoformat(), calendar_version=VERSION, accounts=rows)


def git(*args):
    return subprocess.check_output(['git', *args])


def capture(market):
    path = Path(f'work/account-health/{market}-before.json')
    atomic(path, json.dumps({'files': {p: digest(p) for p in account_files(market)}}).encode())


def record(market, simulation, publication):
    """Called only after the producer's actual push step; confirmation is a second commit."""
    target = Path(f'monitoring/account_receipts/{market}.json')
    prior = read(target) if target.exists() else {}
    target.unlink(missing_ok=True)  # Never preserve a misleading current receipt on failure.
    source = Path(f'work/ingestion/{market}.json')
    if source.exists():
        atomic(Path(f'monitoring/ingestion/{market}.json'), source.read_bytes())
    if simulation != 'success' or publication != 'success':
        return
    now = datetime.now(timezone.utc)
    session = account(Path('.'), market)
    verified, bundle_hash, _ = accepted(Path('.'), market, now)
    if session != verified:
        raise ValueError('published account session does not match accepted input')
    before = read(f'work/account-health/{market}-before.json')['files']
    files = {p: digest(p) for p in account_files(market)}
    # HEAD is the producer commit after push/rebase; verify every recorded byte.
    for path, expected in files.items():
        if hashlib.sha256(git('show', 'HEAD:' + path)).hexdigest() != expected:
            raise ValueError('account files were not committed')
    receipt = dict(schema_version=1, session=session, bundle_sha256=bundle_hash,
                   files=files, simulation=simulation, publication='CONFIRMED',
                   outcome='ADVANCED' if before[account_files(market)[1]] != files[account_files(market)[1]] else 'ALREADY_PROCESSED',
                   run_id=int(os.environ['GITHUB_RUN_ID']), run_attempt=int(os.environ['GITHUB_RUN_ATTEMPT']),
                   last_advancement=session if before[account_files(market)[1]] != files[account_files(market)[1]] else prior.get('last_advancement'),
                   output_commit=git('rev-parse', 'HEAD').decode().strip(), checked_at=now.isoformat())
    atomic(target, (json.dumps(receipt, indent=2) + '\n').encode())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--capture', choices=CONFIG)
    parser.add_argument('--record', choices=CONFIG)
    parser.add_argument('--simulation', default='unknown')
    parser.add_argument('--publication', default='unknown')
    parser.add_argument('--actions-json', type=Path)
    args = parser.parse_args()
    if args.capture:
        capture(args.capture)
    elif args.record:
        try:
            record(args.record, args.simulation, args.publication)
        except Exception as exc:
            print('Account receipt withheld: ' + str(exc))
    else:
        actions = {}
        try:
            actions = read(args.actions_json) if args.actions_json else collect_actions(REPO, os.environ.get('GH_TOKEN', ''))
        except Exception:
            pass  # Missing Actions evidence explicitly blocks each affected account.
        result = build(Path('.'), datetime.now(timezone.utc), actions)
        atomic(Path('docs/account-health/status.json'), (json.dumps(result, indent=2) + '\n').encode())


if __name__ == '__main__':
    main()
