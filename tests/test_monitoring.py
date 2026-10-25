import ast
import contextlib
import csv
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import monitoring.health as health
from monitoring.health import (OUTPUTS, SOURCES, build_report, expected_session, file_evidence,
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

    def test_completed_sessions_weekend_holiday_and_exact_close(self):
        self.assertEqual(str(expected_session(NOW, 'stock')), '2026-10-23')
        self.assertEqual(str(expected_session(NOW, 'crypto')), '2026-10-23')
        holiday = datetime(2026, 7, 3, 23, tzinfo=timezone.utc)
        self.assertEqual(str(expected_session(holiday, 'stock')), '2026-07-02')
        before = datetime(2026, 10, 23, 19, 59, 59, tzinfo=timezone.utc)
        self.assertEqual(str(expected_session(before, 'stock')), '2026-10-22')
        self.assertEqual(str(expected_session(before.replace(hour=20, minute=0, second=0), 'stock')), '2026-10-23')

    def test_source_failure_recovery_and_old_csv_not_refreshed(self):
        name = 'paper/latest_signals.csv'
        self.write(name, 'ticker,price_session,close\nAAPL,2026-10-22,1\nMSFT,2026-10-23,2\n')
        result = source_evidence(self.root, name, 'price_session', 'ticker', 'stock', NOW,
                                 expected_symbols=('AAPL', 'MSFT'))
        self.assertEqual(result['status'], 'STALE')
        self.assertEqual(result['stale_symbols'], ['AAPL'])
        self.write(name, 'ticker,price_session,close\nAAPL,2026-10-23,1\n')
        self.assertEqual(source_evidence(self.root, name, 'price_session', 'ticker', 'stock', NOW,
                                             expected_symbols=('AAPL',))['status'], 'FRESH')

    def test_legacy_run_date_and_no_data_fail_closed(self):
        for content in ['ticker,date_utc,close,signal\nDOGE-USD,2026-10-24,,NO_DATA\n',
                        'ticker,price_session,close,signal\nDOGE-USD,,1,NO_DATA\n']:
            self.write('data.csv', content)
            self.assertEqual(source_evidence(self.root, 'data.csv', 'price_session', 'ticker', 'crypto', NOW,
                                             expected_symbols=('DOGE-USD',))['status'],
                             'NO_DATA')

    def test_future_unfinished_and_nonfinite_prices(self):
        for day, price in [('2026-10-24', '1'), ('2026-10-23', 'nan'), ('2026-10-23', '-1')]:
            self.write('data.csv', f'ticker,price_session,close\nDOGE-USD,{day},{price}\n')
            self.assertEqual(source_evidence(self.root, 'data.csv', 'price_session', 'ticker', 'crypto', NOW,
                                             expected_symbols=('DOGE-USD',))['status'], 'INVALID')

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

    def source(self, content, *, expected=('AAPL',), now=NOW, market='stock'):
        self.write('fixture.csv', content)
        return source_evidence(self.root, 'fixture.csv', 'price_session', 'ticker', market,
                               now, expected_symbols=expected)

    def test_missing_close_column_and_blank_close_are_invalid(self):
        for content in ['ticker,price_session\nAAPL,2026-10-23\n',
                        'ticker,price_session,close\nAAPL,2026-10-23,\n',
                        'ticker,price_session,close\nAAPL,2026-10-23\n']:
            with self.subTest(content=content):
                result = self.source(content)
                self.assertEqual(result['status'], 'INVALID')
                self.assertNotIn('AAPL', result['source_sessions'])

    def test_blank_missing_or_whitespace_symbols_cannot_be_fresh(self):
        for symbol in ['', ' ', ' AAPL', 'AAPL ']:
            with self.subTest(symbol=symbol):
                result = self.source(f'ticker,price_session,close\n{symbol},2026-10-23,100\n')
                self.assertEqual(result['status'], 'INVALID')
                self.assertIn('INVALID_SYMBOL', result['issues'])
                self.assertEqual(result['missing_symbols'], ['AAPL'])
        self.assertEqual(self.source('price_session,close\n2026-10-23,100\n')['status'], 'INVALID')

    def test_conflicting_and_identical_duplicate_records_rejected(self):
        for day, value in [('2026-10-23', '200'), ('2026-10-23', '100'), ('2026-10-22', '99')]:
            with self.subTest(day=day, value=value):
                result = self.source('ticker,price_session,close\nAAPL,2026-10-23,100\n'
                                     f'AAPL,{day},{value}\n')
                self.assertEqual(result['status'], 'INVALID')
                self.assertIn('DUPLICATE_RECORD', result['issues'])

    def test_history_allows_distinct_sessions_but_rejects_conflicting_keys(self):
        name = 'research/stock_history.csv'
        for extra, status in [('', 'FRESH'), ('AAPL,2026-10-23,101\n', 'INVALID')]:
            self.write(name, 'ticker,date,close\nAAPL,2026-10-22,99\nAAPL,2026-10-23,100\n' + extra)
            result = source_evidence(self.root, name, 'date', 'ticker', 'stock', NOW,
                                     expected_symbols=('AAPL',))
            self.assertEqual(result['status'], status)

    def test_omitted_and_unexpected_assets_in_each_production_contract(self):
        self.populate_healthy_outputs()
        for path, spec in SOURCES.items():
            with self.subTest(path=path):
                original = (self.root / path).read_text()
                lines = original.splitlines(keepends=True)
                (self.root / path).write_text(''.join(lines[:-1]))
                report = build_report(self.root, NOW, self.successful_actions())
                self.assertEqual(report['sources'][path]['status'], 'INVALID')
                self.assertEqual(report['sources'][path]['missing_symbols'], [spec.expected_symbols[-1]])
                (self.root / path).write_text(original)
        result = self.source('ticker,price_session,close\nOTHER,2026-10-23,1\n')
        self.assertEqual(result['status'], 'INVALID')
        self.assertEqual(result['unexpected_symbols'], ['OTHER'])

    def test_unknown_requested_universe_cannot_claim_fresh(self):
        self.write('unknown.csv', 'ticker,price_session,close\nAAPL,2026-10-23,100\n')
        result = source_evidence(self.root, 'unknown.csv', 'price_session', 'ticker', 'stock', NOW)
        self.assertEqual(result['status'], 'UNKNOWN_COVERAGE')

    def test_no_data_is_unavailable_with_or_without_date_price_or_close_column(self):
        for content in [
                'ticker,price_session,signal\nAAPL,2026-10-23,NO_DATA\n',
                'ticker,price_session,close,signal\nAAPL,,,NO_DATA\n',
                'ticker,price_session,close,signal\nAAPL,2026-10-23,,NO_DATA\n',
                'ticker,price_session,close,signal\nAAPL,2026-10-23,100,NO_DATA\n']:
            with self.subTest(content=content):
                result = self.source(content)
                self.assertEqual(result['status'], 'NO_DATA')
                self.assertEqual(result['source_sessions'], {})
                self.assertEqual(result['no_data_symbols'], ['AAPL'])
        recovered = self.source('ticker,price_session,close,signal\nAAPL,2026-10-23,100,BULLISH\n')
        self.assertEqual(recovered['status'], 'FRESH')

    def test_malformed_row_and_duplicate_headers_fail_closed(self):
        for content in ['ticker,price_session,close,signal\nAAPL,2026-10-23,100\n',
                        'ticker,price_session,close\nAAPL,2026-10-23,100,extra\n',
                        'ticker,price_session,close,close\nAAPL,2026-10-23,100,200\n']:
            with self.subTest(content=content):
                self.assertEqual(self.source(content)['status'], 'INVALID')

    def test_mourning_closure_uses_january_8_until_january_10_close(self):
        for instant, expected in [('2025-01-09T23:00:00+00:00', '2025-01-08'),
                                  ('2025-01-10T20:59:59+00:00', '2025-01-08'),
                                  ('2025-01-10T21:00:00+00:00', '2025-01-10')]:
            now = datetime.fromisoformat(instant)
            self.assertEqual(expected_session(now, 'stock').isoformat(), expected)
            result = self.source(f'ticker,price_session,close\nAAPL,{expected},100\n', now=now)
            self.assertEqual(result['status'], 'FRESH')
        invalid = self.source('ticker,price_session,close\nAAPL,2025-01-09,100\n',
                              now=datetime.fromisoformat('2025-01-10T22:00:00+00:00'))
        self.assertEqual(invalid['status'], 'INVALID')

    def test_shared_calendar_early_close_dst_and_unsupported_year(self):
        for instant, expected in [('2026-11-27T17:59:59+00:00', '2026-11-25'),
                                  ('2026-11-27T18:00:00+00:00', '2026-11-27'),
                                  ('2026-03-09T19:59:59+00:00', '2026-03-06'),
                                  ('2026-03-09T20:00:00+00:00', '2026-03-09')]:
            self.assertEqual(expected_session(datetime.fromisoformat(instant), 'stock').isoformat(), expected)
        result = self.source('ticker,price_session,close\nAAPL,2028-01-03,100\n',
                             now=datetime.fromisoformat('2028-01-04T22:00:00+00:00'))
        self.assertEqual(result['status'], 'UNKNOWN_SOURCE_DATE_OR_INVALID_DATA')

    @staticmethod
    def successful_actions():
        return {name: {'status': 'SUCCESS'} for name in OUTPUTS}

    def populate_healthy_outputs(self):
        for paths in OUTPUTS.values():
            for path in paths:
                self.write(path, '{}\n' if path.endswith('.json') else
                           'item\nfixture\n' if path.endswith('.csv') else 'synthetic fixture\n')
        for path, spec in SOURCES.items():
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow([*spec.symbol_columns, spec.date_column, spec.value_column])
            for symbol in spec.expected_symbols:
                writer.writerow([*symbol.split('/'), '2026-10-23', 100])
            self.write(path, buf.getvalue())

    def test_healthy_fixture_is_healthy_and_missing_workflow_is_unknown(self):
        self.populate_healthy_outputs()
        report = build_report(self.root, NOW, self.successful_actions())
        self.assertEqual(report['status'], 'HEALTHY')
        self.assertEqual(report['alerts'], {})
        report = build_report(self.root, NOW, {})
        self.assertEqual(report['status'], 'ATTENTION')
        self.assertEqual({v['status'] for v in report['workflows'].values()}, {'UNKNOWN'})

    def run_workflow_cli(self):
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None): return NOW
        evidence = self.root / 'actions.json'
        evidence.write_text(json.dumps(self.successful_actions()))
        args = ['monitoring.health', '--root', str(self.root), '--output', str(self.root / 'evidence'),
                '--actions-json', str(evidence)]
        with patch.object(sys, 'argv', args), patch.object(health, 'datetime', Clock), contextlib.redirect_stdout(io.StringIO()):
            code = health.main()
        report = json.loads((self.root / 'evidence/health.json').read_text())
        self.assertIn(report['status'], (self.root / 'evidence/health.md').read_text())
        return code, report

    def test_workflow_cli_missing_output_fails_and_recovery_passes(self):
        self.populate_healthy_outputs()
        self.assertEqual(self.run_workflow_cli()[0], 0)
        (self.root / 'research_lab/report.txt').unlink()
        code, report = self.run_workflow_cli()
        self.assertEqual(code, 1)
        self.assertEqual(report['alerts']['outputs:research_lab/report.txt'], 'MISSING')
        self.write('research_lab/report.txt', 'synthetic fixture\n')
        self.assertEqual(self.run_workflow_cli()[0], 0)

    def test_workflow_cli_stale_research_fails_despite_successful_actions(self):
        for path in ['strategy_comparison_results.csv', 'research_lab/latest_shadow_results.csv',
                     'research_lab/forward/performance.csv']:
            with self.subTest(path=path):
                self.populate_healthy_outputs()
                target = self.root / path
                target.write_text(target.read_text().replace('2026-10-23', '2026-10-22'))
                code, report = self.run_workflow_cli()
                self.assertEqual(code, 1)
                self.assertEqual(report['alerts']['sources:' + path], 'STALE')
                self.assertEqual(report['workflows']['paper-trading.yml']['status'], 'SUCCESS')

    def test_all_missing_comparison_and_empty_research_cannot_succeed(self):
        for content in ['', 'asset,as_of,sessions\n']:
            self.populate_healthy_outputs()
            self.write('strategy_comparison_results.csv', content)
            self.assertEqual(self.run_workflow_cli()[0], 1)
        self.populate_healthy_outputs()
        # A previous run's complete comparison still cannot pass a new clock.
        p = self.root / 'strategy_comparison_results.csv'
        p.write_text(p.read_text().replace('2026-10-23', '2026-10-22'))
        self.assertEqual(self.run_workflow_cli()[1]['sources']['strategy_comparison_results.csv']['status'], 'STALE')

    def test_requested_universes_match_producers_without_importing_them(self):
        root = Path(__file__).resolve().parents[1]
        def literal(filename, name):
            tree = ast.parse((root / filename).read_text())
            return next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == name for t in node.targets))
        for filename, constant, path in [
                ('paper_trader.py', 'TICKERS', 'paper/latest_signals.csv'),
                ('crypto_paper_trader.py', 'TICKERS', 'crypto_paper/latest_signals.csv'),
                ('stock_history_research.py', 'SYMBOLS', 'research/stock_history.csv')]:
            self.assertEqual(set(literal(filename, constant)), set(SOURCES[path].expected_symbols))
        self.assertEqual(set(literal('strategy_comparison.py', 'STOCKS') + literal('strategy_comparison.py', 'MEMECOINS')),
                         set(SOURCES['strategy_comparison_results.csv'].expected_symbols))
        self.assertEqual({f"{u}/{v['name']}" for u in literal('research_lab.py', 'UNIVERSES')
                          for v in literal('research_lab.py', 'VARIANTS')},
                         set(SOURCES['research_lab/latest_shadow_results.csv'].expected_symbols))
        self.assertEqual({v['name'] for v in literal('forward_shadow.py', 'VARIANTS')},
                         set(SOURCES['research_lab/forward/performance.csv'].expected_symbols))

    def test_ci_covers_monitoring_sources_and_failure_evidence_is_always_published(self):
        root = Path(__file__).resolve().parents[1]
        ci = (root / '.github/workflows/agent-ci.yml').read_text()
        self.assertIn("- 'monitoring/**'", ci)
        self.assertIn("- 'data_contracts/**'", ci)
        self.assertIn("- '.github/workflows/research-health.yml'", ci)
        compile_step = next(line for line in ci.splitlines() if 'python -m compileall' in line)
        self.assertIn('monitoring', compile_step)
        self.assertIn('data_contracts', compile_step)
        workflow = (root / '.github/workflows/research-health.yml').read_text()
        self.assertIn('run: python -m monitoring.health', workflow)
        self.assertNotIn('continue-on-error', workflow)
        self.assertNotIn('|| true', workflow)
        self.assertEqual(workflow.count('if: always()'), 2)
        self.assertIn('if-no-files-found: error', workflow)

    def test_stock_producer_emits_real_source_session_and_monitor_accepts_it(self):
        import numpy as np
        import pandas as pd
        import paper_trader as stock
        from test_market_data_quality import FixedClock
        # Patch all paths; no network or writes to checked-in paper records.
        for path in ['paper/state.json', 'paper/journal.csv', 'paper/performance.csv', 'paper/latest_signals.csv']:
            (self.root / path).parent.mkdir(parents=True, exist_ok=True)
        history = pd.Series(np.linspace(10, 30, 220), index=pd.bdate_range(end='2026-01-14', periods=220))
        with contextlib.ExitStack() as stack:
            for attr, filename in [('STATE_FILE', 'paper/state.json'), ('JOURNAL_FILE', 'paper/journal.csv'),
                                   ('PERFORMANCE_FILE', 'paper/performance.csv'), ('SIGNALS_FILE', 'paper/latest_signals.csv')]:
                stack.enter_context(patch.object(stock, attr, str(self.root / filename)))
            stack.enter_context(patch.object(stock, 'datetime', FixedClock))
            stack.enter_context(patch.object(stock, 'get_data', return_value=history))
            stack.enter_context(patch.object(stock.yf, 'download', side_effect=AssertionError('Network forbidden')))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            # The producer creates a relative paper directory; contain it in the fixture.
            stack.enter_context(contextlib.chdir(self.root))
            stock.main()
        with (self.root / 'paper/latest_signals.csv').open() as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual({row['price_session'] for row in rows}, {'2026-01-14'})
        self.assertTrue(all(row['date_utc'] == row['price_session'] for row in rows))
        result = source_evidence(self.root, 'paper/latest_signals.csv', 'price_session', 'ticker', 'stock',
                                 datetime(2026, 1, 14, 23, 30, tzinfo=timezone.utc))
        self.assertEqual(result['status'], 'FRESH')

    def test_legacy_stock_run_date_never_substitutes_for_source_session(self):
        self.write('paper/latest_signals.csv', 'ticker,date_utc,close\nAAPL,2026-10-23,100\n')
        result = source_evidence(self.root, 'paper/latest_signals.csv', 'price_session', 'ticker',
                                 'stock', NOW, expected_symbols=('AAPL',))
        self.assertEqual(result['status'], 'INVALID')
        self.assertEqual(result['source_sessions'], {})

    def test_mixed_comparison_uses_crypto_weekends_and_stale_members(self):
        now = datetime.fromisoformat('2026-10-25T00:00:00+00:00')
        name = 'strategy_comparison_results.csv'
        for crypto_day, status in [('2026-10-23', 'STALE'), ('2026-10-24', 'FRESH')]:
            self.write(name, 'asset,as_of,sessions\nAAPL,2026-10-23,120\n'
                       f'DOGE-USD,{crypto_day},120\n')
            result = source_evidence(self.root, name, 'as_of', 'asset', 'mixed', now,
                                     expected_symbols=('AAPL', 'DOGE-USD'))
            self.assertEqual(result['status'], status)

    def test_workflow_api_failure_never_reports_success(self):
        self.populate_healthy_outputs()
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None): return NOW
        args = ['monitoring.health', '--root', str(self.root), '--output', str(self.root / 'api-evidence')]
        with patch.object(sys, 'argv', args), patch.object(health, 'datetime', Clock), \
                patch.dict('os.environ', {'GITHUB_REPOSITORY': 'owner/repo', 'GH_TOKEN': 'fixture'}), \
                patch.object(health, 'collect_actions', side_effect=OSError('offline fixture')), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(health.main(), 1)
        report = json.loads((self.root / 'api-evidence/health.json').read_text())
        self.assertEqual({v['status'] for v in report['workflows'].values()}, {'UNKNOWN_API_ERROR'})


if __name__ == '__main__':
    unittest.main()
