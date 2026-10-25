"""Deterministic reporting fixtures; never download prices or run traders."""
import csv
import os
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import performance_reports as reports
import paper_report


class PerformanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'paper').mkdir()
        (self.root / 'research').mkdir()
        self.write('paper/performance.csv', 'date_utc,paper_value,cash', [
            ['2026-01-01', 10000, 9000], ['2026-01-31', 10100, 9600], ['2026-02-10', 10200, 9600]])
        self.write('paper/journal.csv', 'date_utc,ticker,action,price,shares', [
            ['2026-01-01', 'AAPL', 'SIM_BUY', 100, 10], ['2026-01-31', 'AAPL', 'SIM_SELL', 120, 5]])
        self.state = {'last_run_date': '2026-02-10', 'cash': 9600, 'positions': {'AAPL': {'shares': 5, 'entry_price': 100}}}
        self.save_state()
        self.write('research/stock_history.csv', 'date,ticker,close', [
            [d, symbol, p] for symbol in reports.ACCOUNTS['stocks'][3]
            for d, p in [('2026-01-01', 100), ('2026-02-10', 110)]])

    def write(self, path, headers, rows):
        with (self.root / path).open('w', newline='') as f:
            w = csv.writer(f); w.writerow(headers.split(',')); w.writerows(rows)

    def save_state(self):
        (self.root / 'paper/state.json').write_text(json.dumps(self.state))

    def build(self):
        return reports.build_account(self.root, 'stocks', '2026-02-11')

    def test_fifo_total_and_unrealized_reconcile(self):
        m = self.build()['metrics']
        self.assertEqual(m['realized_pnl'], 100)
        self.assertEqual(m['unrealized_pnl'], 100)
        self.assertEqual(m['total_portfolio_change'], 200)
        self.assertEqual(m['unreconciled_change'], 0)
        self.assertAlmostEqual(m['total_return_pct'], 2)
        self.assertEqual(m['cash_return_pct'], 0)

    def test_fifo_multiple_lots_and_partial_sale(self):
        warnings = []
        rows = [{'date_utc':'2026-01-01', 'ticker':'X', 'action':a, 'price':p, 'shares':q}
                for a,p,q in [('SIM_BUY',10,2),('SIM_BUY',20,3),('SIM_SELL',30,4)]]
        result = reports.trade_breakdown(rows,'shares','2026-02-10',100,warnings)
        self.assertEqual(result['realized'],60)
        self.assertEqual(sum(q*p for q,p in result['lots']['X']),20)

    def test_benchmark_exact_dates_and_percentage_point_excess(self):
        r = self.build()
        self.assertAlmostEqual(r['benchmark']['return_pct'], 10)
        self.assertAlmostEqual(r['metrics']['excess_vs_buy_hold_pct'], -8)

    def test_monthly_uses_previous_month_end_and_discloses_partial(self):
        months = self.build()['monthly']
        self.assertEqual([m['portfolio_change'] for m in months], [100,100])
        self.assertAlmostEqual(months[1]['return_pct'], 100/101)
        self.assertEqual(months[0]['coverage'], 'partial launch month')
        self.assertEqual(months[1]['coverage'], 'month to date')

    def test_duplicate_date_excludes_all_ambiguous_rows(self):
        warnings = []
        rows = [{'date_utc':d,'paper_value':v,'cash':0} for d,v in [('2026-02-01',10),('2026-01-01',10),('2026-01-01',20)]]
        clean = reports.valuations(rows,warnings,'2026-02-10')
        self.assertEqual([r['date_utc'] for r in clean], ['2026-02-01'])
        self.assertTrue(any('duplicate' in w for w in warnings))

    def test_missing_and_duplicate_benchmark_endpoint_unavailable(self):
        for rows in ([], [{'date':'2026-01-01','ticker':'X','close':10}]*2):
            warnings = []
            self.assertIsNone(reports.benchmark(rows, ['X'],'2026-01-01','2026-01-02',warnings))
            self.assertTrue(warnings)

    def test_bad_journal_never_reports_partial_realized(self):
        for action in ['SIM_SELL','UNKNOWN']:
            self.write('paper/journal.csv', 'date_utc,ticker,action,price,shares', [['2026-01-01','AAPL',action,100,100]])
            m = self.build()['metrics']
            self.assertIsNone(m['realized_pnl']); self.assertIsNone(m['unrealized_pnl'])

    def test_cash_quantity_or_date_mismatch_suppresses_unrealized(self):
        for key,value in [('cash',9500),('last_run_date','2026-02-09'),('positions',{})]:
            original = self.state.copy(); self.state[key] = value; self.save_state()
            m = self.build()['metrics']
            self.assertIsNone(m['unrealized_pnl'])
            self.assertEqual(m['unreconciled_change'],100)
            self.state = original

    def test_missing_journal_and_state_keep_total_available(self):
        (self.root / 'paper/journal.csv').unlink(); (self.root / 'paper/state.json').unlink()
        m = self.build()['metrics']
        self.assertEqual(m['total_portfolio_change'],200)
        self.assertIsNone(m['realized_pnl']); self.assertIsNone(m['unrealized_pnl'])

    def test_invalid_blank_nonfinite_future_values(self):
        warnings = []
        rows = [{'date_utc':d,'paper_value':v,'cash':0} for d,v in [('2026-01-01',''),('2026-01-02','nan'),('2026-01-03','inf'),('2026-01-04',-1),('2027-01-01',100)]]
        self.assertEqual(reports.valuations(rows,warnings,'2026-02-10'),[])
        self.assertEqual(len(warnings),5)

    def test_drawdown_includes_launch_capital(self):
        self.write('paper/performance.csv','date_utc,paper_value,cash',[['2026-01-01',9000,9000],['2026-02-10',9500,9000]])
        self.assertEqual(self.build()['metrics']['max_drawdown_pct'],10)

    def test_comparison_period_does_not_mix_launch_and_first_observation(self):
        self.write('paper/performance.csv','date_utc,paper_value,cash',[['2026-01-01',9000,9000],['2026-02-10',9900,9000]])
        m = self.build()['metrics']
        self.assertAlmostEqual(m['total_return_pct'],-1)
        self.assertAlmostEqual(m['comparison_return_pct'],10)
        self.assertAlmostEqual(m['excess_vs_buy_hold_pct'],0)

    def test_csv_round_trip_and_missing_account_outputs(self):
        reports.generate(self.root,'2026-02-11')
        for account in ('stocks','crypto'):
            data = json.loads((self.root / f'reports/{account}.json').read_text())
            self.assertEqual(data['schema_version'],1)
            for kind in ('daily','monthly','summary'):
                with (self.root / f'reports/{account}_{kind}.csv').open() as f:
                    self.assertTrue(next(csv.reader(f)))
        self.assertTrue(data['warnings'])
        self.assertEqual(data['metrics'],{})

    def test_crypto_units_reconcile(self):
        (self.root/'paper').rename(self.root/'crypto_paper')
        self.write('crypto_paper/journal.csv','date_utc,ticker,action,price,units',[
            ['2026-01-01','AAPL','SIM_BUY',100,10],['2026-01-31','AAPL','SIM_SELL',120,5]])
        state = self.state.copy(); state['cash'] = 4600; state['positions'] = {'AAPL':{'units':5}}
        (self.root/'crypto_paper/state.json').write_text(json.dumps(state))
        self.write('crypto_paper/performance.csv','date_utc,paper_value,cash',[['2026-01-01',5000,4000],['2026-02-10',5200,4600]])
        m=reports.build_account(self.root,'crypto','2026-02-11')['metrics']
        self.assertEqual(m['realized_pnl'],100); self.assertEqual(m['unrealized_pnl'],100)

    def test_missing_journal_columns_are_not_zero_realized(self):
        self.write('paper/journal.csv', 'wrong,header', [])
        self.assertIsNone(self.build()['metrics']['realized_pnl'])

    def test_empty_valid_journal_and_flat_cash_account(self):
        self.write('paper/journal.csv','date_utc,ticker,action,price,shares',[])
        self.write('paper/performance.csv','date_utc,paper_value,cash',[['2026-02-10',10000,10000]])
        self.state.update(cash=10000,positions={}); self.save_state()
        m=self.build()['metrics']
        self.assertEqual(m['realized_pnl'],0); self.assertEqual(m['unrealized_pnl'],0)

    def test_journal_out_of_order_or_ahead_of_equity_is_unavailable(self):
        for dates in [('2026-02-01','2026-01-01'),('2026-01-01','2026-02-12')]:
            self.write('paper/journal.csv','date_utc,ticker,action,price,shares',[
                [dates[0],'AAPL','SIM_BUY',100,10],[dates[1],'AAPL','SIM_SELL',120,5]])
            self.assertIsNone(self.build()['metrics']['realized_pnl'])

    def test_no_valuation_history_is_explicitly_unavailable(self):
        (self.root/'paper/performance.csv').unlink()
        r=self.build()
        self.assertEqual(r['metrics'],{}); self.assertTrue(r['warnings'])

    def test_legacy_health_report_uses_shared_calculations(self):
        previous = Path.cwd()
        try:
            os.chdir(self.root)
            text = paper_report.build_report()
        finally:
            os.chdir(previous)
        self.assertIn('realized_pnl: 100.0', text)
        self.assertIn('unrealized_pnl: 100.0', text)
        self.assertNotIn('unrealized/other', text)
        self.assertIn('Simulation only', text)

    def test_dashboard_runtime(self):
        subprocess.run(['node', 'tests/performance_dashboard_test.js'],check=True,cwd=Path(__file__).resolve().parents[1])


if __name__ == '__main__':
    unittest.main()
