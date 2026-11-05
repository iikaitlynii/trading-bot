"""Offline synthetic provider evidence; never writes saved simulation accounts."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from data_contracts import ContractError
from data_contracts.ingestion import collect, parse, UNIVERSES

NOW = datetime(2026, 11, 3, 4, tzinfo=timezone.utc)


def response(symbol):
    end = datetime(2026, 11, 2, tzinfo=timezone.utc)
    stamps = [int((end - timedelta(days=i)).timestamp()) for i in reversed(range(220))]
    return json.dumps({'chart': {'error': None, 'result': [{'meta': {'symbol': symbol},
        'timestamp': stamps, 'indicators': {'quote': [{
            'close': [1.0]*220, 'high': [2.0]*220, 'low': [0.5]*220, 'volume': [100]*220}]}}]}}).encode()


class IngestionTests(unittest.TestCase):
    def parse(self, payload):
        return parse(payload, 'PEPE-USD', 'crypto', NOW, NOW, 'test')

    def test_reject_corrupt_sessions_and_prices(self):
        for kind in ('missing', 'duplicate', 'stale', 'invalid', 'null', 'symbol', 'short'):
            data = json.loads(response('PEPE-USD'))
            result = data['chart']['result'][0]
            quotes = result['indicators']['quote'][0]
            if kind == 'missing':
                del result['timestamp'][-10]
                for values in quotes.values(): del values[-10]
            elif kind == 'duplicate': result['timestamp'][-2] = result['timestamp'][-3]
            elif kind == 'stale':
                result['timestamp'].pop()
                for values in quotes.values(): values.pop()
            elif kind == 'invalid': quotes['close'][-1] = -1
            elif kind == 'null': quotes['volume'][-1] = None
            elif kind == 'symbol': result['meta']['symbol'] = 'OTHER'
            elif kind == 'short':
                result['timestamp'] = result['timestamp'][-10:]
                for key in quotes: quotes[key] = quotes[key][-10:]
            with self.subTest(kind=kind), self.assertRaises((ValueError, ContractError)):
                self.parse(json.dumps(data).encode())

    def test_archived_stock_failure_never_substitutes_previous_close(self):
        # Actual immutable responses from Actions run 41954673207. Only the
        # November 4 close is null; an older valid close must not replace it.
        root = Path(__file__).resolve().parents[1]
        hashes = (
            '834caeb790215a2ae52d36be649181bff2111ded76aa222b453a64ac6cb333fc',
            '742c73ccbfeb9505b68d21a6bc7e82c0f39946bad65e432a787ff54bdca4348e',
            '0d52b79661c94b39d18eedc6a825828da66484d2f535d2ab5e710852b620ecff',
            '9ab7102af6517aeb96a943941fdd376670dfbc8d407c3c936cbacd7bf767b9c5',
        )
        paths = [root/'research/datasets/ingested/raw'/f'{digest}.response'
                 for digest in hashes]
        symbols = set()
        clock = datetime(2026, 11, 5, 2, 21, 53, tzinfo=timezone.utc)
        for path in paths:
            payload = path.read_bytes()
            data = json.loads(payload)
            result = data['chart']['result'][0]
            symbol = result['meta']['symbol']
            if symbol not in UNIVERSES['stock']:
                continue
            symbols.add(symbol)
            with self.subTest(symbol=symbol), self.assertRaisesRegex(ValueError, 'INVALID_OHLCV'):
                parse(payload, symbol, 'stock', clock, clock, 'regression')
        self.assertEqual(symbols, set(UNIVERSES['stock']))

    def test_unfinished_bar_excluded_from_snapshot(self):
        data = json.loads(response('PEPE-USD'))
        result = data['chart']['result'][0]
        result['timestamp'].append(int(NOW.timestamp()))
        for values in result['indicators']['quote'][0].values(): values.append(None)
        snapshot, rows = self.parse(json.dumps(data).encode())
        self.assertEqual(snapshot.provenance.end, '2026-11-02')
        self.assertEqual(len(rows), 220)

    def test_partial_universe_preserves_accepted_pointer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            feed = lambda symbol: (200, response(symbol))
            collect('crypto', root, clock=lambda: NOW, fetch=feed, code_version='test')
            pointer = root/'research/datasets/ingested/crypto-latest.json'
            before = pointer.read_bytes()
            def missing(symbol):
                return (404, b'unsupported?') if symbol == 'PEPE-USD' else feed(symbol)
            import io
            from contextlib import redirect_stdout
            diagnostic = io.StringIO()
            with redirect_stdout(diagnostic), self.assertRaisesRegex(ValueError, 'MISSING_SYMBOLS'):
                collect('crypto', root, clock=lambda: NOW, fetch=missing, code_version='test')
            self.assertIn('crypto PEPE-USD: BLOCKED: PROVIDER_HTTP_404', diagnostic.getvalue())
            self.assertEqual(pointer.read_bytes(), before)
            status = json.loads((root/'work/ingestion/crypto.json').read_text())
            self.assertIn('PROVIDER_HTTP_404', status['symbols']['PEPE-USD']['reason'])
            self.assertEqual(status['status'], 'BLOCKED')

    def test_no_new_data_and_failed_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            kwargs = dict(clock=lambda: NOW, fetch=lambda s: (200,response(s)), code_version='test')
            collect('crypto', root, **kwargs)
            collect('crypto', root, **kwargs)
            status_path = root/'work/ingestion/crypto.json'
            self.assertEqual(json.loads(status_path.read_text())['status'], 'NO_NEW_DATA')
            from data_contracts.ingestion import atomic
            def fail(path, payload):
                if Path(path).name == 'crypto-latest.json': raise OSError('disk failure')
                atomic(path, payload)
            with patch('data_contracts.ingestion.atomic', side_effect=fail), self.assertRaises(OSError):
                collect('crypto', root, **kwargs)
            self.assertEqual(json.loads(status_path.read_text())['publication'], 'FAILED')

    def test_frozen_consumer_checks_symbol_hash_and_freshness(self):
        import os
        from data_contracts.ingestion import accepted_close
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None): return NOW
        with tempfile.TemporaryDirectory() as directory:
            previous = os.getcwd()
            os.chdir(directory)
            try:
                manifest = collect('crypto', clock=lambda: NOW,
                                   fetch=lambda s: (200, response(s)), code_version='test')
                pointer = Path('research/datasets/ingested/crypto-latest.json')
                with patch('data_contracts.ingestion.datetime', Clock):
                    self.assertEqual(len(accepted_close('PEPE-USD', pointer)), 220)
                    path = Path(manifest['snapshots']['PEPE-USD'])
                    path.write_bytes(path.read_bytes() + b' ')
                    with self.assertRaisesRegex(ContractError, 'HASH_MISMATCH'):
                        accepted_close('PEPE-USD', pointer)
            finally:
                os.chdir(previous)

    def test_stock_history_preserves_previous_csv_on_blocked_universe(self):
        import stock_history_research as collector
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'stock_history.csv'
            output.write_bytes(b'previous accepted history\n')
            with patch.object(collector, 'OUT', output), patch.object(
                    collector, 'collect', side_effect=ValueError('MISSING_SYMBOLS: NVDA')):
                with self.assertRaisesRegex(ValueError, 'MISSING_SYMBOLS'):
                    collector.main()
            self.assertEqual(output.read_bytes(), b'previous accepted history\n')

    def test_stock_holiday_and_early_close_contract(self):
        from data_contracts.sessions import sessions
        from zoneinfo import ZoneInfo
        as_of = datetime(2026, 11, 27, 18, 30, tzinfo=timezone.utc)
        days = sessions((as_of-timedelta(days=330)).date(), as_of.date(), 'stock')
        data = json.loads(response('AAPL'))
        result = data['chart']['result'][0]
        result['timestamp'] = [int(datetime.combine(day, datetime.min.time(),
            ZoneInfo('America/New_York')).replace(hour=9,minute=30).timestamp()) for day in days]
        result['indicators']['quote'][0] = {key: [value]*len(days) for key,value in
            [('close',1.0),('high',2.0),('low',0.5),('volume',100)]}
        snapshot, _ = parse(json.dumps(data).encode(), 'AAPL', 'stock', as_of, as_of, 'test')
        self.assertEqual(snapshot.provenance.end, '2026-11-27')
        self.assertNotIn('2026-11-26', [b.session for b in snapshot.bars])

    def test_consumer_rejects_corrupt_linked_export(self):
        import os
        from data_contracts.ingestion import accepted_close
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None): return NOW
        with tempfile.TemporaryDirectory() as directory:
            previous = os.getcwd()
            os.chdir(directory)
            try:
                manifest = collect('crypto', clock=lambda: NOW,
                                   fetch=lambda s: (200, response(s)), code_version='test')
                Path(manifest['export']).write_bytes(b'corrupt export')
                with patch('data_contracts.ingestion.datetime', Clock):
                    with self.assertRaisesRegex(ValueError, 'EXPORT_HASH_MISMATCH'):
                        accepted_close('PEPE-USD', 'research/datasets/ingested/crypto-latest.json')
            finally:
                os.chdir(previous)

    def test_atomic_writers_use_independent_staging_files(self):
        from data_contracts.ingestion import atomic
        import os
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'accepted.json'
            path.write_bytes(b'previous')
            first_ready, second_done = Event(), Event()
            replace = os.replace
            def interleave(source, target):
                if Path(source).read_bytes() == b'first':
                    first_ready.set()
                    if not second_done.wait(5):
                        raise RuntimeError('second writer did not finish')
                replace(source, target)
            with patch('data_contracts.ingestion.os.replace', side_effect=interleave):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    first = pool.submit(atomic, path, b'first')
                    self.assertTrue(first_ready.wait(5))
                    try:
                        atomic(path, b'second')
                    finally:
                        second_done.set()
                    first.result(timeout=5)
            self.assertEqual(path.read_bytes(), b'first')
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_actual_replace_failure_keeps_previous_pointer_and_cleans_staging(self):
        from data_contracts.ingestion import atomic
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'accepted.json'
            path.write_bytes(b'previous')
            with patch('data_contracts.ingestion.os.replace', side_effect=OSError('replace failed')):
                with self.assertRaisesRegex(OSError, 'replace failed'):
                    atomic(path, b'new')
            self.assertEqual(path.read_bytes(), b'previous')
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_stock_publication_rejects_corrupt_export(self):
        import stock_history_research as collector
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root/'stock_history.csv'
            output.write_bytes(b'previous accepted history')
            export = root/('0'*64 + '.csv')
            export.write_bytes(b'corrupt export')
            with patch.object(collector, 'ROOT', root), patch.object(collector, 'OUT', output), patch.object(
                    collector, 'collect', return_value={'export': export.name}):
                with self.assertRaisesRegex(ValueError, 'EXPORT_HASH_MISMATCH'):
                    collector.main()
            self.assertEqual(output.read_bytes(), b'previous accepted history')

    def test_consumer_rejects_stale_bundle_and_corrupt_raw_response(self):
        import os
        from data_contracts.ingestion import accepted_close
        class Tomorrow(datetime):
            @classmethod
            def now(cls, tz=None): return NOW + timedelta(days=1)
        class Today(datetime):
            @classmethod
            def now(cls, tz=None): return NOW
        with tempfile.TemporaryDirectory() as directory:
            previous = os.getcwd()
            os.chdir(directory)
            try:
                manifest = collect('crypto', clock=lambda: NOW,
                                   fetch=lambda s: (200, response(s)), code_version='test')
                pointer = 'research/datasets/ingested/crypto-latest.json'
                with patch('data_contracts.ingestion.datetime', Tomorrow):
                    with self.assertRaisesRegex(ValueError, 'STALE_OR_MISMATCHED_BUNDLE'):
                        accepted_close('PEPE-USD', pointer)
                raw = Path(manifest['symbols']['PEPE-USD']['raw_path'])
                raw.write_bytes(b'corrupt response')
                with patch('data_contracts.ingestion.datetime', Today):
                    with self.assertRaisesRegex(ValueError, 'RAW_HASH_MISMATCH'):
                        accepted_close('PEPE-USD', pointer)
                import crypto_paper_trader as crypto
                import paper_trader as stock
                with patch.dict(os.environ, {'MARKET_DATA_MANIFEST': pointer}), patch.object(
                        crypto.yf, 'download', side_effect=AssertionError('download fallback')):
                    for getter in (crypto.get_close, stock.get_data):
                        with self.assertRaisesRegex(ValueError, 'RAW_HASH_MISMATCH'):
                            getter('PEPE-USD')
            finally:
                os.chdir(previous)
