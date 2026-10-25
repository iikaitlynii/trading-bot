"""Read saved research files and Actions metadata; never run trading code."""
import argparse
import csv
import hashlib
import json
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from pandas.tseries.holiday import (
    AbstractHolidayCalendar, Holiday, nearest_workday, USMartinLutherKingJr,
    USPresidentsDay, GoodFriday, USMemorialDay, USLaborDay, USThanksgivingDay,
)


def new_year_observance(day):
    # NYSE does not close the preceding Friday when January 1 is Saturday.
    return day + timedelta(days=1) if day.weekday() == 6 else day


class StockHolidays(AbstractHolidayCalendar):
    rules = [Holiday('New Year', month=1, day=1, observance=new_year_observance),
             USMartinLutherKingJr, USPresidentsDay, GoodFriday, USMemorialDay,
             Holiday('Juneteenth', month=6, day=19, start_date='2022-01-01', observance=nearest_workday),
             Holiday('Independence', month=7, day=4, observance=nearest_workday),
             USLaborDay, USThanksgivingDay,
             Holiday('Christmas', month=12, day=25, observance=nearest_workday)]


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
SOURCES = [
    ('paper/latest_signals.csv', 'price_session', 'ticker', 'stock'),
    ('crypto_paper/latest_signals.csv', 'price_session', 'ticker', 'crypto'),
    ('research/stock_history.csv', 'date', 'ticker', 'stock'),
    ('strategy_comparison_results.csv', 'as_of', 'asset', 'mixed'),
]


def expected_session(now, market):
    """Completed UTC crypto day; stock close with conservative 23:00 UTC grace."""
    day = now.date() - timedelta(days=1 if market == 'crypto' or now.hour < 23 else 0)
    if market == 'crypto':
        return day
    holidays = set(StockHolidays().holidays(start=day - timedelta(days=15), end=day).date)
    while day.weekday() >= 5 or day in holidays:
        day -= timedelta(days=1)
    return day


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


def source_evidence(root, path, column, symbol, market, now):
    result = file_evidence(root, path)
    if result['status'] != 'PRESENT':
        return result
    try:
        with (root / path).open(newline='', encoding='utf-8-sig') as handle:
            rows = list(csv.DictReader(handle))
        latest = {}
        invalid = False
        for row in rows:
            name = row[symbol]
            # Legacy run-date columns are deliberately not a source-date fallback.
            session = datetime.strptime(row[column], '%Y-%m-%d').date()
            kind = 'crypto' if market == 'mixed' and name.endswith('-USD') else market
            kind = 'stock' if kind == 'mixed' else kind
            expected = expected_session(now, kind)
            if session > expected or (kind == 'stock' and session.weekday() > 4):
                invalid = True
            if 'close' in row:
                price = float(row['close'])
                invalid |= not math.isfinite(price) or price <= 0 or row.get('signal') == 'NO_DATA'
            latest[name] = max(latest.get(name, session), session)
        stale = [name for name, day in latest.items() if day < expected_session(
            now, 'crypto' if market == 'crypto' or (market == 'mixed' and name.endswith('-USD')) else 'stock')]
        result.update(status='INVALID' if invalid else 'STALE' if stale else 'FRESH',
                      source_sessions={name: day.isoformat() for name, day in sorted(latest.items())},
                      stale_symbols=sorted(stale))
    except (KeyError, TypeError, ValueError):
        result['status'] = 'UNKNOWN_SOURCE_DATE_OR_INVALID_DATA'
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
    sources = {path: source_evidence(root, path, col, symbol, market, now)
               for path, col, symbol, market in SOURCES}
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
