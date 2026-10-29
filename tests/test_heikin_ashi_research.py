"""Synthetic unit cases are separate from the frozen genuine historical run."""
import json
import copy
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

import heikin_ashi_research as r


def fixture():
    idx = pd.date_range('2026-01-01', periods=240, freq='min', tz='UTC')
    return pd.DataFrame(dict(open=100., high=101., low=99., close=100., volume=10.), index=idx)


class HeikinAshiTests(unittest.TestCase):
    def manifest(self):
        return json.loads((r.ROOT/'manifest.json').read_text())

    def assert_invalid_periods(self, manifest):
        # No source file is needed: the full split must fail before data/simulation.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'manifest.json').write_text(json.dumps(manifest))
            output = root/'temporary-results.json'
            output.write_text('existing output must survive rejection')
            with patch.object(r, 'simulate') as simulate:
                with self.assertRaises(ValueError):
                    r.run(root=root, output_path=output)
                simulate.assert_not_called()
            self.assertEqual(output.read_text(), 'existing output must survive rejection')

    def test_rejects_duplicate_period_roles(self):
        manifest = self.manifest()
        manifest['periods'][2]['name'] = 'validation'
        self.assert_invalid_periods(manifest)

    def test_rejects_missing_period_roles(self):
        for index in range(3):
            with self.subTest(missing=index):
                manifest = self.manifest()
                del manifest['periods'][index]
                self.assert_invalid_periods(manifest)

    def test_rejects_unknown_period_roles(self):
        manifest = self.manifest()
        manifest['periods'][2]['name'] = 'test'
        self.assert_invalid_periods(manifest)

    def test_rejects_reordered_period_roles(self):
        manifest = self.manifest()
        manifest['periods'].reverse()
        self.assert_invalid_periods(manifest)

    def test_rejects_overlapping_periods(self):
        manifest = self.manifest()
        # Invalid final period must block simulations of the earlier valid days.
        manifest['periods'][2]['start'] = '2026-10-20T23:59:00Z'
        self.assert_invalid_periods(manifest)

    def test_rejects_duplicated_period_windows(self):
        manifest = self.manifest()
        manifest['periods'][2].update({key: manifest['periods'][1][key]
                                     for key in ('start', 'end')})
        self.assert_invalid_periods(manifest)
        manifest = self.manifest()
        manifest['periods'].append(copy.deepcopy(manifest['periods'][2]))
        self.assert_invalid_periods(manifest)

    def test_rejects_chronologically_reordered_windows(self):
        manifest = self.manifest()
        # Keep roles ordered, exchange the validation and holdout dates.
        left, right = manifest['periods'][1:]
        for key in ('start', 'end'):
            left[key], right[key] = right[key], left[key]
        self.assert_invalid_periods(manifest)

    def test_rejects_invalid_period_clocks_before_simulation(self):
        for start, end in [('2026-10-22T00:00:00Z', '2026-10-21T00:00:00Z'),
                           ('2026-10-21T00:00:00Z', '2026-10-21T00:00:00Z'),
                           ('2026-10-21T00:00:01Z', '2026-10-22T00:00:00Z'),
                           ('2026-10-21T00:00:00', '2026-10-22T00:00:00Z'),
                           ('NaT', '2026-10-22T00:00:00Z'),
                           ('invalid', '2026-10-22T00:00:00Z'),
                           ('2026-10-21T00:00:00Z', '2026-10-26T00:00:00Z')]:
            with self.subTest(start=start, end=end):
                manifest = self.manifest()
                manifest['periods'][2].update(start=start, end=end)
                self.assert_invalid_periods(manifest)

    def test_accepts_adjacent_and_gapped_period_windows(self):
        manifest = self.manifest()
        r.validate_periods(manifest)
        manifest['periods'][1]['start'] = '2026-10-20T00:01:00Z'
        r.validate_periods(manifest)

    def test_validation_rejects_bad_inputs(self):
        f = fixture()
        start, end = f.index[0], f.index[-1] + pd.Timedelta(minutes=1)
        r.validate(f, start, end)
        for bad in [f.iloc[:-1], f.iloc[1:], f.iloc[::-1], pd.concat([f, f.iloc[-1:]])]:
            with self.assertRaises(ValueError):
                r.validate(bad, start, end)
        for column, value in [('close', np.nan), ('volume', -1), ('high', 90), ('low', 110), ('open', 0)]:
            bad = f.copy()
            bad.iloc[20, bad.columns.get_loc(column)] = value
            with self.assertRaises(ValueError):
                r.validate(bad, start, end)

    def test_ha_hand_calculation_and_prefix(self):
        f = fixture()
        f.iloc[0] = [100, 106, 98, 104, 10]
        f.iloc[1] = [104, 108, 102, 106, 10]
        h = r.indicators(f)
        self.assertEqual(h.open.iloc[0], 102)
        self.assertEqual(h.close.iloc[0], 102)
        self.assertEqual(h.open.iloc[1], 102)
        self.assertEqual(h.close.iloc[1], 105)
        changed = f.copy()
        changed.iloc[220:, :4] *= 2
        pd.testing.assert_frame_equal(r.indicators(changed).iloc[:220], h.iloc[:220])
        pd.testing.assert_series_equal(r.signals(changed).iloc[:220], r.signals(f).iloc[:220])
        pd.testing.assert_series_equal(r.signals(f.iloc[:220]), r.signals(f).iloc[:220])

    def test_exact_pullback_and_doji_requirements(self):
        f = fixture()
        h = pd.DataFrame(dict(open=95., close=96., high=97., low=94., ema=90.), index=f.index)
        h.iloc[208:210] = [97, 95, 98, 94, 90]
        h.iloc[210] = [96, 96.1, 97, 95, 90]
        with patch.object(r, 'indicators', return_value=h):
            self.assertEqual(r.signals(f).iloc[210], 1)
        h.iloc[209, h.columns.get_loc('close')] = 98
        with patch.object(r, 'indicators', return_value=h):
            self.assertEqual(r.signals(f).iloc[210], 0)
        h.iloc[209, h.columns.get_loc('close')] = 95
        for column, value in [('close', 97), ('high', 110)]:
            bad = h.copy()
            bad.iloc[210, bad.columns.get_loc(column)] = value
            with patch.object(r, 'indicators', return_value=bad):
                self.assertEqual(r.signals(f).iloc[210], 0)
        # Mirror all HA and actual prices about 100 for the short case.
        h.iloc[209, h.columns.get_loc('close')] = 95
        mirrored = h.copy()
        for k in ['open', 'close', 'ema']:
            mirrored[k] = 200-h[k]
        mirrored.high, mirrored.low = 200-h.low, 200-h.high
        with patch.object(r, 'indicators', return_value=mirrored):
            self.assertEqual(r.signals(f).iloc[210], -1)

    def test_next_open_actual_stop_and_costs(self):
        f = fixture()
        intent = pd.Series(0, index=f.index)
        intent.iloc[210] = 1
        result = r.simulate(f, intent, True)
        trade = result['trades'][0]
        self.assertEqual(trade['entry_time'], str(f.index[211]))
        self.assertAlmostEqual(trade['entry'], 100.03)
        self.assertEqual(trade['stop'], 98.99)
        # Both touched in entry bar: stop always wins.
        f.iloc[211, f.columns.get_loc('low')] = 98
        f.iloc[211, f.columns.get_loc('high')] = 110
        trade = r.simulate(f, intent, True)['trades'][0]
        self.assertEqual(trade['reason'], 'stop')
        self.assertAlmostEqual(trade['exit'], 98.99 * .9997)
        fees = .001*(100.03+98.99*.9997)
        self.assertAlmostEqual(trade['net'], 98.99*.9997-100.03-fees)
        self.assertAlmostEqual(trade['costs'], fees+.03+98.99*.0003)
        target_net = trade['target']*.9997-100.03-.001*(100.03+trade['target']*.9997)
        self.assertAlmostEqual(target_net, -trade['net'])
        intent.iloc[210] = -1
        short = r.simulate(f, intent, True)['trades'][0]
        short_target = short['entry']-short['target']*1.0003-.001*(short['entry']+short['target']*1.0003)
        self.assertAlmostEqual(short_target, -short['net'])

    def test_gap_stop_and_invalid_entry(self):
        f = fixture()
        intent = pd.Series(0, index=f.index)
        intent.iloc[210] = 1
        f.iloc[212] = [95, 96, 94, 95, 10]
        trade = r.simulate(f, intent, True)['trades'][0]
        self.assertEqual(trade['reason'], 'gap_stop')
        self.assertAlmostEqual(trade['exit'], 95*.9997)
        f.iloc[211] = [98, 99, 97, 98, 10]
        self.assertEqual(r.simulate(f, intent, True)['trade_count'], 0)

    def test_frozen_historical_regression_and_reconciliation(self):
        before = (r.ROOT/'results.json').read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'results.json'
            with contextlib.redirect_stdout(io.StringIO()):
                r.run(output_path=output)
            self.assertEqual(before, output.read_bytes())
        self.assertEqual(before, (r.ROOT/'results.json').read_bytes())
        rows = json.loads(before)
        ha = [x for x in rows if x.get('strategy') == 'ha_pullback']
        self.assertEqual([x['trade_count'] for x in ha], [2, 2, 4])
        for row in rows:
            self.assertNotIn('rejected', row)
            self.assertAlmostEqual(sum(t['net'] for t in row['trades']), row['net_pnl'])
            self.assertAlmostEqual(sum(t['costs'] for t in row['trades']), row['costs'])


if __name__ == '__main__':
    unittest.main()
