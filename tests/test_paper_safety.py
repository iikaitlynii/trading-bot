"""Offline regression tests: no market network or real trading."""
import csv
import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import crypto_paper_trader as crypto
import paper_trader as stock


class PaperSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.previous_cwd = os.getcwd()
        os.chdir(self.tmp.name)

    def tearDown(self):
        os.chdir(self.previous_cwd)
        self.tmp.cleanup()

    @staticmethod
    def history(days=220, value=10.0):
        today = datetime.now(crypto.RUN_TIMEZONE).date()
        dates = pd.date_range(end=today, periods=days, freq="D")
        return pd.Series([value] * days, index=dates, dtype=float)

    def test_crypto_missing_unheld_asset_does_not_sell_held_asset(self):
        Path("crypto_paper").mkdir()
        Path("crypto_paper/state.json").write_text(json.dumps({
            "cash": 4000.0,
            "positions": {"DOGE-USD": {"units": 100, "entry_price": 10.0, "entry_date": "2026-01-01"}},
            "last_run_date": None,
        }))
        def prices(ticker):
            if ticker == "PEPE-USD":
                return pd.Series(dtype=float)
            return self.history()
        with patch.object(crypto, "get_close", side_effect=prices):
            crypto.main()
        with open("crypto_paper/state.json") as f:
            state = json.load(f)
        self.assertIn("DOGE-USD", state["positions"])
        self.assertFalse(Path("crypto_paper/journal.csv").exists())
        with open("crypto_paper/latest_signals.csv", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(next(x for x in rows if x["ticker"] == "PEPE-USD")["signal"], "NO_DATA")

    def test_crypto_missing_held_asset_skips_entire_session(self):
        Path("crypto_paper").mkdir()
        original = {"cash": 4000.0, "positions": {
            "PEPE-USD": {"units": 100, "entry_price": 10.0, "entry_date": "2026-01-01"}
        }, "last_run_date": None}
        Path("crypto_paper/state.json").write_text(json.dumps(original))
        with patch.object(crypto, "get_close", side_effect=lambda t: pd.Series(dtype=float) if t == "PEPE-USD" else self.history()):
            crypto.main()
        self.assertEqual(json.loads(Path("crypto_paper/state.json").read_text()), original)
        self.assertFalse(Path("crypto_paper/performance.csv").exists())
        self.assertFalse(Path("crypto_paper/journal.csv").exists())

    def test_stock_incomplete_history_skips_session(self):
        Path("paper").mkdir()
        original = {"cash": 10000.0, "positions": {}, "last_run_date": None}
        Path("paper/state.json").write_text(json.dumps(original))
        with patch.object(stock, "get_data", side_effect=lambda t: pd.Series(dtype=float) if t == "MSFT" else self.history()):
            stock.main()
        self.assertEqual(json.loads(Path("paper/state.json").read_text()), original)
        self.assertFalse(Path("paper/performance.csv").exists())
        self.assertFalse(Path("paper/journal.csv").exists())


if __name__ == "__main__":
    unittest.main()
