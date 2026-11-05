"""Verify accepted #21 evidence, then freeze observations before any later outcome.

Run from repository root: python -m copilot.publish
No downloads. Only public market-derived fields are published, never raw responses.
"""
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess

from data_contracts import instant, load
from data_contracts.ingestion import UNIVERSES, parse, archive_bytes, atomic
from data_contracts.sessions import latest_completed, session_close

RULE = 'copilot-sma-rsi-v1'


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def checked_path(root, name, directory, suffix):
    base = (root / 'research/datasets/ingested' / directory).resolve()
    path = (root / name).resolve()
    if path.parent != base or path.suffix != suffix:
        raise ValueError('Evidence path outside expected archive')
    payload = path.read_bytes()
    if path.name != hashlib.sha256(payload).hexdigest() + suffix:
        raise ValueError('Evidence hash mismatch')
    return path, payload


def verified(root, now):
    """Reparse preserved provider bytes; hashes alone do not verify indicator claims."""
    pointer = root / 'research/datasets/ingested/stock-latest.json'
    payload = pointer.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    _, frozen = checked_path(root, f'research/datasets/ingested/bundles/{digest}.json', 'bundles', '.json')
    if frozen != payload:
        raise ValueError('Acceptance bundle mismatch')
    manifest = json.loads(payload)
    symbols = UNIVERSES['stock']
    if manifest['market'] != 'stock' or set(manifest['snapshots']) != set(symbols) or set(manifest['symbols']) != set(symbols):
        raise ValueError('Incomplete stock universe')
    as_of = instant(manifest['as_of'])
    if as_of > now:
        raise ValueError('Future acceptance clock')
    expected = latest_completed(now, 'stock').isoformat()
    all_rows, result = [], {}
    for symbol in symbols:
        evidence = manifest['symbols'][symbol]
        path, _ = checked_path(root, manifest['snapshots'][symbol], 'snapshots', '.json')
        snapshot = load(path)
        p = snapshot.provenance
        if (p.symbol, p.market, p.end, p.as_of, p.classification, p.adjustment) != (symbol, 'stock', expected, manifest['as_of'], 'historical research', 'raw_close'):
            raise ValueError('Stale, mismatched or synthetic snapshot')
        retrieved = instant(evidence['retrieved_at'])
        if retrieved > now or retrieved.isoformat() != instant(p.retrieved_at).isoformat() or evidence['http_status'] != 200 or evidence['status'] != 'VALIDATED' or evidence['source_session'] != expected or evidence['snapshot'] != manifest['snapshots'][symbol]:
            raise ValueError('Unverified retrieval evidence')
        _, raw = checked_path(root, evidence['raw_path'], 'raw', '.response')
        rebuilt, rows = parse(raw, symbol, 'stock', as_of, retrieved, p.code_version)
        if rebuilt != snapshot or any(row[5] <= 0 for row in rows):
            raise ValueError('Raw/snapshot mismatch or missing volume')
        all_rows.extend(rows)
        result[symbol] = [{'session':r[0], 'close':r[2], 'high':r[3], 'low':r[4], 'volume':r[5]} for r in rows]
    _, exported = checked_path(root, manifest['export'], 'exports', '.csv')
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(('date', 'ticker', 'close', 'high', 'low', 'volume'))
    writer.writerows(all_rows)
    if exported != output.getvalue().encode():
        raise ValueError('Export not derived from verified raw evidence')
    return digest, result


def deadline(now):
    day = latest_completed(now, 'stock') + timedelta(days=1)
    while True:
        close = session_close(day, 'stock')
        if close and close > now:
            return close
        day += timedelta(days=1)


def publish(root=Path('.'), now=None):
    root = Path(root).resolve()
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Aware observation clock required')
    now = now.astimezone(timezone.utc)
    try:
        digest, rows = verified(root, now)
        quality, reason = 'VERIFIED', 'Complete accepted universe; raw responses, snapshots and export agree. Provider identity is trusted through the configured collector, not independently attested.'
    except (ValueError, KeyError, TypeError, OSError) as error:
        digest, rows, quality = None, {}, 'BLOCKED'
        reason = 'Accepted evidence unavailable or invalid (' + type(error).__name__ + '). See ingestion diagnostics; legacy chart CSVs cannot establish verification.'
    try:
        valid_until = deadline(now).isoformat()
    except ValueError:
        valid_until = now.isoformat()
        quality, rows, reason = 'BLOCKED', {}, 'Calendar unsupported; extend the reviewed calendar.'
    observations = []
    for symbol in UNIVERSES['stock']:
        bars = rows.get(symbol, [])[-100:]
        session = bars[-1]['session'] if bars else None
        observation = dict(schema_version=1, rule=RULE, symbol=symbol, timeframe='1d',
                           observed_at=now.isoformat(), valid_until=valid_until,
                           source_session=session,
                           source_timestamp=session_close(datetime.fromisoformat(session).date(), 'stock').isoformat() if session else None,
                           quality=quality, reason=reason, evidence='validated-provider-snapshot' if bars else 'unavailable',
                           bundle_sha256=digest, bars=bars,
                           volume_profile='Historical candle approximation only; unvalidated saved profiles are excluded from signal votes.',
                           evaluation='PENDING — no future outcomes evaluated',
                           implementation_sha256=hashlib.sha256(b''.join((Path(__file__).resolve().parents[1]/p).read_bytes() for p in ('copilot/publish.py','docs/chart_intelligence.js','docs/copilot_engine.js'))).hexdigest())
        # Reuse the exact frontend indicator implementation and signal rules.
        script = "const fs=require('fs'), e=require('./docs/copilot_engine.js'); const x=JSON.parse(fs.readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(e.assess(x,Date.parse(x.observed_at))));"
        observation['analysis'] = json.loads(subprocess.check_output(['node', '-e', script], input=canonical(observation), cwd=Path(__file__).resolve().parents[1]))
        observations.append(observation)
    envelope = dict(schema_version=1, observed_at=now.isoformat(), observations=observations)
    out = root / 'docs/copilot'
    # Create-only content-addressed records. Latest is only an index to frozen bytes.
    path = archive_bytes(canonical(envelope), out / 'observations', '.json')
    atomic(out / 'latest.json', canonical({'schema_version':1, 'path':'observations/'+path.name, 'sha256':path.stem}))
    return envelope


if __name__ == '__main__':
    report = publish()
    print('COPILOT — simulation only:', report['observations'][0]['quality'])
    print('Observed at:', report['observed_at'], '— later evaluation PENDING')
