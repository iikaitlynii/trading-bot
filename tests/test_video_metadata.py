"""Permission and review boundaries; fixture IDs are fictional, no network."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import unittest

from strategy_discovery.metadata import normalize, candidate_for, validate_record
from strategy_discovery.lab import approve, configuration, digest, extract, load
from strategy_discovery.evaluate import evaluate, synthetic_prices


def envelope():
    return dict(provider='youtube-data-api-v3', interface='search.list', retrieved_at='2026-10-01T10:00:00Z',
                permission=dict(basis='authorized API response', reference='TEST FIXTURE — no real rights claim', scope='metadata', status='active'),
                response=dict(items=[dict(id=dict(videoId='DemoSMA0001'), snippet=dict(title='Daily SMA strategy', channelId='fixture-channel', publishedAt='2026-01-01T00:00:00Z', description='Educational metadata fixture'))]))


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.export = envelope()
        self.q = normalize(self.export, 'sma')
        self.record = self.q['records'][0]
        self.source = load(Path('strategy_discovery/samples/transcripts.json'))[0]
        self.source.update(video_url=self.record['video_url'], retrieved_at='2026-10-02T10:00:00Z')
        self.source['permission'] = dict(basis='creator permission', reference='TEST ONLY written consent fixture', status='active')

    def test_provenance_and_no_rule_invention(self):
        self.assertEqual(self.q['envelope'], self.export)
        self.assertEqual(self.record['original'], self.export['response']['items'][0])
        self.assertEqual(self.record['response_sha256'], digest(self.export['response']))
        self.assertEqual(self.q['matches'], ['DemoSMA0001'])
        self.assertEqual(self.q['candidates'], [])
        self.assertEqual(self.record['state'], 'needs_transcript_permission')
        self.assertEqual(normalize(self.export, 'no-match')['matches'], [])
        self.export['response']['nextPageToken'] = 'next'
        self.assertIn('partial', normalize(self.export, 'sma')['pagination'])

    def test_unsupported_and_revoked_visibly_blocked(self):
        for mutate in [lambda e:e.update(provider='scraped-transcript'),
                       lambda e:e['permission'].update(status='revoked'),
                       lambda e:e['permission'].update(reference=''),
                       lambda e:e.update(interface='captions.download'),
                       lambda e:e['response']['items'][0].update(status={'privacyStatus':'private'}),
                       lambda e:e['response']['items'][0].update(snippet={})]:
            e=deepcopy(self.export);mutate(e);q=normalize(e,'sma')
            self.assertEqual(q['records'][0]['state'],'blocked')
            with self.assertRaises(ValueError):candidate_for(q['records'][0],e,self.source)

    def test_invalid_duplicate_future_or_unavailable(self):
        for mutate in [lambda e:e['response']['items'].append(e['response']['items'][0]),
                       lambda e:e.update(retrieved_at='2999-01-01T00:00:00Z'),
                       lambda e:e.update(retrieved_at='2026-10-01T10:00:00'),
                       lambda e:e.update(response={'error':{'code':403}}),
                       lambda e:e['response']['items'][0].update(id={'channelId':'channel'})]:
            e=deepcopy(self.export);mutate(e)
            with self.assertRaises(ValueError):normalize(e,'sma')
        self.export['response']['items']=[]
        self.assertEqual(normalize(self.export,'sma')['records'],[])

    def test_human_review_bridge_and_historical_block(self):
        c=candidate_for(self.record,self.export,self.source)
        self.assertEqual(c['status'],'needs_human_review')
        self.assertFalse(c['source']['synthetic'])
        self.assertFalse(c['uncertainties'])
        with self.assertRaises(ValueError):approve(c,{})
        review=dict(decision='approve',candidate_sha256=digest(c),reviewer='TEST attestation',reviewed_at='2026-10-03T00:00:00Z',rationale='Fixture only')
        for timestamp in ['2026-01-01T00:00:00Z','2999-01-01T00:00:00Z','2026-10-03T00:00:00']:
            with self.assertRaises(ValueError):approve(c,dict(review,reviewed_at=timestamp))
        spec=approve(c,review);self.assertTrue(configuration(spec))
        with self.assertRaisesRegex(ValueError,'synthetic transcript'):evaluate(spec,synthetic_prices())
        changed=deepcopy(spec);changed['candidate']['source']['discovery_metadata']['envelope']['permission']['status']='withdrawn'
        with self.assertRaises(ValueError):configuration(changed)

    def test_transcript_rights_and_identity_not_metadata_rights(self):
        for mutate in [lambda s:s['permission'].update(status='withdrawn'),
                       lambda s:s['permission'].update(basis='public captions'),
                       lambda s:s.update(video_url='https://www.youtube.com/watch?v=OtherVid001'),
                       lambda s:s.update(retrieved_at='2026-01-01T00:00:00Z')]:
            source=deepcopy(self.source);mutate(source)
            with self.assertRaises(ValueError):candidate_for(self.record,self.export,source)
        changed=deepcopy(self.record);changed['title']='tampered'
        with self.assertRaises(ValueError):validate_record(changed,self.export)
        source=deepcopy(self.source);source['segments']=source['segments'][:1]
        self.assertTrue(candidate_for(self.record,self.export,source)['uncertainties'])
        source['permission']['status']='revoked'
        with self.assertRaises(ValueError):extract(source)

    def test_permissioned_export(self):
        self.export.update(provider='permissioned-metadata-export',interface='licensed export')
        self.export['permission']['basis']='licensed metadata export'
        self.assertEqual(normalize(self.export,'sma')['records'][0]['state'],'needs_transcript_permission')


if __name__ == '__main__':unittest.main()
