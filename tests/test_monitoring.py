import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from monitoring.health import (OUTPUTS, build_report, expected_session, file_evidence,
                               source_evidence, workflow_evidence, api_pages, markdown)

NOW = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)


class MonitoringTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, data):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(data)

    def test_completed_sessions_weekend_holiday_and_grace(self):
        self.assertEqual(str(expected_session(NOW, 'stock')), '2026-10-23')
        self.assertEqual(str(expected_session(NOW, 'crypto')), '2026-10-23')
        holiday = datetime(2026, 7, 3, 23, tzinfo=timezone.utc)
        self.assertEqual(str(expected_session(holiday, 'stock')), '2026-07-02')
        before = datetime(2026, 10, 23, 22, tzinfo=timezone.utc)
        self.assertEqual(str(expected_session(before, 'stock')), '2026-10-22')
        self.assertEqual(str(expected_session(before.replace(hour=23), 'stock')), '2026-10-23')

    def test_source_failure_recovery_and_old_csv_not_refreshed(self):
        name = 'paper/latest_signals.csv'
        self.write(name, 'ticker,price_session,close\nAAPL,2026-10-22,1\nMSFT,2026-10-23,2\n')
        result = source_evidence(self.root, name, 'price_session', 'ticker', 'stock', NOW)
        self.assertEqual(result['status'], 'STALE')
        self.assertEqual(result['stale_symbols'], ['AAPL'])
        self.write(name, 'ticker,price_session,close\nAAPL,2026-10-23,1\n')
        self.assertEqual(source_evidence(self.root, name, 'price_session', 'ticker', 'stock', NOW)['status'], 'FRESH')

    def test_legacy_run_date_and_no_data_fail_closed(self):
        for content in ['ticker,date_utc,close,signal\nDOGE-USD,2026-10-24,,NO_DATA\n',
                        'ticker,price_session,close,signal\nDOGE-USD,,1,NO_DATA\n']:
            self.write('data.csv', content)
            self.assertEqual(source_evidence(self.root, 'data.csv', 'price_session', 'ticker', 'crypto', NOW)['status'],
                             'UNKNOWN_SOURCE_DATE_OR_INVALID_DATA')

    def test_future_unfinished_and_nonfinite_prices(self):
        for day, price in [('2026-10-24', '1'), ('2026-10-23', 'nan'), ('2026-10-23', '-1')]:
            self.write('data.csv', f'ticker,price_session,close\nDOGE-USD,{day},{price}\n')
            self.assertEqual(source_evidence(self.root, 'data.csv', 'price_session', 'ticker', 'crypto', NOW)['status'], 'INVALID')

    def test_output_missing_empty_invalid_and_hash(self):
        self.assertEqual(file_evidence(self.root, 'x.csv')['status'], 'MISSING')
        self.write('x.csv', 'asset,as_of\n')
        self.assertEqual(file_evidence(self.root, 'x.csv')['status'], 'EMPTY')
        self.write('x.json', '{')
        self.assertEqual(file_evidence(self.root, 'x.json')['status'], 'INVALID')
        self.write('x.csv', 'asset,as_of\nAAPL,2026-10-23\n')
        self.assertEqual(len(file_evidence(self.root, 'x.csv')['sha256']), 64)

    def test_workflow_states_use_immutable_id_and_latest_attempt(self):
        workflow = {'id': 42, 'path': '.github/workflows/paper-trading.yml'}
        self.assertEqual(workflow_evidence(workflow, [])['status'], 'NEVER_RUN')
        self.assertEqual(workflow_evidence(None, [])['status'], 'MISSING_WORKFLOW')
        run = dict(workflow_id=42, id=100, run_number=2, status='completed',
                   conclusion='failure', html_url='https://github.com/run/100', updated_at='2026-10-24T00:00:00Z')
        success = dict(run, id=99, run_number=1, conclusion='success')
        for conclusion, status in [('failure', 'FAILURE'), ('cancelled', 'CANCELLED'), ('success', 'SUCCESS'), ('timed_out', 'TIMED_OUT')]:
            result = workflow_evidence(workflow, [dict(run, conclusion=conclusion), success])
            self.assertEqual(result['status'], status)
            self.assertEqual(result['workflow_id'], 42)
        self.assertEqual(workflow_evidence(workflow, [dict(run, status='in_progress', conclusion=None)])['status'], 'IN_PROGRESS')
        self.assertEqual(workflow_evidence(workflow, [dict(run, workflow_id=7)])['status'], 'NEVER_RUN')
        self.assertEqual(workflow_evidence(workflow, [run, dict(run, run_attempt=2, conclusion='success')])['status'], 'SUCCESS')

    def test_success_never_hides_stale_sources_and_alert_dedup_recovery(self):
        actions = {name: {'status': 'SUCCESS'} for name in OUTPUTS}
        report = build_report(self.root, NOW, actions)
        self.assertEqual(report['status'], 'ATTENTION')
        repeated = build_report(self.root, NOW, actions, report)
        self.assertEqual(repeated['new_or_changed_alerts'], {})
        self.write('results/latest_results.txt', 'historical backtest')
        recovered = build_report(self.root, NOW, actions, report)
        self.assertIn('outputs:results/latest_results.txt', recovered['recovered_alerts'])
        self.assertIn('MISSING', markdown(recovered))
        self.assertEqual(json.loads(json.dumps(recovered))['simulation_only'], True)

    def test_api_pagination(self):
        class Response:
            def __init__(self, data): self.data = data
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return json.dumps({'workflow_runs': self.data}).encode()
        with patch('monitoring.health.urlopen', side_effect=[Response([{}] * 100), Response([{}])]) as mock:
            self.assertEqual(len(api_pages('owner/repo', 'actions/runs?branch=main', 'workflow_runs', 'fixture')), 101)
            self.assertIn('&per_page=100&page=2', mock.call_args.args[0].full_url)


if __name__ == '__main__':
    unittest.main()
