"""Yahoo daily ingestion. Archive evidence before atomically accepting a universe."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

from . import Bar, ContractError, Provenance, build, endpoint, load, save
from .sessions import latest_completed

UNIVERSES = {'stock': ('AAPL', 'MSFT', 'NVDA', 'AMZN'),
             'crypto': ('DOGE-USD', 'SHIB-USD', 'PEPE-USD', 'BONK-USD')}


def atomic(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def archive_bytes(payload, directory, suffix):
    path = Path(directory) / (hashlib.sha256(payload).hexdigest() + suffix)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('xb') as stream:
            stream.write(payload)
    except FileExistsError:
        if path.read_bytes() != payload:
            raise ContractError(('HASH_MISMATCH',))
    return path


def download(symbol):
    request = urllib.request.Request(endpoint(symbol) + '?range=2y&interval=1d',
                                    headers={'User-Agent': 'Mozilla/5.0 EducationalResearch/1.0'})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def parse(payload, symbol, market, as_of, retrieved, code_version):
    data = json.loads(payload)['chart']
    if data.get('error'):
        # Provider wording does not prove delisting or lack of instrument support.
        raise ValueError('PROVIDER_REJECTED: ' + json.dumps(data['error'], sort_keys=True))
    results = data.get('result')
    if not results:
        raise ValueError('EMPTY_HISTORY: provider returned no result; support undetermined')
    result = results[0]
    if result['meta']['symbol'] != symbol:
        raise ValueError('SYMBOL_MISMATCH')
    timestamps = result.get('timestamp', [])
    quotes = result['indicators']['quote'][0]
    if not timestamps:
        raise ValueError('EMPTY_HISTORY: no observations; support undetermined')
    if any(len(quotes.get(key, [])) != len(timestamps) for key in ('close', 'high', 'low', 'volume')):
        raise ValueError('MALFORMED: quote lengths')
    end = latest_completed(as_of, market)
    rows = []
    bars = []
    zone = ZoneInfo('America/New_York') if market == 'stock' else timezone.utc
    for i, stamp in enumerate(timestamps):
        day = datetime.fromtimestamp(stamp, timezone.utc).astimezone(zone).date()
        if day > as_of.astimezone(zone).date():
            raise ValueError('FUTURE_SESSION')
        if day > end:  # Preserve raw response; unfinished bars never enter snapshots.
            continue
        values = [quotes[key][i] for key in ('close', 'high', 'low', 'volume')]
        if any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) for v in values):
            raise ValueError('INVALID_OHLCV: null or nonfinite value')
        close, high, low, volume = values
        if not 0 < low <= close <= high or volume < 0 or int(volume) != volume:
            raise ValueError('INVALID_OHLCV: price range or volume')
        bars.append(Bar(day.isoformat(), close))
        rows.append((day.isoformat(), symbol, close, high, low, int(volume)))
    minimum = 200 if market == 'stock' else 100
    if len(bars) < minimum:
        raise ValueError(f'INSUFFICIENT_HISTORY: fewer than {minimum} completed observations')
    provenance = Provenance(symbol, market, endpoint(symbol), retrieved.isoformat(),
                            as_of.isoformat(), bars[0].session, end.isoformat(), 'raw_close',
                            (('python', platform.python_version()),), code_version)
    return build(provenance, bars), rows


def collect(market, root=Path('.'), *, clock=None, fetch=download, code_version=None):
    root = Path(root)
    now = clock or (lambda: datetime.now(timezone.utc))
    as_of = now()
    code_version = code_version or subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    base = root / 'research' / 'datasets' / 'ingested'
    status = {'market': market, 'as_of': as_of.isoformat(), 'expected_symbols': list(UNIVERSES[market]),
              'status': 'BLOCKED', 'symbols': {}, 'publication': 'NOT_ATTEMPTED'}
    all_rows, snapshots = [], {}
    try:
        for symbol in UNIVERSES[market]:
            evidence = status['symbols'][symbol] = {}
            try:
                http, payload = fetch(symbol)
                retrieved = now()
                raw = archive_bytes(payload, base / 'raw', '.response')
                evidence.update(http_status=http, raw_path=str(raw.relative_to(root)),
                                retrieved_at=retrieved.isoformat())
                if http != 200:
                    raise ValueError(f'PROVIDER_HTTP_{http}: support/history undetermined')
                snapshot, rows = parse(payload, symbol, market, as_of, retrieved, code_version)
                path = save(snapshot, base / 'snapshots')
                snapshots[symbol] = str(path.relative_to(root))
                evidence.update(snapshot=snapshots[symbol], source_session=snapshot.provenance.end,
                                status='VALIDATED')
                all_rows.extend(rows)
            except Exception as exc:
                evidence.update(status='BLOCKED', reason=str(exc))
        if set(snapshots) != set(UNIVERSES[market]):
            raise ValueError('MISSING_SYMBOLS: ' + ', '.join(sorted(set(UNIVERSES[market]) - set(snapshots))))
        # Immutable bundle includes legacy HLCV export and links its exact bytes.
        output = io.StringIO(newline='')
        writer = csv.writer(output)
        writer.writerow(('date', 'ticker', 'close', 'high', 'low', 'volume'))
        writer.writerows(all_rows)
        csv_path = archive_bytes(output.getvalue().encode(), base / 'exports', '.csv')
        manifest = {'market': market, 'as_of': as_of.isoformat(), 'snapshots': snapshots,
                    'export': str(csv_path.relative_to(root)), 'symbols': status['symbols']}
        payload = (json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode()
        archive = archive_bytes(payload, base / 'bundles', '.json')
        pointer = base / (market + '-latest.json')
        prior = json.loads(pointer.read_text()) if pointer.exists() else None
        previous_sessions = {s: e.get('source_session') for s, e in prior['symbols'].items()} if prior else {}
        current_sessions = {s: e['source_session'] for s, e in status['symbols'].items()}
        status['publication'] = 'ATTEMPTED'
        # Pointer is the acceptance boundary; consumers verify all linked hashes.
        atomic(pointer, payload)
        status.update(status='NO_NEW_DATA' if previous_sessions == current_sessions else 'ACCEPTED',
                      publication='LOCAL_ACCEPTED', bundle=str(archive.relative_to(root)))
        return manifest
    except Exception as exc:
        status['reason'] = str(exc)
        if status['publication'] == 'ATTEMPTED':
            status['publication'] = 'FAILED'
        raise
    finally:
        atomic(root / 'work' / 'ingestion' / (market + '.json'),
               (json.dumps(status, sort_keys=True, indent=2) + '\n').encode())


def accepted_close(ticker, manifest_path):
    """Frozen consumer adapter: hash-check every symbol, coverage and current clock."""
    import pandas as pd
    pointer = Path(manifest_path)
    payload = pointer.read_bytes()
    bundle = pointer.parent / 'bundles' / (hashlib.sha256(payload).hexdigest() + '.json')
    if bundle.read_bytes() != payload:
        raise ValueError('BUNDLE_HASH_MISMATCH')
    manifest = json.loads(payload)
    market = manifest['market']
    if set(manifest['snapshots']) != set(UNIVERSES[market]):
        raise ValueError('MISSING_SYMBOLS')
    for evidence in manifest['symbols'].values():
        raw = Path(evidence['raw_path'])
        if raw.name != hashlib.sha256(raw.read_bytes()).hexdigest() + '.response':
            raise ValueError('RAW_HASH_MISMATCH')
    snapshots = {symbol: load(path) for symbol, path in manifest['snapshots'].items()}
    expected = latest_completed(datetime.now(timezone.utc), market).isoformat()
    for symbol, snapshot in snapshots.items():
        if snapshot.provenance.symbol != symbol or snapshot.provenance.market != market:
            raise ValueError('SYMBOL_MISMATCH')
        if snapshot.provenance.as_of != manifest['as_of'] or snapshot.provenance.end != expected:
            raise ValueError('STALE_OR_MISMATCHED_BUNDLE')
    snapshot = snapshots[ticker]
    return pd.Series([bar.close for bar in snapshot.bars],
                     index=pd.to_datetime([bar.session for bar in snapshot.bars]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('market', choices=UNIVERSES)
    args = parser.parse_args()
    collect(args.market)


if __name__ == '__main__':
    main()
