"""Deterministic, offline held-out protocol regression checks."""
import copy
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import strategy_comparison as rules
from research.validation import evaluate as v
from research.validation.make_fixture import create


class ValidationProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        create(self.root)
        self.path = self.root/'protocol.json'
        self.cfg = json.loads(self.path.read_text())
        self.no_download = patch.object(rules.yf, 'download', side_effect=AssertionError('offline only'))
        self.no_download.start()
        self.addCleanup(self.no_download.stop)

    def save(self, cfg):
        self.path.write_bytes(v.encoded(cfg))

    def test_repeatability_and_no_mutation(self):
        before = {p.name:p.read_bytes() for p in self.root.iterdir()}
        a = v.encoded(v.evaluate(self.path))
        self.assertEqual(a, v.encoded(v.evaluate(self.path)))
        self.assertEqual(before, {p.name:p.read_bytes() for p in self.root.iterdir()})
        result = json.loads(a)
        self.assertEqual(len(result['results']), 8*4*3)
        self.assertEqual(result['cap_impact']['status'], 'unavailable')
        self.assertIn('unavailable', result['historical_status'])

    def test_exact_existing_rule_parity(self):
        cfg, df, _ = v.load_inputs(self.path)
        for asset in v.UNIVERSE:
            close = df[asset]
            reference = rules.calculate(asset, close)
            for name, exposure in v.exposures(asset, close).items():
                actual, _ = v.ledger(close, exposure.iloc[-rules.WINDOW:], 10, 10)
                for key in ('net_return_pct', 'max_drawdown_pct'):
                    refkey = 'return_pct' if key == 'net_return_pct' else key
                    self.assertEqual(round(actual[key], 2), reference[name+'_'+refkey])
                self.assertEqual(actual['turnover'], reference[name+'_position_changes'])

    def test_cost_ledger_entry_exit_reentry_and_valuation(self):
        dates = pd.date_range('2020-01-01', periods=5)
        close = pd.Series([100.,110.,99.,99.,108.9], index=dates)
        held = pd.Series([1.,0.,1.,1.], index=dates[1:])
        summary, daily = v.ledger(close, held, 10, 20)
        # Scalar hand accounting: +10%-0.3%, exit -0.3%, reentry -0.3%, +10%.
        expected = 1.097 * .997 * .997 * 1.1
        self.assertAlmostEqual(summary['net_return_pct'], (expected-1)*100)
        self.assertEqual(summary['turnover'], 3)
        self.assertAlmostEqual(daily.fee_return.sum(), .003)
        self.assertAlmostEqual(daily.slippage_return.sum(), .006)
        flat = pd.Series(100., index=dates)
        bh, _ = v.ledger(flat, held*0+1, 10, 10)
        cash, _ = v.ledger(flat, held*0, 10, 10)
        self.assertAlmostEqual(bh['net_return_pct'], -.2)
        self.assertAlmostEqual(bh['max_drawdown_pct'], -.2)
        self.assertEqual(cash['net_return_pct'], 0)

    def test_future_shock_cannot_select_rules_or_earn_own_return(self):
        _, df, _ = v.load_inputs(self.path)
        close = df.AAPL.copy()
        original = v.exposures('AAPL', close)
        close.iloc[-1] *= 100
        pd.testing.assert_frame_equal(original, v.exposures('AAPL', close))
        first = v.evaluate(self.path)
        # Mutation demonstrates the protocol detects an accidentally unlagged signal.
        real = v.exposures
        def leaking(asset, series):
            signal = real(asset, series)
            signal['momentum'] = (series.shift(-1) > series).astype(float)
            return signal
        with patch.object(v, 'exposures', side_effect=leaking):
            with self.assertRaises(AssertionError):
                v.evaluate(self.path)
        self.assertEqual(first['assumptions']['selection'].split(':')[0], 'none')

    def test_reject_invalid_frozen_contracts(self):
        mutations = [
            lambda c:c.update(rule_sha256='bad'),
            lambda c:c.update(evaluator_sha256='bad'),
            lambda c:c.update(dataset_sha256='bad'),
            lambda c:c.update(evidence='historical'),
            lambda c:c.update(universe=['AAPL']),
            lambda c:c.update(fee_bps=-1),
            lambda c:c.update(slippage_bps=float('inf')),
            lambda c:c['periods'].update(selection=c['periods']['train']),
            lambda c:c['periods'].update(evaluation=['2030-01-01','2030-02-01']),
            lambda c:c['expected_sessions'].pop(50),
            lambda c:c.update(source=''),
        ]
        for mutate in mutations:
            cfg = copy.deepcopy(self.cfg)
            mutate(cfg)
            # Use default encoder to exercise rejection of nonfinite input.
            self.path.write_text(json.dumps(cfg))
            with self.subTest(config=cfg), self.assertRaises(ValueError):
                v.load_inputs(self.path)

    def test_missing_price_is_rejected_even_with_updated_hash(self):
        data_path = self.root/'synthetic.csv'
        df = pd.read_csv(data_path)
        df.loc[300,'AAPL'] = np.nan
        df.to_csv(data_path,index=False)
        self.cfg['dataset_sha256'] = v.digest(data_path.read_bytes())
        self.save(self.cfg)
        with self.assertRaisesRegex(ValueError, 'finite'):
            v.load_inputs(self.path)

    def test_relabelled_synthetic_is_never_historical(self):
        # A caller controls all these assertions; none verifies the provider.
        for acceptance in (None, False, True, 'reviewed',
                           {'verified': True, 'review_url': 'https://github.com/example/review'}):
            cfg = copy.deepcopy(self.cfg)
            cfg.update(evidence='historical', snapshot_acceptance=acceptance,
                       source='https://query1.finance.yahoo.com/v8/finance/chart/AAPL',
                       retrieved_at='2026-10-24T22:00:00+00:00',
                       adjustment_basis='adjusted_close', session_convention='XNYS regular session')
            self.save(cfg)
            with self.subTest(acceptance=acceptance), self.assertRaisesRegex(
                    ValueError, 'historical evaluation unsupported'):
                v.evaluate(self.path)

    def test_claimed_contract_and_hashes_do_not_verify_history(self):
        cfg = copy.deepcopy(self.cfg)
        # Contract-shaped metadata, rehashed payloads and a schema version are
        # integrity claims, not independently verified origin or an adapter.
        snapshot = dict(schema_version=1, calendar_version='utc-daily-v1',
                        provenance=dict(classification='historical research',
                                        source_url='https://query1.finance.yahoo.com/v8/finance/chart/BTC-USD'))
        cfg.update(evidence='historical', snapshot_acceptance=True,
                   provenance=snapshot, dataset_contract=dict(schema_version=1,
                       verified=True, sha256=v.digest(v.encoded(snapshot))))
        self.save(cfg)
        with self.assertRaisesRegex(ValueError, 'historical evaluation unsupported'):
            v.evaluate(self.path)

    def test_historical_block_precedes_price_io_and_calculation(self):
        self.save(dict(evidence='historical', snapshot_acceptance=True,
                       dataset='does-not-exist.csv'))
        with patch.object(v, 'exposures', side_effect=AssertionError('must not calculate')):
            with self.assertRaisesRegex(ValueError, 'historical evaluation unsupported'):
                v.evaluate(self.path)

    def test_synthetic_acceptance_flag_is_not_a_trust_mechanism(self):
        self.cfg['snapshot_acceptance'] = True
        self.save(self.cfg)
        with self.assertRaisesRegex(ValueError, 'snapshot_acceptance is unsupported'):
            v.evaluate(self.path)

    def test_historical_cli_fails_without_creating_or_replacing_reports(self):
        cfg = copy.deepcopy(self.cfg)
        cfg.update(evidence='historical', snapshot_acceptance=True)
        self.save(cfg)
        destination = self.root/'report.json'
        for existing in (False, True):
            if existing:
                destination.write_bytes(b'previous synthetic evidence\n')
            result = subprocess.run([sys.executable, '-m', 'research.validation.evaluate',
                                     str(self.path), '--output', str(destination)],
                                    cwd=v.ROOT, capture_output=True, text=True)
            with self.subTest(existing=existing):
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('historical evaluation unsupported', result.stderr)
                if existing:
                    self.assertEqual(destination.read_bytes(), b'previous synthetic evidence\n')
                else:
                    self.assertFalse(destination.exists())

    def test_periods_start_fresh_and_use_only_preceding_close_return(self):
        report = v.evaluate(self.path)
        for period, (start, end) in self.cfg['periods'].items():
            cash = [r for r in report['daily'] if r['period']==period and r['signal']=='cash']
            self.assertTrue(all(r['net_return']==0 for r in cash))
            buys = [r for r in report['daily'] if r['period']==period and r['signal']=='buy_hold' and r['asset']=='AAPL']
            self.assertEqual(buys[0]['date'], start)
            self.assertEqual(buys[-1]['date'], end)
            self.assertEqual(buys[0]['turnover'], 1)
            self.assertEqual(sum(r['turnover'] for r in buys), 1)


if __name__ == '__main__':
    unittest.main()
