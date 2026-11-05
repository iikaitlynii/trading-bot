"""Entirely synthetic temporary accounts; production history is never changed."""
import csv
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from monitoring.account_health import build, row, digest, account_files, next_close, REPO, BASE
from data_contracts.ingestion import collect, UNIVERSES
from data_contracts.sessions import sessions, session_close

NOW = datetime(2026, 11, 3, 4, tzinfo=timezone.utc)


def fixture(root, market='stock'):
    end = datetime(2026,11,2).date()
    days = sessions(end-timedelta(days=420), end, market)
    def response(symbol):
        stamps = [int(session_close(d, market).timestamp()) - (3600 if market == 'stock' else 86400) for d in days]
        return 200,json.dumps({'chart': {'error':None,'result':[{'meta':{'symbol':symbol},'timestamp':stamps,'indicators':{'quote':[{'close':[1.0]*len(days),'high':[2.0]*len(days),'low':[.5]*len(days),'volume':[100]*len(days)}]}}]}}).encode()
    collect(market,root,clock=lambda:NOW,fetch=response,code_version='explicit-synthetic-test')
    starting = 10000 if market == 'stock' else 5000
    folder = 'paper' if market == 'stock' else 'crypto_paper'
    p=root/folder;p.mkdir()
    (p/'state.json').write_text(json.dumps({'cash':starting,'positions':{},'last_run_date':'2026-11-02','last_price_session':'2026-11-02'}))
    (p/'performance.csv').write_text(f'date_utc,paper_value,cash,open_positions\n2026-11-02,{starting},{starting},0\n')
    (p/'journal.csv').write_text('date_utc,ticker,action,price,shares,units,reason\n')
    (p/'latest_signals.csv').write_text('ticker,price_session,close,signal\n'+''.join(s+',2026-11-02,1,HOLD\n' for s in UNIVERSES[market]))
    receipt={'schema_version':1,'session':'2026-11-02','bundle_sha256':digest(root/f'research/datasets/ingested/{market}-latest.json'),
             'files':{p:digest(root/p) for p in account_files(market)},'publication':'CONFIRMED','simulation':'success','outcome':'ADVANCED',
             'last_advancement':'2026-11-02','run_id':42,'run_attempt':1,'checked_at':NOW.isoformat()}
    target=root/f'monitoring/account_receipts/{market}.json';target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(receipt))
    target=root/f'monitoring/ingestion/{market}.json';target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/f'work/ingestion/{market}.json',target)
    workflow = 'paper-trading.yml' if market=='stock' else 'crypto-paper-trading.yml'
    return {workflow:{'status':'SUCCESS','run_id':42,'run_attempt':1,'url':BASE+'/actions/runs/42'}}


class AccountHealthTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.actions=fixture(self.root)
    def health(self,now=NOW,market='stock'):
        return row(self.root,market,now,self.actions)
    def receipt(self,**changes):
        p=self.root/'monitoring/account_receipts/stock.json';r=json.loads(p.read_text());r.update(changes);p.write_text(json.dumps(r))
    def test_active_requires_all_independent_evidence(self):
        h=self.health();self.assertEqual(h['status'],'ACTIVE');self.assertEqual(h['last_verified_data_session'],'2026-11-02')
    def test_already_processed_paused_and_advancement_retained(self):
        self.receipt(outcome='ALREADY_PROCESSED');h=self.health();self.assertEqual(h['status'],'PAUSED');self.assertEqual(h['last_successful_account_advancement'],'2026-11-02')
    def test_stock_weekend_and_crypto_continuous_boundaries(self):
        fri=datetime(2026,11,6,22,tzinfo=timezone.utc)
        self.assertEqual(next_close(fri,'stock').isoformat(),'2026-11-09T21:00:00+00:00')
        self.assertEqual(next_close(fri,'crypto').isoformat(),'2026-11-07T00:00:00+00:00')
        early=datetime(2026,11,27,17,tzinfo=timezone.utc)
        self.assertEqual(next_close(early,'stock').isoformat(),'2026-11-27T18:00:00+00:00')
    def test_next_due_session_blocks_old_evidence(self):
        self.assertEqual(self.health(datetime(2026,11,3,21,tzinfo=timezone.utc))['status'],'BLOCKED')
    def test_unknown_or_successful_workflow_alone_blocked(self):
        self.actions={};self.assertEqual(self.health()['status'],'BLOCKED')
        self.actions={'paper-trading.yml':{'status':'SUCCESS'}};self.assertEqual(self.health()['status'],'BLOCKED')
    def test_missing_publication_confirmation(self):
        (self.root/'monitoring/account_receipts/stock.json').unlink();self.assertIn('PUBLICATION_UNCONFIRMED',self.health()['reason_codes'])
    def test_failed_publication_wrong_run_and_rerun_block(self):
        for changes in [{'publication':'FAILED'},{'run_id':7},{'run_attempt':2},{'simulation':'skipped'},{'outcome':'UNKNOWN'}]:
            with self.subTest(changes=changes):
                self.receipt(**changes);self.assertEqual(self.health()['status'],'BLOCKED')
                self.receipt(publication='CONFIRMED',run_id=42,run_attempt=1,simulation='success',outcome='ADVANCED')
    def test_duplicate_ledger_blocks_and_is_preserved(self):
        p=self.root/'paper/performance.csv';p.write_text(p.read_text()+'2026-11-02,10000,10000,0\n');before=p.read_bytes()
        self.assertIn('ACCOUNT_INVALID_OR_STALE',self.health()['reason_codes']);self.assertEqual(p.read_bytes(),before)
    def test_account_balance_or_hash_changes_block(self):
        p=self.root/'paper/state.json';s=json.loads(p.read_text());s['cash']=9999;p.write_text(json.dumps(s));self.assertEqual(self.health()['status'],'BLOCKED')
    def test_missing_raw_and_corrupt_bundle_block(self):
        p=next((self.root/'research/datasets/ingested/raw').glob('*'));p.write_bytes(b'bad');self.assertEqual(self.health()['status'],'BLOCKED')
    def test_latest_failed_ingestion_cannot_hide_behind_accepted_pointer(self):
        p=self.root/'monitoring/ingestion/stock.json';s=json.loads(p.read_text());s['status']='BLOCKED';s['reason']='provider null close';p.write_text(json.dumps(s));self.assertEqual(self.health()['status'],'BLOCKED')
    def test_missing_ingestion_evidence_blocked(self):
        (self.root/'monitoring/ingestion/stock.json').unlink();self.assertEqual(self.health()['status'],'BLOCKED')
    def test_future_and_unsupported_calendar_block(self):
        self.receipt(checked_at='2027-01-01T00:00:00Z');self.assertEqual(self.health()['status'],'BLOCKED')
        self.assertIn('CALENDAR_UNSUPPORTED',self.health(datetime(2028,2,1,tzinfo=timezone.utc))['reason_codes'])
    def test_forward_unknowns_default_blocked_with_four_accounts(self):
        h=build(self.root,NOW,self.actions)['accounts'][-1];self.assertEqual(h['status'],'BLOCKED');self.assertEqual(len(h['accounts']),4)
    def test_crypto_active_expires_at_utc_midnight(self):
        actions=fixture(self.root,'crypto');self.actions=actions
        self.assertEqual(self.health(market='crypto')['status'],'ACTIVE')
        self.assertEqual(self.health(datetime(2026,11,4,tzinfo=timezone.utc),market='crypto')['status'],'BLOCKED')
    def test_production_legacy_duplicates_are_not_repaired(self):
        root=Path(__file__).resolve().parents[1];paths=account_files('stock')+account_files('crypto');before={p:digest(root/p) for p in paths}
        h=build(root,NOW,{})
        self.assertTrue(all(a['status']=='BLOCKED' for a in h['accounts']))
        self.assertEqual(before,{p:digest(root/p) for p in paths})

    def test_historical_recovery_inventory_cannot_be_overridden_by_fresh_inputs(self):
        p=self.root/'research/reliability/recovery-v1/investigation.json';p.parent.mkdir(parents=True)
        p.write_text(json.dumps({'schema_version':1,'status':'BLOCKED','stock_rows':[{'status':'UNRESOLVED'}],'reason':'Unresolved original sessions'}))
        self.assertIn('HISTORICAL_RECONCILIATION_REQUIRED',self.health()['reason_codes'])
    def test_missing_or_unreconciled_journal_blocks(self):
        p=self.root/'paper/journal.csv';p.write_text('wrong,header\n')
        self.assertIn('ACCOUNT_INVALID_OR_STALE',self.health()['reason_codes'])
        p.write_text('date_utc,ticker,action,price,shares\n2026-11-02,AAPL,SIM_BUY,1,10\n')
        self.assertIn('ACCOUNT_INVALID_OR_STALE',self.health()['reason_codes'])
    def test_skipped_simulation_removes_current_receipt_and_preserves_ingestion(self):
        import os
        from monitoring.account_health import record
        previous=Path.cwd()
        try:
            os.chdir(self.root)
            record('stock','skipped','success')
        finally:
            os.chdir(previous)
        self.assertFalse((self.root/'monitoring/account_receipts/stock.json').exists())
        self.assertTrue((self.root/'monitoring/ingestion/stock.json').exists())
    def test_receipt_records_committed_bytes_and_already_processed(self):
        import os
        from unittest.mock import patch
        from monitoring.account_health import capture,record
        class Clock(datetime):
            @classmethod
            def now(cls,tz=None):return NOW
        def git(*args):
            return (self.root/args[1].split('HEAD:',1)[1]).read_bytes() if args[0]=='show' else b'abc123\n'
        previous=Path.cwd()
        try:
            os.chdir(self.root)
            with patch('monitoring.account_health.datetime',Clock),patch('monitoring.account_health.git',git),patch.dict(os.environ,GITHUB_RUN_ID='42',GITHUB_RUN_ATTEMPT='1'):
                capture('stock');record('stock','success','success')
        finally:
            os.chdir(previous)
        self.assertEqual(self.health()['status'],'PAUSED')
        receipt=json.loads((self.root/'monitoring/account_receipts/stock.json').read_text())
        self.assertEqual(receipt['output_commit'],'abc123')
        self.assertEqual(receipt['files'],{p:digest(self.root/p) for p in account_files('stock')})
