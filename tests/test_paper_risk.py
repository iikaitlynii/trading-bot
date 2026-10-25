"""Deterministic synthetic-account risk regressions, without network access."""
import contextlib
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from paper_risk import Limits, buy_budget, snapshot, record_risk
import test_market_data_quality as quality
import paper_trader as stock
import crypto_paper_trader as crypto


class RiskCalculationTests(unittest.TestCase):
    def test_budget_boundaries(self):
        limits = Limits(.2, .5, .1)
        for cash, invested, expected in [(1000, 0, 200), (600, 400, 100),
                                          (500, 500, 0), (400, 600, 0), (25, 0, 25)]:
            with self.subTest(cash=cash, invested=invested):
                self.assertEqual(buy_budget(1000, cash, invested, limits), expected)
        self.assertEqual(buy_budget(0, 0, 0, limits), 0)
        self.assertEqual(buy_budget(1000, 1000, 0, Limits(0, 0, .1)), 0)

    def test_invalid_configuration_fails_closed(self):
        for value in (-.1, 1.01, float('nan'), float('inf'), True):
            for offset in range(3):
                args = [.2, .8, .1]
                args[offset] = value
                with self.subTest(value=value, offset=offset), self.assertRaises(ValueError):
                    Limits(*args)
        for value in ('bad', 'nan', '-1', '2', ''):
            with patch.dict(os.environ, {'STOCK_PAPER_MAX_EXPOSURE': value}):
                with self.assertRaises(ValueError):
                    Limits.from_env('STOCK_PAPER', .2, .8)

    def test_configuration_is_account_specific(self):
        with patch.dict(os.environ, {'STOCK_PAPER_MAX_POSITION_WEIGHT': '.05',
                                     'STOCK_PAPER_MAX_EXPOSURE': '.15',
                                     'STOCK_PAPER_DRAWDOWN_WARNING': '.25'}, clear=True):
            self.assertEqual(Limits.from_env('STOCK_PAPER', .2, .8), Limits(.05, .15, .25))
            self.assertEqual(Limits.from_env('CRYPTO_PAPER', .1, .4), Limits(.1, .4, .1))

    def test_mark_to_market_concentration_and_drawdown(self):
        state = {'cash': 600, 'positions': {'A': {'shares': 4}}}
        limits = Limits(.4, .5, .1)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            record_risk(state, {'A': 100}, 'shares', limits, 1000)
            self.assertEqual(state['peak_equity'], 1000)
            self.assertEqual(state['risk']['weights'], {'A': .4})
            self.assertFalse(state['risk']['limit_breach'])
            record_risk(state, {'A': 75}, 'shares', limits, 1000)
            self.assertAlmostEqual(state['risk']['drawdown'], .1)
            self.assertTrue(state['risk']['drawdown_warning'])
            self.assertEqual(state['peak_equity'], 1000)
            record_risk(state, {'A': 200}, 'shares', limits, 1000)
            self.assertEqual(state['peak_equity'], 1400)
            self.assertTrue(state['risk']['limit_breach'])
            record_risk(state, {'A': 100}, 'shares', limits, 1000)
            self.assertAlmostEqual(state['risk']['drawdown'], 2 / 7)
        self.assertIn('SIMULATED DRAWDOWN WARNING', output.getvalue())

    def test_invalid_accounts_cannot_be_valued(self):
        for cash, units, price in [(-1, 1, 10), (float('nan'), 1, 10),
                                    (100, -1, 10), (100, 1, 0), (100, 1, float('inf'))]:
            with self.subTest(cash=cash, units=units, price=price), self.assertRaises(ValueError):
                snapshot({'cash': cash, 'positions': {'A': {'units': units}}}, {'A': price}, 'units')
        self.assertEqual(snapshot({'cash': 0, 'positions': {}}, {}, 'units'), (0, 0, {}))


class RiskAccountTests(unittest.TestCase):
    account = quality.MarketDataQualityTests.account
    history = staticmethod(quality.MarketDataQualityTests.history)

    def setUp(self):
        self.enterContext(patch.dict(os.environ, {}, clear=True))
        self.enterContext(patch.object(stock, 'datetime', quality.FixedClock))
        self.enterContext(patch.object(crypto, 'datetime', quality.FixedClock))
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.enterContext(patch.object(stock.yf, 'download', side_effect=AssertionError('network forbidden')))

    def test_both_accounts_enforce_exposure_and_position_limits(self):
        for module, prefix, quantity in [(stock, 'STOCK_PAPER', 'shares'),
                                         (crypto, 'CRYPTO_PAPER', 'units')]:
            with self.subTest(module=module.__name__), self.account(module):
                with patch.dict(os.environ, {prefix + '_MAX_POSITION_WEIGHT': '.07',
                                             prefix + '_MAX_EXPOSURE': '.15'}):
                    getter = 'get_data' if module is stock else 'get_close'
                    with patch.object(module, getter, return_value=self.history(module)):
                        module.main()
                state = json.loads(Path(module.STATE_FILE).read_text())
                self.assertEqual(len(state['positions']), 3)
                notionals = [p[quantity] * 30 for p in state['positions'].values()]
                self.assertAlmostEqual(sum(notionals), module.STARTING_CASH * .15)
                self.assertLessEqual(max(notionals), module.STARTING_CASH * .07 + 1e-9)
                self.assertAlmostEqual(state['risk']['exposure'], .15)
                self.assertAlmostEqual(state['cash'], module.STARTING_CASH * .85)

    def test_partial_crypto_feed_pauses_buys_and_defensive_sells_then_recovers(self):
        positions = {'DOGE-USD': {'units': 10, 'entry_price': 30, 'entry_date': '2025-01-01'}}
        with self.account(crypto, positions=positions) as original:
            falling = self.history(crypto).iloc[::-1].to_numpy()
            defensive = self.history(crypto)
            defensive.iloc[:] = falling
            def feed(ticker):
                if ticker == 'PEPE-USD':
                    raise RuntimeError('offline')
                return defensive if ticker == 'DOGE-USD' else self.history(crypto)
            with patch.object(crypto, 'get_close', side_effect=feed):
                crypto.main()
            self.assertEqual(Path(crypto.STATE_FILE).read_bytes(), original)
            self.assertFalse(Path(crypto.JOURNAL_FILE).exists())
            self.assertFalse(Path(crypto.PERFORMANCE_FILE).exists())
            with patch.object(crypto, 'get_close', return_value=self.history(crypto)):
                crypto.main()
            self.assertIsNotNone(json.loads(Path(crypto.STATE_FILE).read_text())['last_run_date'])

    def test_bad_config_leaves_accounts_unchanged(self):
        for module, prefix in [(stock, 'STOCK_PAPER'), (crypto, 'CRYPTO_PAPER')]:
            with self.subTest(module=module.__name__), self.account(module) as original:
                with patch.dict(os.environ, {prefix + '_MAX_EXPOSURE': 'nan'}):
                    with self.assertRaises(ValueError):
                        module.main()
                self.assertEqual(Path(module.STATE_FILE).read_bytes(), original)
                self.assertFalse(Path(module.JOURNAL_FILE).exists())

    def test_existing_exposure_breach_blocks_new_entries_without_forced_sale(self):
        for module, quantity in [(stock, 'shares'), (crypto, 'units')]:
            positions = {module.TICKERS[0]: {quantity: 2000, 'entry_price': 10,
                                            'entry_date': '2025-01-01'}}
            with self.subTest(module=module.__name__), self.account(module, positions=positions):
                getter = 'get_data' if module is stock else 'get_close'
                with patch.object(module, getter, return_value=self.history(module)):
                    module.main()
                state = json.loads(Path(module.STATE_FILE).read_text())
                self.assertEqual(state['positions'], positions)
                self.assertEqual(state['cash'], module.STARTING_CASH)
                self.assertTrue(state['risk']['limit_breach'])
                self.assertFalse(Path(module.JOURNAL_FILE).exists())

    def test_persisted_peak_warns_in_both_accounts(self):
        for module in (stock, crypto):
            with self.subTest(module=module.__name__), self.account(module):
                state = json.loads(Path(module.STATE_FILE).read_text())
                state['peak_equity'] = module.STARTING_CASH * 2
                Path(module.STATE_FILE).write_text(json.dumps(state))
                getter = 'get_data' if module is stock else 'get_close'
                with patch.object(module, getter, return_value=self.history(module)):
                    module.main()
                saved = json.loads(Path(module.STATE_FILE).read_text())
                self.assertEqual(saved['peak_equity'], module.STARTING_CASH * 2)
                self.assertEqual(saved['risk']['drawdown'], .5)
                self.assertTrue(saved['risk']['drawdown_warning'])
