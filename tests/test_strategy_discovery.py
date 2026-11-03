import copy
import unittest
from pathlib import Path
from unittest.mock import patch

from strategy_discovery.lab import approve, configuration, digest, discover, extract, load
from strategy_discovery.evaluate import evaluate, synthetic_prices, baselines, submission, research_rank

ROOT = Path(__file__).resolve().parents[1] / 'strategy_discovery'


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.sources = load(ROOT/'samples/transcripts.json')
        self.spec = load(ROOT/'specifications/demo.json')

    def test_metadata_search_and_timestamp_provenance(self):
        hits = discover(load(ROOT/'samples/metadata.json'), 'educational sma')
        self.assertEqual(len(hits), 1)
        candidate = extract(self.sources[0])
        self.assertEqual(candidate['status'], 'needs_human_review')
        self.assertEqual(candidate['source_sha256'], digest(self.sources[0]))
        self.assertEqual(candidate['evidence']['risk'][0]['url'], self.sources[0]['video_url']+'&t=40')
        self.assertEqual(candidate['config']['max_weight'], .15)

    def test_permission_required(self):
        for permission in ({}, {'basis':'public video', 'reference':'public visibility'}, {'basis':'creator permission'}):
            source=copy.deepcopy(self.sources[0]);source['permission']=permission
            with self.assertRaises(ValueError): extract(source)

    def test_missing_ambiguous_conflicting_and_injection_are_blocked(self):
        sources = [self.sources[1]]
        for change in ('missing', 'duplicate', 'injection', 'negated'):
            s=copy.deepcopy(self.sources[0])
            if change=='missing': s['segments'].pop()
            else:
                text={'duplicate':s['segments'][0]['text'], 'injection':"__import__('os').system('touch /tmp/unsafe-discovery')", 'negated':'Do not use Entry: close above regime SMA and fast SMA above slow SMA.'}[change]
                s['segments'].append(dict(start=60,end=68,text=text))
            sources.append(s)
        for source in sources:
            candidate=extract(source)
            self.assertTrue(candidate['uncertainties'])
            review=dict(self.spec['review'], candidate_sha256=digest(candidate))
            with self.assertRaises(ValueError): approve(candidate,review)

    def test_review_hash_identity_and_candidate_integrity(self):
        self.assertEqual(configuration(self.spec)['fast'], 10)
        for field,value in [('reviewer',''),('candidate_sha256','bad'),('decision','pending')]:
            spec=copy.deepcopy(self.spec);spec['review'][field]=value
            with self.assertRaises(ValueError): configuration(spec)
        for change in ('config', 'uncertainties', 'template', 'code'):
            spec=copy.deepcopy(self.spec)
            if change=='config':spec['candidate']['config']['fast']=11
            elif change=='uncertainties':spec['candidate']['uncertainties']=['unresolved']
            elif change=='template':spec['template']='arbitrary_python'
            else:spec['code']='print(1)'
            with self.assertRaises(ValueError): configuration(spec)

    def test_invalid_times_risk_and_periods_fail_closed(self):
        for start,end in [(float('nan'),8),(0,float('inf')),(-1,8),(8,8)]:
            s=copy.deepcopy(self.sources[0]);s['segments'][0].update(start=start,end=end)
            with self.assertRaises(ValueError): extract(s)
        for text in ['Risk: stop 0 percent below entry fill; max weight 15 percent.',
                     'Risk: stop 3 percent below entry fill; max weight 100 percent.',
                     'Indicators: SMA(30), SMA(10), SMA(150).']:
            s=copy.deepcopy(self.sources[0]);s['segments'][4 if text.startswith('Risk') else 1]['text']=text
            self.assertTrue(extract(s)['uncertainties'])

    def test_offline_reproducibility_and_fixed_periods(self):
        with patch('yfinance.download', side_effect=AssertionError('network forbidden')):
            a=evaluate(self.spec,synthetic_prices());b=evaluate(self.spec,synthetic_prices())
        self.assertEqual(a,b)
        self.assertEqual(a['periods']['train']['end'],'2021-01-04')
        self.assertLess(a['periods']['selection']['end'],a['periods']['evaluation']['start'])
        self.assertEqual(submission(self.spec,a)['status'],'blocked_pending_human_integration')
        self.assertFalse(a['robustness']['historical_evidence'])

    def test_future_changes_do_not_affect_prior_engine_results(self):
        from strategy_discovery.evaluate import _run
        prices=synthetic_prices();changed=prices.copy();changed.iloc[490:]*=2
        cfg=configuration(self.spec)
        self.assertEqual(_run(prices,cfg,370,490),_run(changed,cfg,370,490))

    def test_bad_or_real_data_cannot_enter_prototype(self):
        prices=synthetic_prices()
        for value in (None,0,float('inf'),float('nan')):
            changed=prices.copy();changed.iloc[500,0]=value
            with self.assertRaises(ValueError): evaluate(self.spec,changed)
        with self.assertRaises(ValueError): evaluate(self.spec,prices.iloc[:-1])
        changed=prices.copy();changed.iloc[500,0]*=1.01
        with self.assertRaises(ValueError): evaluate(self.spec,changed)

    def test_costs_baselines_and_existing_framework_parity(self):
        import research_lab as engine
        from strategy_discovery.evaluate import _run
        cfg=configuration(self.spec);prices=synthetic_prices()
        self.assertEqual(_run(prices,cfg,490,610),engine.run_variant(prices.iloc[340:610],cfg))
        baseline=baselines(prices,490,610)
        expected=(prices.iloc[609,0]/prices.iloc[490,0]*(1-.001)/(1+.001)-1)*100
        self.assertAlmostEqual(baseline['buy_hold']['return_pct'],expected,places=4)
        self.assertEqual(baseline['cash']['return_pct'],0)
        self.assertIn('trend_return_pct',baseline['existing_trend'])
        # Independent entry accounting: one 15% allocation, entry fee/slippage once.
        import pandas as pd
        ramp=pd.DataFrame({'SYNTH':[100.+i for i in range(153)]})
        actual=engine.run_variant(ramp,cfg)
        shares=1500*.999/(250*1.001)
        expected=(8500+shares*252)/10000*100-100
        self.assertAlmostEqual(actual['return_pct'],expected,places=4)
        flat=pd.DataFrame({'SYNTH':[100.]*300})
        # Flat indicators prevent entries: no missing-data-as-sell or fabricated trades.
        r=engine.run_variant(flat,cfg)
        self.assertEqual(r['return_pct'],0)

    def test_rank_does_not_reward_profit(self):
        c=extract(self.sources[0]);result=evaluate(self.spec,synthetic_prices())
        rank=research_rank(c,result)
        changed=copy.deepcopy(result)
        changed['periods']['evaluation']['candidate']['return_pct']=999999
        self.assertEqual(research_rank(c,changed),rank)
        self.assertGreater(rank['score'],research_rank(extract(self.sources[1]))['score'])



class DashboardTests(unittest.TestCase):
    def test_escapes_untrusted_transcript_and_title(self):
        from strategy_discovery.dashboard import render
        report=load(ROOT/'demo_report.json')
        report['candidates'][0]['candidate']['source']['title']='<script>alert(1)</script>'
        report['candidates'][0]['candidate']['evidence']['entry'][0]['quote']='<img src=x onerror=alert(1)>'
        html=render(report)
        self.assertNotIn('<script>',html)
        self.assertNotIn('<img',html)
        self.assertIn('&lt;script&gt;',html)
        self.assertIn('blocked_pending_human_integration',html)


if __name__=='__main__': unittest.main()
