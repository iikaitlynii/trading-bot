"""Deterministic daily-data audit: synthetic prices, no market network."""
import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

import crypto_paper_trader as crypto
import paper_trader as stock


class FixedClock(datetime):
    @classmethod
    def now(cls, tz=None):
        now = datetime(2026, 1, 14, 23, 30, tzinfo=timezone.utc)
        return now.astimezone(tz) if tz else now.replace(tzinfo=None)


class MarketDataQualityTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(stock, "datetime", FixedClock))
        self.enterContext(patch.object(crypto, "datetime", FixedClock))
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        # An accidental network call is a test failure, never a live-data test.
        download = self.enterContext(patch.object(stock.yf, "download"))
        download.side_effect = AssertionError("Unexpected market network call")

    @contextlib.contextmanager
    def account(self, module, *, positions=None):
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as directory:
            os.chdir(directory)
            try:
                folder = Path(module.STATE_FILE).parent
                folder.mkdir()
                state = {"cash": module.STARTING_CASH, "positions": positions or {},
                         "last_run_date": None}
                Path(module.STATE_FILE).write_text(json.dumps(state))
                original = Path(module.STATE_FILE).read_bytes()
                yield original
            finally:
                os.chdir(previous)

    @staticmethod
    def history(module, *, end=None, periods=220):
        end = end or ("2026-01-14" if module is stock else "2026-01-13")
        index = pd.date_range(end=end, periods=periods, freq="B" if module is stock else "D")
        return pd.Series(np.linspace(10, 30, periods), index=index)

    @staticmethod
    def held(module, ticker=None):
        return {ticker or module.TICKERS[0]: {
            "shares" if module is stock else "units": 10,
            "entry_price": 10, "entry_date": "2025-01-01",
        }}

    def run_feed(self, module, bad, *, target=None):
        target = target or module.TICKERS[0]
        getter = "get_data" if module is stock else "get_close"
        def feed(ticker):
            if ticker == target:
                if isinstance(bad, Exception):
                    raise bad
                return bad
            return self.history(module)
        with patch.object(module, getter, side_effect=feed):
            module.main()

    def assert_held(self, module, original):
        self.assertEqual(Path(module.STATE_FILE).read_bytes(), original)
        self.assertFalse(Path(module.PERFORMANCE_FILE).exists())
        self.assertFalse(Path(module.JOURNAL_FILE).exists())

    def test_invalid_prices_never_trade_or_value_held_assets(self):
        for module in (stock, crypto):
            for value in (np.nan, np.inf, -np.inf, 0, -1, "bad", "12.5", True, 1j, pd.NA):
                # A bad point inside the MA window must not be silently dropped.
                for offset in (-1, -20):
                    with self.subTest(trader=module.__name__, value=value, offset=offset):
                        bad = self.history(module).astype(object)
                        bad.iloc[offset] = value
                        # Keep real numeric dtype for numerical corruption cases.
                        if isinstance(value, (float, int)) and not isinstance(value, bool):
                            bad = bad.astype(float)
                        with self.account(module, positions=self.held(module)) as original:
                            self.run_feed(module, bad)
                            self.assert_held(module, original)

    def test_malformed_and_incomplete_histories_hold(self):
        for module in (stock, crypto):
            valid = self.history(module)
            duplicate = valid.copy()
            duplicate.index = valid.index[:-1].append(valid.index[-2:-1])
            intraday_duplicate = valid.copy()
            intraday_duplicate.index = valid.index[:-1].append(
                pd.DatetimeIndex([valid.index[-2] + pd.Timedelta(hours=1)]))
            missing_date = valid.copy()
            missing_date.index = valid.index[:-1].append(pd.DatetimeIndex([pd.NaT]))
            cases = {
                "empty": pd.Series(dtype=float),
                "too_short": valid.iloc[-(module.REGIME_MA_DAYS - 1):],
                "duplicate": duplicate, "same_day_twice": intraday_duplicate,
                "reversed": valid.iloc[::-1], "missing_date": missing_date,
                "string_index": valid.set_axis(valid.index.astype(str)),
                "range_index": valid.reset_index(drop=True),
                "wrong_shape": valid.to_frame(),
                "download_error": RuntimeError("provider unavailable"),
                "future": self.history(module, end="2026-01-15"),
                "stale": self.history(module, end="2026-01-05"),
            }
            if module is crypto:
                cases["too_short_after_unfinished_bar_removed"] = self.history(
                    crypto, end="2026-01-14", periods=crypto.REGIME_MA_DAYS)
            for name, bad in cases.items():
                with self.subTest(trader=module.__name__, case=name):
                    with self.account(module, positions=self.held(module)) as original:
                        self.run_feed(module, bad)
                        self.assert_held(module, original)

    def test_session_mismatch_holds_both_portfolios(self):
        for module in (stock, crypto):
            end = "2026-01-13" if module is stock else "2026-01-12"
            with self.subTest(trader=module.__name__):
                with self.account(module, positions=self.held(module)) as original:
                    self.run_feed(module, self.history(module, end=end))
                    self.assert_held(module, original)
                    self.assertFalse(Path(module.SIGNALS_FILE).exists())

    def test_untracked_held_asset_cannot_use_entry_price_as_market_value(self):
        for module in (stock, crypto):
            with self.subTest(trader=module.__name__):
                with self.account(module, positions=self.held(module, "REMOVED")) as original:
                    self.run_feed(module, self.history(module))
                    self.assert_held(module, original)

    def test_crypto_invalid_unheld_asset_is_no_data_not_defensive(self):
        for value in (np.nan, np.inf, 0, -1):
            with self.subTest(value=value):
                with self.account(crypto, positions=self.held(crypto)):
                    bad = self.history(crypto)
                    bad.iloc[-1] = value
                    self.run_feed(crypto, bad, target="PEPE-USD")
                    signals = pd.read_csv(crypto.SIGNALS_FILE).set_index("ticker")
                    self.assertEqual(signals.loc["PEPE-USD", "signal"], "NO_DATA")
                    state = json.loads(Path(crypto.STATE_FILE).read_text())
                    self.assertIn("DOGE-USD", state["positions"])
                    self.assertNotIn("PEPE-USD", state["positions"])
                    journal = pd.read_csv(crypto.JOURNAL_FILE)
                    self.assertNotIn("SIM_SELL", set(journal.action))
                    self.assertNotIn("PEPE-USD", set(journal.ticker))

    def test_crypto_all_missing_does_not_consume_daily_run(self):
        with self.account(crypto) as original:
            with patch.object(crypto, "get_close", return_value=pd.Series(dtype=float)):
                crypto.main()
            self.assert_held(crypto, original)
            signals = pd.read_csv(crypto.SIGNALS_FILE)
            self.assertEqual(set(signals.signal), {"NO_DATA"})

    def test_crypto_missing_interior_daily_session_holds(self):
        with self.account(crypto, positions=self.held(crypto)) as original:
            bad = self.history(crypto).drop(self.history(crypto).index[-10])
            self.run_feed(crypto, bad)
            self.assert_held(crypto, original)

    def test_stock_weekend_session_is_invalid(self):
        with self.account(stock, positions=self.held(stock)) as original:
            bad = self.history(stock)
            index = list(bad.index)
            index[-3] = pd.Timestamp("2026-01-11")  # Sunday, before Monday's row.
            bad.index = pd.DatetimeIndex(index)
            self.run_feed(stock, bad)
            self.assert_held(stock, original)

    def test_stock_uses_unrounded_prices_for_simulated_accounting(self):
        with self.account(stock):
            tiny = self.history(stock) * 1e-8
            with patch.object(stock, "get_data", return_value=tiny):
                stock.main()
            state = json.loads(Path(stock.STATE_FILE).read_text())
            self.assertEqual(len(state["positions"]), len(stock.TICKERS))
            for position in state["positions"].values():
                self.assertEqual(position["entry_price"], tiny.iloc[-1])
            self.assertEqual(pd.read_csv(stock.PERFORMANCE_FILE).iloc[-1].paper_value, stock.STARTING_CASH)

    def test_valid_data_processes_once_and_only_creates_simulated_buys(self):
        for module in (stock, crypto):
            with self.subTest(trader=module.__name__):
                with self.account(module):
                    self.run_feed(module, self.history(module))
                    state = json.loads(Path(module.STATE_FILE).read_text())
                    self.assertEqual(set(state["positions"]), set(module.TICKERS))
                    journal = pd.read_csv(module.JOURNAL_FILE)
                    self.assertEqual(set(journal.action), {"SIM_BUY"})
                    self.assertEqual(len(pd.read_csv(module.PERFORMANCE_FILE)), 1)
                    before = {p: p.read_bytes() for p in Path('.').rglob('*') if p.is_file()}
                    self.run_feed(module, self.history(module))
                    self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_completed_healthy_defensive_data_still_sells_in_simulation(self):
        for module in (stock, crypto):
            with self.subTest(trader=module.__name__):
                with self.account(module, positions=self.held(module)):
                    falling = self.history(module)
                    falling.iloc[:] = np.linspace(30, 10, len(falling))
                    getter = "get_data" if module is stock else "get_close"
                    with patch.object(module, getter, return_value=falling):
                        module.main()
                    self.assertEqual(json.loads(Path(module.STATE_FILE).read_text())["positions"], {})
                    self.assertEqual(set(pd.read_csv(module.JOURNAL_FILE).action), {"SIM_SELL"})

    def test_crypto_current_utc_bar_is_not_a_completed_close(self):
        with self.account(crypto):
            history = self.history(crypto, end="2026-01-14")
            expected = history.iloc[-2]
            history.iloc[-1] = 0  # Unfinished bar must not become a sell signal.
            with patch.object(crypto, "get_close", return_value=history):
                crypto.main()
            signals = pd.read_csv(crypto.SIGNALS_FILE)
            np.testing.assert_allclose(signals.close, expected)
            self.assertTrue((signals.price_session == "2026-01-13").all())

    def test_crypto_completed_bar_uses_utc_even_on_previous_central_date(self):
        class AfterUtcMidnight(FixedClock):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 1, 15, 0, 30, tzinfo=timezone.utc).astimezone(tz)
        with self.account(crypto):
            history = self.history(crypto, end="2026-01-14")
            with patch.object(crypto, "datetime", AfterUtcMidnight), patch.object(crypto, "get_close", return_value=history):
                crypto.main()
            signals = pd.read_csv(crypto.SIGNALS_FILE)
            self.assertTrue((signals.date_utc == "2026-01-14").all())
            self.assertTrue((signals.price_session == "2026-01-14").all())

    def test_stock_before_close_uses_previous_completed_session(self):
        class BeforeClose(FixedClock):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 1, 14, 15, tzinfo=timezone.utc).astimezone(tz)
        with self.account(stock):
            history = self.history(stock)
            with patch.object(stock, "datetime", BeforeClose), patch.object(stock, "get_data", return_value=history):
                stock.main()
            self.assertEqual(json.loads(Path(stock.STATE_FILE).read_text())["last_run_date"], "2026-01-13")

    def test_stock_accepts_friday_prices_on_monday_morning(self):
        class Monday(FixedClock):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 1, 12, 14, tzinfo=timezone.utc).astimezone(tz)
        with self.account(stock):
            history = self.history(stock, end="2026-01-09")
            with patch.object(stock, "datetime", Monday), patch.object(stock, "get_data", return_value=history):
                stock.main()
            self.assertEqual(json.loads(Path(stock.STATE_FILE).read_text())["last_run_date"], "2026-01-09")

    def test_stock_cannot_replay_an_older_session(self):
        with self.account(stock):
            state = json.loads(Path(stock.STATE_FILE).read_text())
            state["last_run_date"] = "2026-01-14"
            Path(stock.STATE_FILE).write_text(json.dumps(state))
            original = Path(stock.STATE_FILE).read_bytes()
            old = self.history(stock, end="2026-01-13")
            with patch.object(stock, "get_data", return_value=old):
                stock.main()
            self.assert_held(stock, original)

    def test_download_selects_requested_symbol_and_preserves_bad_rows(self):
        for module, getter in ((stock, stock.get_data), (crypto, crypto.get_close)):
            ticker = module.TICKERS[0]
            valid = self.history(module)
            valid.iloc[-1] = np.nan
            download = pd.DataFrame({("Close", "OTHER"): valid.fillna(999), ("Close", ticker): valid})
            with self.subTest(trader=module.__name__):
                with patch.object(module.yf, "download", return_value=download):
                    pd.testing.assert_series_equal(getter(ticker), download[("Close", ticker)])
                with patch.object(module.yf, "download", return_value=download.drop(columns=ticker, level=1)):
                    with self.assertRaises((KeyError, ValueError)):
                        getter(ticker)


if __name__ == "__main__":
    unittest.main()
