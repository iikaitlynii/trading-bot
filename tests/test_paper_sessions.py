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

    def test_entrypoints_cannot_bypass_legacy_reconciliation(self):
        import paper_trader as stock
        for module,folder in [(stock,'paper'),(crypto,'crypto_paper')]:
            previous=os.getcwd()
            with tempfile.TemporaryDirectory() as tmp:
                os.chdir(tmp)
                try:
                    Path(folder).mkdir()
                    path=Path(folder)/'performance.csv'
                    path.write_bytes(b'date_utc,paper_value\n2026-11-03,1\n2026-11-03,2\n')
                    before=path.read_bytes()
                    with self.assertRaisesRegex(ValueError,'BLOCKED'):module.main()
                    self.assertEqual(path.read_bytes(),before)
                    self.assertFalse(Path('simulation-v2').exists())
                finally:os.chdir(previous)
