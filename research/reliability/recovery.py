"""Read-only verification of v1 unresolved historical evidence, never an importer.

Successful evidence checks do not authorize corrections or simulation advancement.
All prices below are saved simulated marks, not independently authenticated prices.
"""
import csv
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'research/reliability/recovery-v1/investigation.json'


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def checked_source(root, source):
    path = (root / source['path']).resolve()
    archive = (root / 'research/reliability/recovery-v1/evidence').resolve()
    if not path.is_relative_to(archive):
        raise ValueError('source outside recovery evidence archive')
    payload = path.read_bytes()
    if digest(payload) != source['sha256']:
        raise ValueError('recovery source SHA-256 mismatch')
    header = f'blob {len(payload)}\0'.encode()
    if hashlib.sha1(header + payload).hexdigest() != source['git_blob']:
        raise ValueError('recovery source Git blob mismatch')
    return payload


def verify(root=ROOT):
    """Reproduce arithmetic and trace identities; fail on corrupt evidence.

    This version intentionally has no accepted-correction path. Future verified
    corrections need a new schema, independent evidence and reviewed integration.
    """
    root = Path(root)
    manifest = json.loads((root / MANIFEST.relative_to(ROOT)).read_text())
    if (manifest['schema_version'] != 1 or manifest['status'] != 'BLOCKED'
            or manifest['accepted_corrections'] != []
            or manifest['derived_reconciled_view'] is not None):
        raise ValueError('v1 unresolved evidence cannot authorize reconciliation')
    for source in manifest['originals'].values():
        checked_source(root, source)
    findings = []
    for item in manifest['stock_rows']:
        if item['status'] != 'UNRESOLVED' or item['verified_market_session'] is not None:
            raise ValueError('unverified market-session assignment')
        sources = {name: checked_source(root, source)
                   for name, source in item['sources'].items()}
        parents = {name: checked_source(root, source)
                   for name, source in item['parent_sources'].items()}
        ledger = sources['paper/performance.csv']
        line = ledger.splitlines(keepends=True)[item['line_number'] - 1]
        if digest(line) != item['row_sha256'] or line.decode() != item['row_text']:
            raise ValueError('disputed physical row mismatch')
        if (ledger != parents['paper/performance.csv'] + line
                or sources['paper/journal.csv'] != parents['paper/journal.csv']):
            raise ValueError('append-only trace or unchanged journal mismatch')
        rows = list(csv.DictReader(io.StringIO(ledger.decode())))
        row = rows[item['line_number'] - 2]
        state = json.loads(sources['paper/state.json'])
        signals = list(csv.DictReader(io.StringIO(sources['paper/latest_signals.csv'].decode())))
        prices = {s['ticker']: float(s['close']) for s in signals}
        if len(prices) != len(signals) or set(prices) != {'AAPL', 'MSFT', 'NVDA', 'AMZN'}:
            raise ValueError('incomplete saved signal universe')
        equity = state['cash'] + sum(p['shares'] * prices[t]
                                     for t, p in state['positions'].items())
        if (round(equity, 2) != float(row['paper_value'])
                or round(state['cash'], 2) != float(row['cash'])
                or len(state['positions']) != int(row['open_positions'])
                or state['last_run_date'] != row['date_utc']):
            raise ValueError('saved valuation/state arithmetic mismatch')
        findings.append({'commit': item['commit'], 'line_number': item['line_number'],
                         'saved_label': row['date_utc'], 'saved_value': row['paper_value'],
                         'arithmetic': 'MATCHES_SAVED_MARKS_ONLY',
                         'verified_market_session': None, 'status': 'UNRESOLVED'})
    return {'schema_version': 1, 'status': 'BLOCKED', 'accepted_corrections': [],
            'stock_rows': findings, 'reason': manifest['reason']}


def corroborate_stock(root=ROOT):
    """Match saved four-symbol marks to later Yahoo bars, without assigning dates."""
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    root = Path(root)
    manifest = json.loads((root / MANIFEST.relative_to(ROOT)).read_text())
    archive = json.loads((root / MANIFEST.relative_to(ROOT).parent /
                          'stock-corroboration.json').read_text())
    prices = {}
    for source in archive['sources']:
        payload = (root / source['path']).read_bytes()
        if digest(payload) != source['sha256']:
            raise ValueError('corroborating response hash mismatch')
        result = json.loads(payload)['chart']['result'][0]
        symbol = result['meta']['symbol']
        quotes = result['indicators']['quote'][0]['close']
        prices[symbol] = {datetime.fromtimestamp(t, timezone.utc).astimezone(
            ZoneInfo('America/New_York')).date().isoformat(): round(v, 4)
            for t, v in zip(result['timestamp'], quotes) if v is not None}
    if set(prices) != {'AAPL', 'MSFT', 'NVDA', 'AMZN'}:
        raise ValueError('incomplete corroborating universe')
    candidates = []
    for row in manifest['stock_rows']:
        signals = checked_source(root, row['sources']['paper/latest_signals.csv'])
        marks = {s['ticker']: float(s['close']) for s in csv.DictReader(io.StringIO(signals.decode()))}
        matches = sorted(day for day in prices['AAPL']
                         if all(prices[t].get(day) == marks[t] for t in prices))
        candidates.append({'commit': row['commit'], 'matching_later_provider_dates': matches,
                           'verified_market_session': None, 'status': 'CORROBORATION_ONLY'})
    return candidates


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2, sort_keys=True))
    raise SystemExit(2)  # Verified archive integrity still means blocked recovery.
