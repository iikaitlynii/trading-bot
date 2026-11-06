"""Synthetic forward-only examples. Never saved to production account paths."""
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from simulation_v2.model import advance, assumptions, new_account, reconcile
from simulation_v2.store import Store
from simulation_v2.runner import run

HASH = 'a' * 64


def fresh(market='stock', symbols=('A',), costs=None):
    return new_account(market, symbols, '1000', '2026-11-02T22:00:00+00:00', costs)


def step(a, day='02', price='100', signal='BULLISH', hour='22', **kwargs):
    return advance(a, session='2026-11-'+day, observed_at=f'2026-11-{day}T{hour}:00:00+00:00',
                   retrieved_at=f'2026-11-{day}T{hour}:00:00+00:00',
                   prices={s:price for s in a['symbols']}, signals={s:signal for s in a['symbols']},
                   input_hash=HASH, **kwargs)


class ExecutionTests(unittest.TestCase):
    def test_signal_creates_pending_only_then_next_session_gap_fill(self):
        a=step(fresh());self.assertEqual(a['fills'],[]);self.assertEqual(a['cash'],'1000')
        o=a['orders'][0];self.assertEqual(o['signal_session'],'2026-11-02');self.assertEqual(o['status'],'PENDING')
        b=step(a,'03','150');f=b['fills'][0]
        self.assertEqual(f['market_price'],'150');self.assertEqual(f['execution_price'],'150.150')
        self.assertGreater(Decimal(f['fee']),0);self.assertEqual(f['signal_session'],'2026-11-02')
        self.assertTrue(reconcile(b));self.assertLessEqual(-Decimal(f['cash_delta']),Decimal(o['budget']))

    def test_same_session_and_replay_are_idempotent(self):
        a=step(fresh());self.assertEqual(a,step(a,price='999'))
        b=step(a,'03');self.assertEqual(b,step(b,'03'))
        with self.assertRaises(ValueError):step(b)

    def test_delayed_signal_never_selects_price_that_already_existed(self):
        a=fresh();a['created_at']='2026-11-03T22:00:00+00:00'
        a=step(a,'03')
        # A stale source session is not eligible; next actual accepted close is used.
        with self.assertRaises(ValueError):step(a,'02')
        b=step(a,'05','125');self.assertEqual(b['fills'][0]['session'],'2026-11-05')
        self.assertEqual(b['fills'][0]['market_price'],'125')

    def test_missing_price_or_signal_keeps_pending_and_original_bytes(self):
        a=step(fresh());before=deepcopy(a)
        for prices,signals in [({}, {'A':'BULLISH'}),({'A':'NaN'},{'A':'BULLISH'}),({'A':'100'},{'A':'NO_DATA'}),({'A':'0'},{'A':'DEFENSIVE'})]:
            with self.subTest(prices=prices,signals=signals),self.assertRaises(ValueError):
                advance(a,session='2026-11-03',observed_at='2026-11-03T22:00:00Z',retrieved_at='2026-11-03T22:00:00Z',prices=prices,signals=signals,input_hash=HASH)
        self.assertEqual(a,before)

    def test_stock_calendar_weekend_holiday_early_close(self):
        a=step(fresh())
        for day,hour in [('07','22'),('26','22'),('27','17')]:
            with self.subTest(day=day),self.assertRaises(ValueError):step(a,day,hour=hour)
        b=step(a,'27',hour='19');self.assertEqual(b['fills'][0]['price_at'],'2026-11-27T18:00:00+00:00')

    def test_crypto_fills_on_weekend_only_after_completed_utc_day(self):
        a=fresh('crypto');a['created_at']='2026-11-07T01:00:00Z'
        a=advance(a,session='2026-11-06',observed_at='2026-11-07T01:00:00Z',retrieved_at='2026-11-07T01:00:00Z',prices={'A':'100'},signals={'A':'BULLISH'},input_hash=HASH)
        b=advance(a,session='2026-11-07',observed_at='2026-11-08T01:00:00Z',retrieved_at='2026-11-08T01:00:00Z',prices={'A':'110'},signals={'A':'BULLISH'},input_hash=HASH)
        self.assertEqual(b['fills'][0]['price_at'],'2026-11-08T00:00:00+00:00')

    def test_buy_sell_roundtrip_cost_basis_and_equity_identity(self):
        a=step(fresh(costs=assumptions('25','50','1')))
        a=step(a,'03',signal='DEFENSIVE');self.assertEqual(len(a['fills']),1)
        a=step(a,'04',signal='DEFENSIVE');self.assertEqual(len(a['fills']),2)
        self.assertFalse(a['positions']);self.assertLess(Decimal(a['realized_pnl']),0)
        self.assertEqual(Decimal(a['cash'])-1000,Decimal(a['realized_pnl']))
        self.assertEqual(Decimal(a['fees']),sum(Decimal(f['fee']) for f in a['fills']))
        sell=a['fills'][1];self.assertLess(Decimal(sell['execution_price']),Decimal(sell['market_price']))
        self.assertEqual(Decimal(sell['cash_delta']),Decimal(sell['gross'])-Decimal(sell['fee']))

    def test_full_cash_cost_reserves_multiple_orders_and_tiny_units(self):
        a=step(fresh(symbols=('A','B','C','D')),weight='.4',max_invested='1')
        self.assertEqual(sum(Decimal(o['budget']) for o in a['orders']),1000)
        b=step(a,'03',price='0.000000123456789',weight='.4',max_invested='1')
        self.assertGreaterEqual(Decimal(b['cash']),0)
        self.assertEqual(len(b['fills']),3);self.assertTrue(reconcile(b))

    def test_cost_sensitivity_and_expensive_fee_rejection(self):
        equities=[]
        for cost in ('0','10','100'):
            a=step(step(fresh(costs=assumptions(cost,cost))),'03')
            equities.append(Decimal(a['valuations'][-1]['total_equity']))
        self.assertGreater(equities[0],equities[1]);self.assertGreater(equities[1],equities[2])
        a=step(step(fresh(costs=assumptions(fixed_fee='500'))),'03')
        self.assertFalse(a['fills']);self.assertEqual(a['orders'][0]['status'],'REJECTED_COST_OR_QUANTITY')

    def test_tampered_account_fees_fill_duplicate_and_orders_fail_reconciliation(self):
        a=step(step(fresh()),'03')
        mutations=[lambda b:b.update(cash='0'),lambda b:b['fills'].append(deepcopy(b['fills'][0])),
                   lambda b:b['orders'].append(deepcopy(b['orders'][0])),lambda b:b['fills'][0].update(fee='0'),
                   lambda b:b['valuations'][-1].update(unrealized_pnl='999'),lambda b:b['fills'][0].update(price_at='2026-11-02T21:00:00Z')]
        for mutate in mutations:
            b=deepcopy(a);mutate(b)
            with self.subTest(mutate=mutate),self.assertRaises((ValueError,KeyError)):reconcile(b)

    def test_configuration_is_validated(self):
        for fee,slip,fixed in [('-1','0','0'),('0','10000','0'),('NaN','0','0'),('0','0','-1')]:
            with self.assertRaises(ValueError):assumptions(fee,slip,fixed)


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)
        self.store=Store(self.path/'account')
    def crash(self,at):
        def stop(name):
            if name==at:raise InterruptedError(at)
        return stop
    def test_partial_writes_do_not_publish_or_repeat_fills(self):
        with self.store.locked():
            key=self.store.commit(step(fresh()),None)
            before=(self.store.path/'current.json').read_bytes()
            for at in ('state.json','orders.json','fills.json','valuations.json'):
                with self.assertRaises(InterruptedError):self.store.commit(step(self.store.load(),'03'),key,interrupt=self.crash(at))
                self.assertEqual((self.store.path/'current.json').read_bytes(),before)
                self.assertEqual(self.store.load()['fills'],[])
            updated=step(self.store.load(),'03');self.store.commit(updated,key)
            self.assertEqual(len(self.store.load()['fills']),1)
    def test_complete_unpublished_requires_explicit_rollforward(self):
        with self.store.locked():
            key=self.store.commit(step(fresh()),None)
            with self.assertRaises(InterruptedError):self.store.commit(step(self.store.load(),'03'),key,interrupt=self.crash('prepared'))
            self.assertFalse(self.store.load()['fills'])
            with self.assertRaisesRegex(ValueError,'recovery'):self.store.commit(step(self.store.load(),'03'),key)
            candidate=self.store.prepared()[0];self.store.recover(candidate)
            self.assertEqual(len(self.store.load()['fills']),1)
            self.assertEqual(self.store.commit(self.store.load(),candidate),candidate)
    def test_interruption_after_publication_is_already_committed(self):
        with self.store.locked():
            with self.assertRaises(InterruptedError):self.store.commit(step(fresh()),None,interrupt=self.crash('published'))
            self.assertEqual(self.store.load()['last_session'],'2026-11-02');self.assertFalse(self.store.prepared())
    def test_hash_mismatch_recovery_and_competing_lock_fail_closed(self):
        with self.store.locked():
            key=self.store.commit(step(fresh()),None)
            with self.assertRaises(BlockingIOError):
                with Store(self.store.path).locked():pass
            path=self.store.path/'generations'/key/'orders.json';path.write_text('[]')
            with self.assertRaisesRegex(ValueError,'hash'):self.store.load()
    def test_compare_and_swap_and_history_rewrites_rejected(self):
        with self.store.locked():
            key=self.store.commit(step(fresh()),None)
            with self.assertRaises(ValueError):self.store.commit(step(self.store.load(),'03'),'f'*64)
            b=step(self.store.load(),'03');b['valuations'][0]['input_sha256']='b'*64
            with self.assertRaises(ValueError):self.store.commit(b,key)
    def test_production_history_unchanged_and_blocked(self):
        root=Path(__file__).resolve().parents[1]
        paths=[root/folder/name for folder in ('paper','crypto_paper') for name in ('state.json','journal.csv','performance.csv')]
        before=[p.read_bytes() for p in paths]
        for market in ('stock','crypto'):
            with self.assertRaisesRegex(ValueError,'BLOCKED'):run(market,root=root)
        self.assertEqual(before,[p.read_bytes() for p in paths]);self.assertFalse((root/'simulation-v2').exists())

class AcceptedAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
    def inputs(self,now,market='stock',missing=None):
        from datetime import timedelta
        from data_contracts.ingestion import collect
        from data_contracts.sessions import sessions, session_close, latest_completed
        end=latest_completed(now,market);days=sessions(end-timedelta(days=420),end,market)
        def response(symbol):
            n=len(days);values=[10+i for i in range(n)]
            if symbol==missing:values[-1]=None
            stamps=[int(session_close(d,market).timestamp())-(3600 if market=='stock' else 86400) for d in days]
            return 200,json.dumps({'chart':{'error':None,'result':[{'meta':{'symbol':symbol},'timestamp':stamps,'indicators':{'quote':[{'close':values,'high':[11+i for i in range(n)],'low':[9+i for i in range(n)],'volume':[100]*n}]}}]}}).encode()
        return collect(market,self.root,clock=lambda:now,fetch=response,code_version='SYNTHETIC-TEST-ONLY')
    def test_accepted_inputs_create_pending_then_fill_later_and_export(self):
        from simulation_v2.report import build
        now=datetime(2026,11,3,4,tzinfo=timezone.utc);self.inputs(now)
        a=run('stock',root=self.root,now=now);self.assertFalse(a['fills']);self.assertEqual(len(a['orders']),4)
        self.assertEqual(a,run('stock',root=self.root,now=now))
        now=datetime(2026,11,4,4,tzinfo=timezone.utc);self.inputs(now)
        b=run('stock',root=self.root,now=now);self.assertEqual(len(b['fills']),4)
        self.assertTrue(all(f['session']=='2026-11-03' for f in b['fills']))
        report=build(self.root,now);self.assertEqual(report['accounts'][0]['availability'],'SAVED_SIMULATION')
        self.assertEqual(report['accounts'][0]['accounting']['fees'],b['fees'])
    def test_latest_failed_attempt_cannot_use_previous_accepted_pointer(self):
        now=datetime(2026,11,3,4,tzinfo=timezone.utc);self.inputs(now);a=run('stock',root=self.root,now=now)
        with self.assertRaises(ValueError):self.inputs(now,missing='AAPL')
        with self.assertRaisesRegex(ValueError,'ingestion'):run('stock',root=self.root,now=now)
        self.assertEqual(Store(self.root/'simulation-v2/stock').load(),a)
    def test_missing_raw_bytes_blocks_and_keeps_pending(self):
        now=datetime(2026,11,3,4,tzinfo=timezone.utc);self.inputs(now);a=run('stock',root=self.root,now=now)
        next((self.root/'research/datasets/ingested/raw').iterdir()).write_bytes(b'corrupt')
        with self.assertRaises(ValueError):run('stock',root=self.root,now=now)
        self.assertEqual(Store(self.root/'simulation-v2/stock').load(),a)
    def test_risk_configuration_reserves_cash_and_warnings_persist(self):
        a=step(fresh(symbols=('A','B','C','D')),weight='.07',max_invested='.15')
        self.assertEqual([Decimal(o['budget']) for o in a['orders']],[Decimal('70.00'),Decimal('70.00')])
        # Minimum order size leaves the residual $10 unallocated.
        b=step(a,'03','100',weight='.07',max_invested='.15')
        c=step(b,'04','1000',weight='.07',max_invested='.15')
        self.assertTrue(c['valuations'][-1]['risk']['limit_breach'])
        d=step(c,'05','1',weight='.07',max_invested='.15')
        self.assertTrue(d['valuations'][-1]['risk']['drawdown_warning'])
        self.assertTrue(reconcile(d))
    def test_disabled_entry_limits_and_unrounded_fill_prices(self):
        a=step(fresh(),weight='0',max_invested='0');self.assertFalse(a['orders'])
        a=step(fresh());b=step(a,'03','0.000000123456789')
        self.assertEqual(Decimal(b['fills'][0]['market_price']),Decimal('0.000000123456789'))
    def test_recovery_revalidates_exact_archived_inputs(self):
        from simulation_v2.runner import recovery_evidence
        now=datetime(2026,11,3,4,tzinfo=timezone.utc);self.inputs(now);a=run('stock',root=self.root,now=now)
        now=datetime(2026,11,4,4,tzinfo=timezone.utc);self.inputs(now);b=run('stock',root=self.root,now=now)
        recovery_evidence(b,self.root)
        old_hash=a['valuations'][0]['input_sha256']
        (self.root/'research/datasets/ingested/bundles'/(old_hash+'.json')).write_bytes(b'{}')
        with self.assertRaises((ValueError,KeyError,FileNotFoundError)):recovery_evidence(b,self.root)
    def test_cost_changes_cannot_reprice_existing_account(self):
        import os
        now=datetime(2026,11,3,4,tzinfo=timezone.utc);self.inputs(now);a=run('stock',root=self.root,now=now)
        with patch.dict(os.environ, SIM_FEE_BPS='100'):
            with self.assertRaisesRegex(ValueError,'configuration'):run('stock',root=self.root,now=now)
        self.assertEqual(Store(self.root/'simulation-v2/stock').load(),a)
    def test_consumer_freezes_verified_bundle_across_pointer_replacement(self):
        from simulation_v2.runner import accepted
        now=datetime(2026,11,3,4,tzinfo=timezone.utc);self.inputs(now)
        def replacing_pointer(*args,**kwargs):
            verified=accepted(*args,**kwargs)
            (self.root/'research/datasets/ingested/stock-latest.json').write_bytes(b'concurrent pointer replacement')
            return verified
        with patch('simulation_v2.runner.accepted',side_effect=replacing_pointer):
            a=run('stock',root=self.root,now=now)
        self.assertEqual(len(a['orders']),4);self.assertFalse(a['fills']);self.assertTrue(reconcile(a))
