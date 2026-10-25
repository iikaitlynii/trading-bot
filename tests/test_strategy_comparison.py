"""Offline synthetic regressions; no evidence of historical profitability."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

import strategy_comparison as comparison


class StrategyComparisonTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(comparison.yf, 'download', side_effect=AssertionError('Unexpected network')))

    @staticmethod
    def prices(values=None, periods=300):
        values = np.full(periods, 100.0) if values is None else values
        return pd.Series(values, index=pd.date_range('2024-01-01', periods=len(values), freq='D'))

    def assert_metric(self, result, name, daily, exposure):
        # Independent scalar ledger, including the initial unit of equity.
        wealth, peak, worst, previous, changes = 1.0, 1.0, 0.0, 0, 0
        for change, held in zip(daily, exposure):
            turnover = abs(held - previous)
            wealth *= 1 + change * held - turnover * 0.002
            peak = max(peak, wealth)
            worst = min(worst, wealth / peak - 1)
            changes += turnover
            previous = held
        self.assertEqual(result[name + '_return_pct'], round((wealth - 1) * 100, 2))
        self.assertEqual(result[name + '_max_drawdown_pct'], round(worst * 100, 2))
        self.assertEqual(result[name + '_position_changes'], changes)
        self.assertEqual(result[name + '_invested_days'], sum(exposure))

    def test_flat_prices_charge_one_buy_hold_entry_and_cash_is_flat(self):
        result = comparison.calculate('AAPL', self.prices())
        self.assert_metric(result, 'buy_hold', [0] * 120, [1] * 120)
        for name in ('trend', 'momentum', 'cash'):
            self.assert_metric(result, name, [0] * 120, [0] * 120)

    def test_benchmark_includes_boundary_return_and_has_no_forced_exit(self):
        close = self.prices()
        close.iloc[-120:] = 125
        result = comparison.calculate('AAPL', close)
        # Initial capital is valued at the preceding close (100), not 125.
        self.assert_metric(result, 'buy_hold', [0.25] + [0] * 119, [1] * 120)
        self.assertEqual(result['sessions'], 120)
        self.assertEqual(result['as_of'], close.index[-1].date().isoformat())

    def test_entry_exit_and_reentry_match_scalar_ledger_for_each_regime(self):
        values = [100.0] * 300
        for i in range(210, 240):
            values[i] = 200.0
        for i in range(240, 270):
            values[i] = 50.0
        for i in range(270, 300):
            values[i] = 220.0
        for ticker, regime in [('AAPL', 200), ('DOGE-USD', 100)]:
            with self.subTest(ticker=ticker):
                result = comparison.calculate(ticker, self.prices(values))
                exposures = {'trend': [], 'momentum': []}
                returns = []
                for i in range(180, 300):
                    previous = i - 1
                    past = values[:i]
                    exposures['trend'].append(int(previous >= regime - 1 and
                        past[-1] > sum(past[-regime:]) / regime and
                        sum(past[-20:]) / 20 > sum(past[-50:]) / 50))
                    exposures['momentum'].append(int(past[-1] > past[-21]))
                    returns.append(values[i] / values[i-1] - 1)
                for name, exposure in exposures.items():
                    self.assertGreater(sum(abs(a-b) for a,b in zip([0]+exposure, exposure)), 1)
                    self.assert_metric(result, name, returns, exposure)

    def test_signal_cannot_capture_the_jump_that_creates_it(self):
        close = self.prices()
        close.iloc[-1] = 1000
        result = comparison.calculate('AAPL', close)
        for name in ('trend', 'momentum'):
            self.assertEqual(result[name + '_invested_days'], 0)
            self.assertEqual(result[name + '_return_pct'], 0)

    def test_future_price_does_not_change_prior_exposure(self):
        close = self.prices(np.linspace(100, 200, 320))
        # Last-session shock changes valuation, never that session's exposure.
        for ticker in ('AAPL', 'DOGE-USD'):
            original = comparison.calculate(ticker, close)
            shock = close.copy()
            shock.iloc[-1] = 1
            shocked = comparison.calculate(ticker, shock)
            for name in ('trend', 'momentum'):
                self.assertEqual(original[name+'_invested_days'], shocked[name+'_invested_days'])
                self.assertEqual(original[name+'_position_changes'], shocked[name+'_position_changes'])

    def test_fee_and_slippage_are_independent_adverse_costs(self):
        close = self.prices()
        for fee, slippage, expected in [(0, 0, 0), (10, 0, -0.1), (0, 10, -0.1), (10, 10, -0.2)]:
            with self.subTest(fee=fee, slippage=slippage), patch.object(comparison, 'FEE_BPS', fee), patch.object(comparison, 'SLIPPAGE_BPS', slippage):
                result = comparison.calculate('AAPL', close)
                self.assertEqual(result['buy_hold_return_pct'], expected)
                self.assertEqual(result['cash_return_pct'], 0)

    def test_invalid_prices_fail_instead_of_creating_signals(self):
        for value in (np.nan, np.inf, -np.inf, 0, -1, 'bad', '100', True, 1j):
            for offset in (-1, -40, 10):
                with self.subTest(value=value, offset=offset):
                    close = self.prices().astype(object)
                    close.iloc[offset] = value
                    with self.assertRaises(ValueError):
                        comparison.calculate('AAPL', close)

    def test_invalid_dates_and_shapes_fail(self):
        close = self.prices()
        duplicate = close.copy()
        duplicate.index = close.index[:-1].append(close.index[-2:-1])
        nat = close.copy()
        nat.index = close.index[:-1].append(pd.DatetimeIndex([pd.NaT]))
        same_day = close.copy()
        same_day.index = close.index[:-1].append(pd.DatetimeIndex([close.index[-2] + pd.Timedelta(hours=1)]))
        for bad in (same_day, close.iloc[:229], close.iloc[::-1], duplicate, nat, close.reset_index(drop=True), close.to_frame(), close.set_axis(close.index.astype(str))):
            with self.subTest(shape=type(bad).__name__), self.assertRaises(ValueError):
                comparison.calculate('AAPL', bad)

    def test_downloader_selects_requested_ticker_and_preserves_missing_rows(self):
        close = self.prices()
        close.iloc[-30] = np.nan
        for columns in ('field_first', 'ticker_first'):
            frame = pd.DataFrame({('Close', 'OTHER'): close.fillna(999), ('Close', 'AAPL'): close})
            if columns == 'ticker_first':
                frame = frame.swaplevel(axis=1)
            with self.subTest(columns=columns), patch.object(comparison.yf, 'download', return_value=frame) as download:
                actual = comparison.history('AAPL')
                self.assertTrue(pd.isna(actual.iloc[-30]))
                self.assertEqual(actual.iloc[0], 100)
                self.assertTrue(download.call_args.kwargs['auto_adjust'])
                with self.assertRaises(ValueError):
                    comparison.calculate('AAPL', actual)
            with patch.object(comparison.yf, 'download', return_value=frame.drop(columns='AAPL', level=1 if columns == 'field_first' else 0)):
                with self.assertRaises(ValueError):
                    comparison.history('AAPL')

    def test_repeat_runs_are_identical_and_input_is_unchanged(self):
        close = self.prices(np.linspace(100, 200, 300))
        original = close.copy(deep=True)
        self.assertEqual(comparison.calculate('AAPL', close), comparison.calculate('AAPL', close))
        pd.testing.assert_series_equal(close, original)

    def test_main_records_missing_asset_and_reproduces_csv_bytes(self):
        def feed(ticker):
            if ticker == 'BAD':
                bad = self.prices()
                bad.iloc[-1] = np.nan
                return bad
            return self.prices()
        with tempfile.TemporaryDirectory() as directory, patch.object(comparison, 'STOCKS', ['AAPL', 'BAD']), patch.object(comparison, 'MEMECOINS', []), patch.object(comparison, 'history', side_effect=feed), patch.object(comparison.pd.DataFrame, 'to_csv', autospec=True) as save, contextlib.redirect_stdout(io.StringIO()):
            # Redirect the two output files without changing process cwd.
            def write(frame, path, **kwargs):
                original_to_csv(frame, Path(directory) / path, **kwargs)
            save.side_effect = write
            comparison.main()
            first = {p.name: p.read_bytes() for p in Path(directory).iterdir()}
            comparison.main()
            self.assertEqual(first, {p.name: p.read_bytes() for p in Path(directory).iterdir()})
            missing = pd.read_csv(Path(directory) / 'strategy_comparison_missing.csv')
            self.assertEqual(missing.asset.tolist(), ['BAD'])
            self.assertEqual(pd.read_csv(Path(directory) / 'strategy_comparison_results.csv').asset.tolist(), ['AAPL'])

    def test_all_missing_raises_without_writing_results(self):
        with patch.object(comparison, 'history', side_effect=ValueError('missing')), patch.object(comparison.pd.DataFrame, 'to_csv') as save, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError):
                comparison.main()
            save.assert_not_called()


original_to_csv = pd.DataFrame.to_csv

if __name__ == '__main__':
    unittest.main()
