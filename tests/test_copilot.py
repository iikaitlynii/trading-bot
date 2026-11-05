"""Synthetic security/causality tests. No performance or provider-authenticity claim."""
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from copilot.publish import publish, verified, canonical
from data_contracts.ingestion import collect, archive_bytes, atomic
from data_contracts.sessions import sessions

NOW = datetime(2026, 11, 4, 23, tzinfo=timezone.utc)


def response(symbol):
    days = sessions(datetime(2025, 11, 3).date(), NOW.date(), 'stock')
    n = len(days)
    stamps = [int(datetime(d.year, d.month, d.day, 15, tzinfo=timezone.utc).timestamp()) for d in days]
    quotes = {'close':[100+i for i in range(n)], 'high':[102+i for i in range(n)],
              'low':[98+i for i in range(n)], 'volume':[1000]*n}
    return json.dumps({'chart':{'error':None,'result':[{'meta':{'symbol':symbol},'timestamp':stamps,'indicators':{'quote':[quotes]}}]}}).encode()


class CopilotTests(unittest.TestCase):
    def accepted(self, root):
        return collect('stock', root, clock=lambda:NOW, fetch=lambda s:(200,response(s)), code_version='synthetic-test-only')

    def test_missing_evidence_freezes_wait_without_touching_accounts(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            report=publish(root,NOW)
            self.assertEqual({o['analysis']['state'] for o in report['observations']},{'WAIT'})
            self.assertFalse((root/'paper').exists())
            pointer=json.loads((root/'docs/copilot/latest.json').read_text())
            path=root/'docs/copilot'/pointer['path']
            original=path.read_bytes()
            self.assertEqual(path.stem,hashlib.sha256(original).hexdigest())
            publish(root,NOW+timedelta(minutes=1))
            self.assertEqual(path.read_bytes(),original)
            self.assertEqual(len(list(path.parent.glob('*.json'))),2)
            self.assertEqual(report['observations'][0]['evaluation'],'PENDING — no future outcomes evaluated')

    def test_reparsed_full_universe_supports_directional_paper_scenario(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.accepted(root)
            digest,rows=verified(root,NOW)
            self.assertEqual(set(rows),{'AAPL','MSFT','NVDA','AMZN'})
            first=publish(root,NOW)
            self.assertEqual({o['analysis']['state'] for o in first['observations']},{'BUY'})
            before={p.name:p.read_bytes() for p in (root/'docs/copilot/observations').glob('*.json')}
            publish(root,NOW)
            self.assertEqual(before,{p.name:p.read_bytes() for p in (root/'docs/copilot/observations').glob('*.json')})
            stale=publish(root,NOW+timedelta(days=1))
            self.assertEqual({o['analysis']['state'] for o in stale['observations']},{'WAIT'})

    def test_hash_tamper_and_incomplete_universe_force_wait(self):
        for mode in ('raw','export','snapshot','universe','path','future'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as d:
                root=Path(d);m=self.accepted(root)
                if mode=='raw': path=root/m['symbols']['MSFT']['raw_path'];path.write_bytes(path.read_bytes()+b' ')
                if mode=='export': path=root/m['export'];path.write_bytes(path.read_bytes()+b' ')
                if mode=='snapshot': path=root/m['snapshots']['AAPL'];path.write_bytes(path.read_bytes()+b' ')
                if mode in ('universe','path','future'):
                    if mode=='universe': del m['snapshots']['MSFT']
                    if mode=='path': m['export']='../../private.csv'
                    if mode=='future': m['as_of']=(NOW+timedelta(days=1)).isoformat()
                    payload=canonical(m);archive_bytes(payload,root/'research/datasets/ingested/bundles','.json')
                    atomic(root/'research/datasets/ingested/stock-latest.json',payload)
                report=publish(root,NOW)
                self.assertEqual({o['quality'] for o in report['observations']},{'BLOCKED'})
                self.assertEqual({o['analysis']['state'] for o in report['observations']},{'WAIT'})

    def test_rehashed_export_is_not_enough_to_verify_values(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);m=self.accepted(root)
            payload=(root/m['export']).read_bytes().replace(b',1000\r\n',b',9999\r\n')
            path=archive_bytes(payload,root/'research/datasets/ingested/exports','.csv')
            m['export']=str(path.relative_to(root));payload=canonical(m)
            archive_bytes(payload,root/'research/datasets/ingested/bundles','.json')
            atomic(root/'research/datasets/ingested/stock-latest.json',payload)
            self.assertEqual(publish(root,NOW)['observations'][0]['quality'],'BLOCKED')

    def test_calendar_exhaustion_and_naive_clocks(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(publish(Path(d),datetime(2028,1,5,tzinfo=timezone.utc))['observations'][0]['analysis']['state'],'WAIT')
            with self.assertRaises(ValueError):publish(Path(d),datetime(2026,11,4))
