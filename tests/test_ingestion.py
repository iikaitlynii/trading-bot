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
            with self.assertRaisesRegex(ValueError, 'MISSING_SYMBOLS'):
                collect('crypto', root, clock=lambda: NOW, fetch=missing, code_version='test')
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
