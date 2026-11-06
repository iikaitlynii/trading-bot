"""Deterministic synthetic-account risk regressions, without network access."""
import contextlib
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from paper_risk import Limits, buy_budget, snapshot, record_risk
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
