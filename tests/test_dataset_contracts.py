"""Offline synthetic evidence only; never execute a paper trader or fetch prices."""
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from data_contracts import (Bar, ContractError, Provenance, build, canonical, digest,
                            endpoint, load, save, validate, validate_comparison)
from data_contracts.sessions import latest_completed, session_close, sessions


def fixture(market='stock', symbol='SPY', start='2026-07-01', end='2026-07-02',
            as_of='2026-07-03T18:00:00+00:00'):
    p = Provenance(symbol, market, endpoint(symbol), as_of, as_of, start, end,
                   'raw_close', (('python', '3.11'),), 'synthetic-v1',
                   'synthetic illustrative fixture')
    bars = [Bar(d.isoformat(), 100.0 + i) for i, d in enumerate(
        sessions(date.fromisoformat(start), date.fromisoformat(end), market))]
    return build(p, bars)


class SessionTests(unittest.TestCase):
    def test_holidays_weekend_and_special_closure(self):
        for day in ['2026-07-03', '2026-07-04', '2025-01-09', '2025-04-18',
                    '2027-06-18', '2027-12-24']:
            with self.subTest(day=day):
                self.assertIsNone(session_close(date.fromisoformat(day), 'stock'))
        self.assertEqual(latest_completed(datetime.fromisoformat('2026-07-05T23:00:00+00:00'), 'stock'), date(2026, 7, 2))

    def test_early_close_exact_boundary(self):
        for instant, expected in [('2026-11-27T17:59:59+00:00', '2026-11-25'),
                                  ('2026-11-27T18:00:00+00:00', '2026-11-27')]:
            self.assertEqual(latest_completed(datetime.fromisoformat(instant), 'stock').isoformat(), expected)
        self.assertEqual(session_close(date(2025, 7, 3), 'stock').hour, 17)

    def test_dst_and_regular_close_boundary(self):
        self.assertEqual(session_close(date(2026, 3, 6), 'stock').hour, 21)
        self.assertEqual(session_close(date(2026, 3, 9), 'stock').hour, 20)
        self.assertEqual(latest_completed(datetime.fromisoformat('2026-03-09T19:59:59+00:00'), 'stock'), date(2026, 3, 6))
        self.assertEqual(latest_completed(datetime.fromisoformat('2026-03-09T16:00:00-04:00'), 'stock'), date(2026, 3, 9))

    def test_crypto_utc_weekend_leap_day_and_boundary(self):
        for instant, expected in [('2026-07-05T23:59:59+00:00', '2026-07-04'),
                                  ('2026-07-06T00:00:00+00:00', '2026-07-05'),
                                  ('2024-03-01T00:00:00+00:00', '2024-02-29'),
                                  ('2026-07-05T19:00:00-05:00', '2026-07-05')]:
            self.assertEqual(latest_completed(datetime.fromisoformat(instant), 'crypto').isoformat(), expected)

    def test_unknown_calendar_and_naive_time_fail_closed(self):
        for market, instant in [('stock', '2028-01-03T22:00:00+00:00'), ('stock', '2026-07-03T18:00:00'), ('other', '2026-07-03T18:00:00+00:00')]:
            with self.assertRaises(ValueError):
                latest_completed(datetime.fromisoformat(instant), market)

    def test_new_year_saturday_holiday_does_not_close_december_31(self):
        # NYSE does not observe a Saturday New Year on the preceding Friday.
        self.assertIsNotNone(session_close(date(2027, 12, 31), 'stock'))


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.s = fixture()

    def test_valid_stock_crypto_and_btc(self):
        self.assertEqual(validate(self.s), ())
        for symbol in ['ETH-USD', 'BTC-USD']:
            s = fixture('crypto', symbol, '2026-07-01', '2026-07-02', '2026-07-03T00:00:00+00:00')
            self.assertEqual(validate(s), ())

    def test_omitted_first_middle_last_and_empty_sessions(self):
        s = fixture(start='2026-06-29')
        for index in range(len(s.bars)):
            with self.subTest(index=index):
                self.assertIn('MISSING', validate(replace(s, bars=s.bars[:index] + s.bars[index+1:])))
        self.assertIn('MISSING', validate(replace(s, bars=())))
        self.assertIn('STALE', validate(replace(s, bars=s.bars[:-1])))

    def test_stale_even_with_new_retrieval_time(self):
        p = replace(self.s.provenance, retrieved_at='2026-07-06T22:00:00+00:00', as_of='2026-07-06T22:00:00+00:00')
        self.assertIn('STALE', validate(replace(self.s, provenance=p)))

    def test_unfinished_stock_and_crypto_rejected(self):
        stock = replace(self.s, provenance=replace(self.s.provenance, as_of='2026-07-02T19:59:59+00:00'))
        self.assertIn('UNFINISHED', validate(stock))
        crypto = fixture('crypto', 'BTC-USD', as_of='2026-07-03T00:00:00+00:00')
        self.assertIn('UNFINISHED', validate(replace(crypto, provenance=replace(crypto.provenance, as_of='2026-07-02T23:59:59+00:00'))))

    def test_invalid_dates_duplicates_order_and_prices(self):
        for value in [float('nan'), float('inf'), -1, 0, True, '100']:
            with self.subTest(value=value):
                self.assertIn('INVALID_PRICE', validate(replace(self.s, bars=(replace(self.s.bars[0], close=value),) + self.s.bars[1:])))
        self.assertIn('DUPLICATE', validate(replace(self.s, bars=self.s.bars + self.s.bars)))
        self.assertIn('UNSORTED', validate(replace(self.s, bars=self.s.bars[::-1])))
        self.assertIn('INVALID_SESSION', validate(replace(self.s, bars=self.s.bars + (Bar('2026-07-03', 1),))))
        self.assertTrue(validate(replace(self.s, bars=(Bar('not-a-date', 1),))))

    def test_metadata_endpoint_clock_basis_and_calendar_rejected(self):
        for changes in [dict(source_url=endpoint('QQQ')), dict(adjustment='unknown'),
                        dict(retrieved_at='2026-07-01T00:00:00+00:00'),
                        dict(as_of='2026-07-03T18:00:00'), dict(dependencies=()),
                        dict(dependencies=(('python', '3'), ('python', '4'))), dict(code_version='')]:
            with self.subTest(changes=changes):
                self.assertTrue(validate(replace(self.s, provenance=replace(self.s.provenance, **changes))))
        self.assertTrue(validate(replace(self.s, timezone='UTC')))
        self.assertTrue(validate(replace(self.s, calendar_version='unknown')))
        self.assertEqual(endpoint('BRK/B'), 'https://query1.finance.yahoo.com/v8/finance/chart/BRK%2FB')

    def test_mixed_asof_adjustment_windows_or_evidence_rejected(self):
        other = fixture(symbol='QQQ')
        self.assertEqual(len(validate_comparison([self.s, other])), 2)
        for changes in [dict(as_of='2026-07-03T17:00:00+00:00'),
                        dict(adjustment='adjusted_close'), dict(classification='historical research')]:
            with self.assertRaisesRegex(ContractError, 'MISMATCHED_COMPARISON'):
                validate_comparison([self.s, replace(other, provenance=replace(other.provenance, **changes))])
        with self.assertRaisesRegex(ContractError, 'MISMATCHED_COMPARISON'):
            validate_comparison([self.s, fixture(symbol='QQQ', start='2026-06-30')])
        with self.assertRaisesRegex(ContractError, 'DUPLICATE_SYMBOL'):
            validate_comparison([self.s, self.s])
        with self.assertRaises(ContractError):
            validate_comparison([])

    def test_immutable_canonical_hash_and_archive_roundtrip(self):
        with self.assertRaises(FrozenInstanceError):
            self.s.bars[0].close = 0
        self.assertEqual(digest(self.s), hashlib.sha256(canonical(self.s)).hexdigest())
        with tempfile.TemporaryDirectory() as directory:
            path = save(self.s, directory)
            self.assertEqual(load(path), self.s)
            self.assertEqual(save(self.s, directory), path)
            modified = replace(self.s, bars=(Bar('2026-07-01', 101),) + self.s.bars[1:])
            self.assertNotEqual(save(modified, directory), path)
            self.assertNotEqual(digest(replace(self.s, provenance=replace(self.s.provenance, code_version='v2'))), digest(self.s))
            path.write_bytes(path.read_bytes().replace(b'100.0', b'999.0'))
            with self.assertRaisesRegex(ContractError, 'HASH_MISMATCH'):
                load(path)
            with self.assertRaisesRegex(ContractError, 'HASH_MISMATCH'):
                save(self.s, directory)

    def test_invalid_snapshot_cannot_be_archived(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ContractError):
                save(replace(self.s, bars=()), directory)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_crypto_missing_interior_and_weekend_are_expected(self):
        s = fixture('crypto', 'BTC-USD', '2026-07-03', '2026-07-06', '2026-07-07T00:00:00+00:00')
        for index in [1, 2]:
            self.assertIn('MISSING', validate(replace(s, bars=s.bars[:index] + s.bars[index+1:])))
        with self.assertRaises(ContractError):
            build(s.provenance, s.bars[:-1])

    def test_rehashed_invalid_provenance_still_rejected_on_load(self):
        data = json.loads(canonical(self.s))
        data['provenance']['source_url'] = endpoint('QQQ')
        payload = (json.dumps(data, sort_keys=True, separators=(',', ':')) + '\n').encode()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / (hashlib.sha256(payload).hexdigest() + '.json')
            path.write_bytes(payload)
            with self.assertRaisesRegex(ContractError, 'endpoint/symbol'):
                load(path)

    def test_unreviewed_range_and_noncanonical_dates_rejected(self):
        p = replace(self.s.provenance, start='2023-12-29')
        self.assertTrue(any('unsupported XNYS' in issue for issue in validate(replace(self.s, provenance=p))))
        self.assertTrue(validate(replace(self.s, bars=(Bar('20260701', 100),) + self.s.bars[1:])))
        with self.assertRaises(ValueError):
            sessions(date(2026, 7, 2), date(2026, 7, 1), 'stock')

    def test_checked_in_snapshots_and_manifest(self):
        root = Path(__file__).resolve().parents[1] / 'research/datasets'
        manifest = json.loads((root / 'fixtures.json').read_text())
        self.assertEqual(set(manifest), {'SPY', 'ETH-USD', 'BTC-USD'})
        for symbol, filename in manifest.items():
            snapshot = load(root / filename)
            self.assertEqual(snapshot.provenance.symbol, symbol)
            self.assertEqual(snapshot.provenance.classification, 'synthetic illustrative fixture')


if __name__ == '__main__':
    unittest.main()
