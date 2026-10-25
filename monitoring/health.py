"""Read saved research files and Actions metadata; never run trading code."""
import argparse
import csv
import hashlib
import json
import math
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from data_contracts.sessions import VERSION, latest_completed, session_close


# Explicit contracts: output existence does not prove a successful market refresh.
OUTPUTS = {
    'paper-trading.yml': ['paper/latest_signals.csv', 'paper/report.txt',
                         'strategy_comparison_results.csv', 'research_lab/latest_shadow_results.csv',
                         'research_lab/report.txt', 'research_lab/forward/performance.csv'],
    'crypto-paper-trading.yml': ['crypto_paper/latest_signals.csv', 'crypto_paper/performance.csv'],
    'stock-history-research.yml': ['research/stock_history.csv'],
    'etf-history-research.yml': ['research/etf_history.csv'],
    'smart-money-research.yml': ['smart_money/health_report.txt', 'smart_money/integrity_status.json',
                                 'smart_money/latest_scores.csv', 'smart_money/paper_comparison.csv'],
    'token-discovery-research.yml': ['crypto_paper/discovered_tokens.csv'],
    'performance-reports.yml': ['reports/stocks.json', 'reports/crypto.json'],
    'backtest.yml': ['results/latest_results.txt', 'results/stress_results.txt'],
}
# Independent requested universes: never infer coverage from the rows that survived.
# Regression tests compare these manifests with the producer configuration.
STOCK_SYMBOLS = ('AAPL', 'MSFT', 'NVDA', 'AMZN')
CRYPTO_SYMBOLS = ('DOGE-USD', 'SHIB-USD', 'PEPE-USD', 'BONK-USD')
VARIANTS = ('current_20_50', 'faster_10_30', 'conservative_30_75', 'low_concentration_20_50')


@dataclass(frozen=True)
class SourceContract:
    date_column: str
    symbol_columns: tuple
    market: str
    expected_symbols: tuple
    value_column: str = 'close'
    history: bool = False


SOURCES = {
    'paper/latest_signals.csv': SourceContract('price_session', ('ticker',), 'stock', STOCK_SYMBOLS),
    'crypto_paper/latest_signals.csv': SourceContract('price_session', ('ticker',), 'crypto', CRYPTO_SYMBOLS),
    'research/stock_history.csv': SourceContract('date', ('ticker',), 'stock', STOCK_SYMBOLS, history=True),
    # A comparison has no close column. Require a positive session count instead.
    'strategy_comparison_results.csv': SourceContract('as_of', ('asset',), 'mixed',
                                                     STOCK_SYMBOLS + CRYPTO_SYMBOLS, 'sessions'),
    'research_lab/latest_shadow_results.csv': SourceContract(
        'market_session', ('universe', 'variant'), 'stock',
        tuple(f'{universe}/{variant}' for universe in ('core4', 'diversified16') for variant in VARIANTS),
        'ending_value'),
    'research_lab/forward/performance.csv': SourceContract(
        'market_session', ('variant',), 'stock', VARIANTS, 'paper_value', history=True),
}


def expected_session(now, market):
    """Use the shared bounded XNYS/UTC contract, with exact close boundaries."""
    return latest_completed(now, market)


def file_evidence(root, path):
    target = root / path
    try:
        data = target.read_bytes()
        if not data.strip():
            return {'status': 'EMPTY'}
        if path.endswith('.csv'):
            rows = list(csv.DictReader(data.decode('utf-8-sig').splitlines()))
            if not rows:
                return {'status': 'EMPTY'}
        elif path.endswith('.json'):
            json.loads(data)
        return {'status': 'PRESENT', 'sha256': hashlib.sha256(data).hexdigest()}
    except FileNotFoundError:
        return {'status': 'MISSING'}
    except (ValueError, UnicodeError, OSError, csv.Error):
        return {'status': 'INVALID'}


def source_evidence(root, path, column, symbol, market, now, *, expected_symbols=None,
                    value_column='close', history=False):
    """Validate schema, requested coverage and records before making freshness claims.

    Unknown output paths require an explicit expected universe; observed rows cannot
    establish that an asset was not omitted. Snapshot duplicates are rejected even
    across dates; history permits multiple sessions but never duplicate keys.
    """
    result = file_evidence(root, path)
    if result['status'] != 'PRESENT':
        return result
    contract = SOURCES.get(path)
    if expected_symbols is None and contract:
        expected_symbols = contract.expected_symbols
    if contract:
        value_column, history = contract.value_column, contract.history
    if not expected_symbols:
        return dict(result, status='UNKNOWN_COVERAGE')
    symbol_columns = (symbol,) if isinstance(symbol, str) else symbol
    expected_symbols = set(expected_symbols)
    latest, seen, observed, no_data = {}, set(), set(), set()
    issues = set()
    try:
        with (root / path).open(newline='', encoding='utf-8-sig') as handle:
            reader = csv.DictReader(handle)
            fields = reader.fieldnames or []
            if len(set(fields)) != len(fields):
                issues.add('DUPLICATE_COLUMNS')
            required = {column, value_column, *symbol_columns}
            if required - set(fields):
                issues.add('MISSING_REQUIRED_COLUMNS')
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    issues.add('MALFORMED_ROW')
                parts = [row.get(key) for key in symbol_columns]
                if any(not part or not part.strip() or part != part.strip() for part in parts):
                    issues.add('INVALID_SYMBOL')
                    continue
                name = '/'.join(parts)
                observed.add(name)
                # NO_DATA is an availability state, never a successful observation,
                # even when the producer omits close/price_session or includes a price.
                if (row.get('signal') or '').strip().upper() == 'NO_DATA':
                    no_data.add(name)
                    continue
                try:
                    session = date.fromisoformat(row[column])
                    if session.isoformat() != row[column]:
                        raise ValueError('noncanonical source session')
                    value = float(row[value_column])
                    if not math.isfinite(value) or (value_column in ('close', 'sessions') and value <= 0):
                        raise ValueError('nonpositive or nonfinite value')
                except (KeyError, TypeError, ValueError):
                    issues.add('INVALID_SOURCE_DATE_OR_VALUE')
                    continue
                kind = 'crypto' if market == 'crypto' or (market == 'mixed' and name.endswith('-USD')) else 'stock'
                # Reject holidays and unfinished source bars, not merely stale dates.
                close = session_close(session, kind)
                if close is None or close > now or session > expected_session(now, kind):
                    issues.add('INVALID_OR_UNFINISHED_SESSION')
                key = (name, session) if history else name
                if key in seen:
                    issues.add('DUPLICATE_RECORD')
                seen.add(key)
                latest[name] = max(latest.get(name, session), session)
        missing = expected_symbols - observed
        unexpected = observed - expected_symbols
        if missing:
            issues.add('MISSING_ASSETS')
        if unexpected:
            issues.add('UNEXPECTED_ASSETS')
        stale = sorted(name for name, day in latest.items() if day < expected_session(
            now, 'crypto' if market == 'crypto' or (market == 'mixed' and name.endswith('-USD')) else 'stock'))
        # NO_DATA takes precedence over price-schema errors so unavailable feeds have
        # an honest status. Issues still disclose malformed records and omissions.
        status = ('NO_DATA' if no_data else 'INVALID' if issues else 'STALE' if stale else 'FRESH')
        result.update(status=status, issues=sorted(issues), missing_symbols=sorted(missing),
                      unexpected_symbols=sorted(unexpected), no_data_symbols=sorted(no_data),
                      source_sessions={name: day.isoformat() for name, day in sorted(latest.items())},
                      stale_symbols=stale, calendar_version=VERSION if market != 'crypto' else 'utc-daily-v1')
    except (KeyError, TypeError, ValueError, OSError, csv.Error) as exc:
        result.update(status='UNKNOWN_SOURCE_DATE_OR_INVALID_DATA', issues=[type(exc).__name__])
    return result


def workflow_evidence(workflow, runs):
    if workflow is None:
        return {'status': 'MISSING_WORKFLOW'}
    result = {'workflow_id': workflow['id'], 'path': workflow['path']}
    runs = sorted((r for r in runs if r['workflow_id'] == workflow['id']),
                  key=lambda r: (r['run_number'], r.get('run_attempt', 1)), reverse=True)
    if not runs:
        return dict(result, status='NEVER_RUN')
    run = runs[0]
    state = (run.get('conclusion') or 'UNKNOWN').upper() if run['status'] == 'completed' else 'IN_PROGRESS'
    success = next((r for r in runs if r.get('conclusion') == 'success'), None)
    return dict(result, status=state, run_id=run['id'], run_attempt=run.get('run_attempt', 1),
                url=run['html_url'], updated_at=run['updated_at'],
                last_successful_run_at=success['updated_at'] if success else None,
                last_successful_run_id=success['id'] if success else None)


def api_pages(repository, endpoint, key, token):
    collected = []
    page = 1
    while True:
        separator = '&' if '?' in endpoint else '?'
        request = Request(f'https://api.github.com/repos/{repository}/{endpoint}{separator}per_page=100&page={page}',
                          headers={'Accept': 'application/vnd.github+json',
                                   'Authorization': f'Bearer {token}', 'User-Agent': 'research-health'})
        with urlopen(request, timeout=30) as response:
            batch = json.load(response)[key]
        collected.extend(batch)
        if len(batch) < 100:
            return collected
        page += 1


def collect_actions(repository, token):
    workflows = api_pages(repository, 'actions/workflows', 'workflows', token)
    evidence = {}
    for filename in OUTPUTS:
        workflow = next((w for w in workflows if w['path'] == f'.github/workflows/{filename}'), None)
        # Only latest runs needed; pagination is still required to avoid hiding old successes.
        runs = api_pages(repository, f"actions/workflows/{workflow['id']}/runs?branch=main", 'workflow_runs', token) if workflow else []
        evidence[filename] = workflow_evidence(workflow, runs)
    return evidence


def build_report(root, now, actions, previous=None):
    files = {path: file_evidence(root, path) for paths in OUTPUTS.values() for path in paths}
    sources = {path: source_evidence(root, path, spec.date_column, spec.symbol_columns, spec.market, now,
                                    expected_symbols=spec.expected_symbols,
                                    value_column=spec.value_column, history=spec.history)
               for path, spec in SOURCES.items()}
    actions = {name: actions.get(name, {'status': 'UNKNOWN'}) for name in OUTPUTS}
    alerts = {}
    for category, entries, healthy in [('workflows', actions, {'SUCCESS'}),
                                       ('outputs', files, {'PRESENT'}), ('sources', sources, {'FRESH'})]:
        for key, value in entries.items():
            if value['status'] not in healthy:
                alerts[f'{category}:{key}'] = value['status']
    old = (previous or {}).get('alerts', {})
    return {'schema_version': 1, 'checked_at': now.isoformat(), 'simulation_only': True,
            'status': 'ATTENTION' if alerts else 'HEALTHY', 'workflows': actions,
            'outputs': files, 'sources': sources, 'alerts': alerts,
            'new_or_changed_alerts': {k: v for k, v in alerts.items() if old.get(k) != v},
            'recovered_alerts': sorted(set(old) - set(alerts))}


def markdown(report):
    lines = [f"# Research health: {report['status']}", '', f"Checked: {report['checked_at']}",
             '', 'Simulation only. Refresh health is separate from performance or profitability.', '',
             '| Category | Item | Status | Last success / source sessions |', '| --- | --- | --- | --- |']
    for category in ['workflows', 'sources', 'outputs']:
        for name, value in report[category].items():
            detail = value.get('last_successful_run_at') or ', '.join(
                f"{symbol}: {day}" for symbol, day in value.get('source_sessions', {}).items()) or 'Unknown / not applicable'
            lines.append(f"| {category} | {name} | {value['status']} | {detail} |")
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--output', type=Path, default=Path('work/monitoring'))
    parser.add_argument('--actions-json', type=Path, help='Offline normalized workflow evidence')
    parser.add_argument('--previous', type=Path, help='Previous health.json for alert transitions')
    args = parser.parse_args()
    if args.actions_json:
        actions = json.loads(args.actions_json.read_text())
    else:
        try:
            actions = collect_actions(os.environ['GITHUB_REPOSITORY'], os.environ['GH_TOKEN'])
        except (KeyError, OSError, ValueError):
            actions = {name: {'status': 'UNKNOWN_API_ERROR'} for name in OUTPUTS}
    # An incomplete fixture must never silently produce a healthy workflow panel.
    actions = {name: actions.get(name, {'status': 'UNKNOWN'}) for name in OUTPUTS}
    previous = json.loads(args.previous.read_text()) if args.previous else None
    report = build_report(args.root, datetime.now(timezone.utc), actions, previous)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'health.json').write_text(json.dumps(report, indent=2) + '\n')
    (args.output / 'health.md').write_text(markdown(report))
    print(markdown(report))
    return int(report['status'] != 'HEALTHY')


if __name__ == '__main__':
    raise SystemExit(main())
