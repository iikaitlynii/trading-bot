"""Frozen historical trace regressions plus explicitly synthetic alias rejection."""
import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from data_contracts.ingestion import collect, parse, UNIVERSES
from paper_sessions import already_processed
from research.reliability.recovery import MANIFEST, ROOT, checked_source, corroborate_stock, verify
from test_ingestion import NOW, response


class HistoricalRecoveryTests(unittest.TestCase):
    def test_frozen_rows_reproduce_but_never_become_accepted_sessions(self):
        report = verify()
        self.assertEqual(report['status'], 'BLOCKED')
        self.assertEqual(report['accepted_corrections'], [])
        self.assertEqual([r['saved_value'] for r in report['stock_rows']],
                         ['9883.03', '10029.89', '10053.48'])
        self.assertEqual([r['line_number'] for r in report['stock_rows']], [25, 26, 27])
        self.assertTrue(all(r['verified_market_session'] is None for r in report['stock_rows']))

    def test_original_duplicate_ledger_still_blocks_replay_without_mutation(self):
        manifest = json.loads(MANIFEST.read_text())
        for row in manifest['stock_rows'][2:]:
            payload = checked_source(ROOT, row['sources']['paper/performance.csv'])
            state = json.loads(checked_source(ROOT, row['sources']['paper/state.json']))
            before = copy.deepcopy(state)
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'performance.csv'
                path.write_bytes(payload)
                with self.assertRaisesRegex(ValueError, 'duplicate'):
                    already_processed(state, '2026-09-21', path)
                self.assertEqual(path.read_bytes(), payload)
                self.assertEqual(state, before)

    def test_tampered_archive_or_claimed_correction_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            relative = MANIFEST.relative_to(ROOT)
            shutil.copytree(MANIFEST.parent, root / relative.parent)
            manifest = json.loads((root / relative).read_text())
            source = next(iter(manifest['originals'].values()))
            target = root / source['path']
            original = target.read_bytes()
            target.write_bytes(original + b'\n')
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                verify(root)
            target.write_bytes(original)
            manifest['accepted_corrections'] = [{'session': '2026-09-18'}]
            (root / relative).write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'cannot authorize'):
                verify(root)

    def test_real_pepe_rejection_is_not_proof_of_delisting_or_a_price(self):
        path = ROOT / 'research/reliability/evidence/f0b5f9feeac9f1fc93c31b1edc03fbc1fda4acb3ec5e233ebb39d6f8b66e1769.response'
        payload = path.read_bytes()
        self.assertEqual(hashlib.sha256(payload).hexdigest(), path.stem)
        with self.assertRaisesRegex(ValueError, 'PROVIDER_REJECTED'):
            parse(payload, 'PEPE-USD', 'crypto', NOW, NOW, 'recovery-regression')

    def test_candidate_cannot_satisfy_logical_asset_or_replace_accepted_bundle(self):
        # Synthetic healthy candidate bars prove that even usable candidate data
        # cannot bypass exact-symbol/full-universe validation without review.
        self.assertIn('PEPE-USD', UNIVERSES['crypto'])
        self.assertNotIn('PEPE24478-USD', UNIVERSES['crypto'])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            collect('crypto', root, clock=lambda: NOW,
                    fetch=lambda s: (200, response(s)), code_version='synthetic-test')
            pointer = root / 'research/datasets/ingested/crypto-latest.json'
            before = pointer.read_bytes()
            def mapped(symbol):
                return 200, response('PEPE24478-USD' if symbol == 'PEPE-USD' else symbol)
            with self.assertRaisesRegex(ValueError, 'MISSING_SYMBOLS: PEPE-USD'):
                collect('crypto', root, clock=lambda: NOW, fetch=mapped,
                        code_version='synthetic-test')
            self.assertEqual(pointer.read_bytes(), before)
            status = json.loads((root / 'work/ingestion/crypto.json').read_text())
            self.assertEqual(status['symbols']['PEPE-USD']['reason'], 'SYMBOL_MISMATCH')

    def test_fresh_crypto_failures_preserve_last_accepted_complete_bundle(self):
        probes = json.loads((MANIFEST.parent / 'crypto-probes.json').read_text())['probes']
        by_symbol = {p['symbol']: p for p in probes}
        clock = datetime.fromisoformat(by_symbol['DOGE-USD']['request_started_at'])
        frozen = {}
        for symbol, probe in by_symbol.items():
            payload = (ROOT / probe['raw_path']).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), probe['sha256'])
            frozen[symbol] = (probe['http_status'], payload)
            if symbol == 'PEPE-USD':
                self.assertEqual(probe['http_status'], 404)
                continue
            result = json.loads(payload)['chart']['result'][0]
            self.assertEqual(len(result['timestamp']), len(set(result['timestamp'])))
            self.assertEqual(result['timestamp'], sorted(result['timestamp']))
            index = result['timestamp'].index(1793750400)  # 2026-11-04T00:00Z
            for values in result['indicators']['quote'][0].values():
                self.assertIsNone(values[index])
            with self.subTest(symbol=symbol), self.assertRaisesRegex(ValueError, 'INVALID_OHLCV'):
                parse(payload, symbol, 'crypto', clock, clock, 'frozen-real-probe')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            collect('crypto', root, clock=lambda: NOW,
                    fetch=lambda s: (200, response(s)), code_version='synthetic-test')
            pointer = root / 'research/datasets/ingested/crypto-latest.json'
            before = pointer.read_bytes()
            with self.assertRaisesRegex(ValueError, 'MISSING_SYMBOLS'):
                collect('crypto', root, clock=lambda: clock,
                        fetch=lambda s: frozen[s], code_version='frozen-real-probe')
            self.assertEqual(pointer.read_bytes(), before)
            status = json.loads((root / 'work/ingestion/crypto.json').read_text())
            self.assertEqual(status['status'], 'BLOCKED')
            self.assertEqual(status['publication'], 'NOT_ATTEMPTED')
            self.assertTrue(all(e['status'] == 'BLOCKED' for e in status['symbols'].values()))

    def test_later_provider_matches_are_corroboration_never_session_corrections(self):
        report = corroborate_stock()
        self.assertEqual([r['matching_later_provider_dates'] for r in report],
                         [['2026-09-16'], ['2026-09-17'], ['2026-09-18']])
        self.assertTrue(all(r['verified_market_session'] is None for r in report))
        self.assertEqual(verify()['accepted_corrections'], [])
