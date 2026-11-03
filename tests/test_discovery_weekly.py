"""Offline weekly evidence, archive and dashboard contracts."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from strategy_discovery.lab import encoded, load
from strategy_discovery.weekly import archive_index, build_report, publish, validate_report

ROOT = Path(__file__).resolve().parents[1]


def ledger(simulation=False):
    sources = load(ROOT/'strategy_discovery/samples/transcripts.json')
    reviews = [dict(reviewed_at='2026-10-25T02:00:00Z', reviewer='test fixture reviewer', source=s) for s in sources]
    if simulation:
        reviews[0]['specification'] = load(ROOT/'strategy_discovery/specifications/demo.json')
    return dict(schema_version=1, reviews=reviews)


def report(simulation=False, start='2026-10-19'):
    return build_report(ledger(simulation), start, '2026-10-26T03:00:00Z')


class WeeklyEvidenceTests(unittest.TestCase):
    def test_empty_run_is_distinct_from_not_run_and_no_fixture_auto_import(self):
        r = build_report({'schema_version': 1, 'reviews': []}, '2026-10-19', '2026-10-26T03:00:00Z')
        self.assertEqual(r['activity_state'], 'EMPTY')
        self.assertEqual(r['simulation_state'], 'NOT RUN')
        self.assertEqual(r['historical_state'], 'UNVALIDATED')
        self.assertEqual(r['counts'], dict(sources_reviewed=0, candidates=0, ambiguous=0, simulations=0))
        self.assertEqual(load(ROOT/'docs/strategy-discovery/index.json')['reports'], [])

    def test_dated_review_counts_ambiguities_and_rankings_without_simulation(self):
        r = report()
        self.assertEqual(r['counts'],dict(sources_reviewed=2,candidates=2,ambiguous=1,simulations=0))
        self.assertEqual(r['simulation_state'],'NOT RUN')
        self.assertEqual({s['source_sha256'] for s in r['sources']},{c['candidate']['source_sha256'] for c in r['candidates']})
        self.assertIn('SYNTHETIC FIXTURES ONLY',r['scope'])
        self.assertEqual(r['candidates'][0]['candidate']['status'],'needs_human_review')

    def test_simulation_is_recomputed_offline_and_not_historical(self):
        with patch('yfinance.download',side_effect=AssertionError('no network')):
            r=report(True)
        self.assertEqual(r['counts']['simulations'],1)
        c=next(c for c in r['candidates'] if c['result'])
        self.assertEqual(c['simulation_state'],'UNVALIDATED')
        self.assertEqual(c['result']['evidence'],'illustrative synthetic simulation')
        self.assertGreater(c['quality']['score'],r['candidates'][1]['quality']['score'])
        self.assertEqual(validate_report(r),r)

    def test_time_boundaries_do_not_count_activity_in_other_weeks(self):
        l=ledger();l['reviews'][1]['reviewed_at']='2026-10-26T00:00:00Z'
        r=build_report(l,'2026-10-19','2026-10-26T03:00:00Z')
        self.assertEqual(r['counts']['sources_reviewed'],1)
        self.assertEqual(r['week_end'],'2026-10-25')
        self.assertEqual(build_report(l,'2026-10-12','2026-10-26T03:00:00Z')['activity_state'],'EMPTY')

    def test_future_unfinished_or_invalid_week_rejected(self):
        for start,generated in [('2026-10-20','2026-10-26T00:00:00Z'),('2026-10-19','2026-10-25T23:59:59Z'),('2026-10-19','2099-01-01T00:00:00Z'),('2026-10-19','2026-10-26T00:00:00')]:
            with self.assertRaises(ValueError):build_report(ledger(),start,generated)
        l=ledger();l['reviews'][0]['reviewed_at']='2026-10-27T00:00:00Z'
        with self.assertRaises(ValueError):build_report(l,'2026-10-19','2026-10-26T00:00:00Z')
        l=ledger();l['reviews'][0]['reviewed_at']='2026-10-24T00:00:00Z'
        with self.assertRaises(ValueError):build_report(l,'2026-10-19','2026-10-26T00:00:00Z')

    def test_real_source_claims_and_supplied_performance_fail_closed(self):
        for change in ('real','permission','result','historical','reviewer','duplicate'):
            l=ledger()
            if change=='real':l['reviews'][0]['source']['synthetic']=False
            if change=='permission':l['reviews'][0]['source']['permission']['basis']='public video'
            if change=='result':l['reviews'][0]['result']={'return_pct':999}
            if change=='historical':l['reviews'][0]['evidence']='historical'
            if change=='reviewer':l['reviews'][0]['reviewer']=''
            if change=='duplicate':l['reviews'].append(copy.deepcopy(l['reviews'][0]))
            with self.subTest(change=change),self.assertRaises(ValueError):build_report(l,'2026-10-19','2026-10-26T03:00:00Z')

    def test_tampered_reports_and_unreviewed_specs_are_rejected(self):
        for field,value in [('counts',{}),('historical_state','VALIDATED'),('simulation_state','COMPLETE')]:
            r=report();r[field]=value
            with self.assertRaises(ValueError):validate_report(r)
        l=ledger(True);l['reviews'][0]['specification']['candidate']['config']['fast']=11
        with self.assertRaises(ValueError):build_report(l,'2026-10-19','2026-10-26T03:00:00Z')
        l=ledger(True);l['reviews'][1]['specification']=l['reviews'][0]['specification']
        with self.assertRaises(ValueError):build_report(l,'2026-10-19','2026-10-26T03:00:00Z')


class WeeklyArchiveTests(unittest.TestCase):
    def test_archive_missing_empty_sorted_immutable_and_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            self.assertEqual(archive_index(root)['reports'],[])
            latest=report();index=publish(latest,root)
            raw=(root/'index.json').read_bytes()
            self.assertEqual(publish(latest,root),index)
            self.assertEqual((root/'index.json').read_bytes(),raw)
            older=report(start='2026-10-12');publish(older,root)
            self.assertEqual([e['week_start'] for e in archive_index(root)['reports']],['2026-10-19','2026-10-12'])
            changed=build_report({'schema_version':1,'reviews':[]},'2026-10-19','2026-10-26T03:00:00Z')
            before=(root/'2026-10-19.json').read_bytes()
            with self.assertRaises(ValueError):publish(changed,root)
            self.assertEqual((root/'2026-10-19.json').read_bytes(),before)

    def test_corrupt_missing_duplicate_or_unsafe_archive_is_not_repaired_silently(self):
        for change in ('corrupt','missing','duplicate','unsafe','order'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);index=publish(report(),root)
                if change=='corrupt':(root/'2026-10-19.json').write_text('{}')
                if change=='missing':(root/'2026-10-19.json').unlink()
                if change=='duplicate':index['reports'].append(index['reports'][0])
                if change=='unsafe':index['reports'][0]['path']='../secrets.json'
                if change=='order':
                    publish(report(start='2026-10-12'),root);index=load(root/'index.json');index['reports'].reverse()
                (root/'index.json').write_bytes(encoded(index))
                with self.assertRaises((ValueError,FileNotFoundError)):archive_index(root)

    def test_orphans_locks_and_existing_temporary_files_preserved(self):
        for name in ('2026-10-19.json','.weekly.lock','.index.tmp'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);(root/name).write_text('existing')
                with self.assertRaises(FileExistsError):publish(report(),root)
                self.assertEqual((root/name).read_text(),'existing')
                self.assertFalse((root/'index.json').exists())

    def test_cli_requires_evidence_and_never_relabels_demo_as_activity(self):
        with tempfile.TemporaryDirectory() as temp:
            args=[sys.executable,'-m','strategy_discovery.weekly','--ledger','strategy_discovery/samples/empty_weekly_ledger.json','--week-start','2026-10-19','--archive',temp]
            completed=subprocess.run(args,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(completed.returncode,0,completed.stderr)
            r=load(Path(temp)/'2026-10-19.json')
            self.assertEqual(r['counts']['sources_reviewed'],0)
            self.assertEqual(r['activity_state'],'EMPTY')

    def test_dashboard_preserves_old_panels_and_scopes_local_data(self):
        html=(ROOT/'docs/index.html').read_text()
        for identifier in ('portfolio-overview','weekly-report','performance-reports','trade-history','strategy-discovery','discovery-archive'):
            self.assertEqual(html.count('id="'+identifier+'"'),1)
        for script in ('dashboard.js','performance_reports.js','research_extensions.js','strategy_discovery.js'):
            self.assertEqual(html.count('src="'+script+'"'),1)
        self.assertIn('href="#strategy-discovery"',html)
        js=(ROOT/'docs/strategy_discovery.js').read_text()
        self.assertNotIn('demo_report.json',js)
        self.assertNotIn('raw.githubusercontent.com',js)
        self.assertNotIn('innerHTML',js)
        self.assertIn("strategy-discovery/index.json",js)


if __name__=='__main__':unittest.main()
