"""Synthetic offline regression evidence, not historical returns."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
import crypto_paper_trader as crypto
from paper_sessions import already_processed, recorded_sessions


class SessionTests(unittest.TestCase):
    def test_ambiguous_ledgers_fail_closed_without_changes(self):
        for payload in ('date_utc\n2026-11-02\n2026-11-02\n',
                        'date_utc\n2026-11-03\n2026-11-02\n',
                        'date_utc\nnot-a-date\n', 'wrong_header\n',
                        'date_utc\n20261102\n'):
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp)/'performance.csv'
                path.write_text(payload)
                with self.assertRaises(ValueError):
                    already_processed({}, '2026-11-04', path)
                self.assertEqual(path.read_text(), payload)

    def test_older_and_recorded_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'performance.csv'
            path.write_text('date_utc\n2026-11-02\n')
            self.assertTrue(already_processed({}, '2026-11-02', path))
            with self.assertRaisesRegex(ValueError, 'precedes'):
                already_processed({}, '2026-11-01', path)
            self.assertFalse(already_processed({}, '2026-11-03', path))
            with self.assertRaisesRegex(ValueError, 'precedes'):
                already_processed({'last_price_session':'2026-11-04'},
                                  '2026-11-03', path, crypto=True)

    def test_unreadable_ledger_is_not_an_empty_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(OSError):
                recorded_sessions(tmp)

    def test_stock_saved_evidence_is_never_silently_normalized(self):
        import paper_trader as stock
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 11, 5, 2, tzinfo=timezone.utc).astimezone(tz)
        history = pd.Series(range(1, 221), dtype=float,
                            index=pd.bdate_range(end='2026-11-04', periods=220))
        for ledger in ('date_utc,paper_value\n2026-11-04,10000\n',
                       'date_utc,paper_value\n2026-11-03,10000\n2026-11-03,10000\n'):
            previous = os.getcwd()
            with self.subTest(ledger=ledger), tempfile.TemporaryDirectory() as tmp:
                os.chdir(tmp)
                try:
                    Path('paper').mkdir()
                    state = Path('paper/state.json')
                    state.write_text(json.dumps({'cash': 10000, 'positions': {},
                                                'last_run_date': '2026-11-03'}))
                    saved = state.read_bytes()
                    Path('paper/performance.csv').write_text(ledger)
                    with patch.object(stock, 'datetime', Clock), patch.object(
                            stock, 'get_data', return_value=history):
                        if ledger.count('2026-11-03') == 2:
                            with self.assertRaisesRegex(ValueError, 'duplicate'):
                                stock.main()
                        else:
                            stock.main()
                    self.assertEqual(state.read_bytes(), saved)
                    self.assertEqual(Path('paper/performance.csv').read_text(), ledger)
                    self.assertFalse(Path('paper/journal.csv').exists())
                    self.assertFalse(Path('paper/latest_signals.csv').exists())
                finally:
                    os.chdir(previous)

    def test_crypto_new_source_on_same_chicago_date_is_processed(self):
        class Clock(datetime):
            day, hour = 3, 23
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 11, cls.day, cls.hour, tzinfo=timezone.utc).astimezone(tz)
        def feed(ticker):
            end = '2026-11-02' if Clock.day == 3 else '2026-11-03'
            return pd.Series(range(1, 221), dtype=float,
                             index=pd.date_range(end=end, periods=220))
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                with patch.object(crypto, 'datetime', Clock), patch.object(
                        crypto, 'get_close', side_effect=feed):
                    crypto.main()
                    Clock.day, Clock.hour = 4, 1
                    crypto.main()
                    self.assertEqual(recorded_sessions('crypto_paper/performance.csv'),
                                     ['2026-11-02', '2026-11-03'])
            finally:
                os.chdir(previous)

    def test_crypto_same_source_across_chicago_midnight_is_not_replayed(self):
        class Clock(datetime):
            hour = 4
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 11, 4, cls.hour, tzinfo=timezone.utc).astimezone(tz)
        history = pd.Series(range(1, 221), dtype=float,
                            index=pd.date_range(end='2026-11-03', periods=220))
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                with patch.object(crypto, 'datetime', Clock), patch.object(
                        crypto, 'get_close', return_value=history):
                    crypto.main()
                    paths = [Path('crypto_paper')/name for name in
                             ('state.json', 'journal.csv', 'performance.csv')]
                    saved = [p.read_bytes() for p in paths]
                    self.assertEqual(json.loads(saved[0])['last_price_session'], '2026-11-03')
                    Clock.hour = 6
                    crypto.main()
                    self.assertEqual(saved, [p.read_bytes() for p in paths])
                    self.assertEqual(recorded_sessions(paths[-1]), ['2026-11-03'])
            finally:
                os.chdir(previous)
