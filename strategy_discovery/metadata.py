"""Permission-aware metadata-export discovery; no network, captions or execution.

Consume an official YouTube Data API response obtained by an authorized operator,
or a documented permissioned export. Public visibility never grants transcript rights.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import re
from pathlib import Path

from .lab import digest, encoded, extract, load

PROVIDERS = {'youtube-data-api-v3', 'permissioned-metadata-export'}
BASES = {'authorized API response', 'licensed metadata export', 'creator permission'}
VIDEO = re.compile(r'[A-Za-z0-9_-]{11}')


def instant(value):
    if not isinstance(value, str):
        raise ValueError('timezone-aware timestamp required')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('timezone-aware timestamp required')
    return result


def normalize(envelope, query, now=None):
    """Preserve the entire response and permission record, hash-bound per source.

    Export declarations are auditable assertions, not authenticated permission.
    Unknown providers/rights remain blocked, never routed to a scraper.
    """
    now = now or datetime.now(timezone.utc)
    if not isinstance(query, str) or not query.strip():
        raise ValueError('discovery query required')
    acquired = instant(envelope['retrieved_at'])
    if acquired > now:
        raise ValueError('future retrieval timestamp')
    response = envelope['response']
    if not isinstance(response, dict) or 'error' in response or not isinstance(response.get('items'), list):
        raise ValueError('response.items required; API errors are not empty success')
    permission = envelope.get('permission', {})
    provider = envelope.get('provider')
    allowed = (provider in PROVIDERS and permission.get('basis') in BASES and
               isinstance(permission.get('reference'), str) and bool(permission['reference'].strip()) and
               permission.get('scope') == 'metadata' and permission.get('status') == 'active')
    if provider == 'youtube-data-api-v3':
        allowed = allowed and envelope.get('interface') in {'search.list', 'videos.list'} and permission.get('basis') == 'authorized API response'
    records, seen = [], set()
    for item in response['items']:
        key = item.get('id')
        video_id = key.get('videoId') if isinstance(key, dict) else key
        if not isinstance(video_id, str) or not VIDEO.fullmatch(video_id):
            raise ValueError('video metadata requires canonical video ID; channels/playlists unsupported')
        if video_id in seen:
            raise ValueError('duplicate video ID; reconcile explicitly before import')
        seen.add(video_id)
        snippet = item.get('snippet', {})
        title, channel = snippet.get('title'), snippet.get('channelId')
        available = bool(isinstance(title, str) and title.strip() and isinstance(channel, str) and channel.strip())
        available = available and item.get('status', {}).get('privacyStatus', 'public') == 'public'
        if snippet.get('publishedAt') is not None:
            instant(snippet['publishedAt'])
        records.append(dict(video_id=video_id, video_url='https://www.youtube.com/watch?v='+video_id,
                            title=title if isinstance(title, str) else '(metadata unavailable)', channel_id=channel,
                            published_at=snippet.get('publishedAt'), retrieved_at=envelope['retrieved_at'],
                            provider=provider, interface=envelope.get('interface'), query=query,
                            permission=deepcopy(permission), original=deepcopy(item),
                            response_sha256=digest(response), envelope_sha256=digest(envelope),
                            state='needs_transcript_permission' if allowed and available else 'blocked',
                            reason='Metadata only; no strategy rules inferred' if allowed and available else 'Unsupported provider, unavailable/private source or inactive/undocumented metadata permission'))
    tokens = query.casefold().split()
    matches = [r for r in records if all(t in (r['title']+' '+r['original'].get('snippet', {}).get('description', '')).casefold() for t in tokens)]
    return dict(schema_version=1, simulation_only=True, evidence='public metadata / strategy unvalidated',
                envelope=deepcopy(envelope), query=query, records=records, matches=[r['video_id'] for r in matches],
                pagination='partial — next page not imported' if response.get('nextPageToken') else 'end of supplied response',
                live_discovery='BLOCKED — no configured authorized API client; export import only',
                candidates=[], note='No transcript retrieval or inferred rules. Permission assertions require human verification; public metadata is not historical performance evidence.')


def validate_record(record, envelope):
    fresh = normalize(envelope, record['query'])
    expected = next((r for r in fresh['records'] if r['video_id'] == record['video_id']), None)
    if record != expected or record['state'] != 'needs_transcript_permission':
        raise ValueError('changed, blocked or unavailable metadata source')


def candidate_for(record, envelope, transcript):
    validate_record(record, envelope)
    source = deepcopy(transcript)
    if source.get('video_url') != record['video_url']:
        raise ValueError('metadata/transcript video mismatch')
    permission = source.get('permission', {})
    if permission.get('status') != 'active' or permission.get('basis') not in {'creator permission', 'owned captions'}:
        raise ValueError('active independent transcript permission required')
    if instant(source['retrieved_at']) < instant(record['retrieved_at']):
        raise ValueError('transcript acquisition predates metadata evidence')
    source['synthetic'] = False
    source['discovery_metadata'] = dict(record=deepcopy(record), envelope=deepcopy(envelope))
    return extract(source)  # Existing controlled parser and unchanged human review gate.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('export', type=Path)
    parser.add_argument('--query', required=True)
    parser.add_argument('--transcripts', type=Path, help='Optional authorized local JSON transcript array')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = normalize(load(args.export), args.query)
    if args.transcripts:
        for source in load(args.transcripts):
            record = next((r for r in manifest['records'] if r['video_url'] == source.get('video_url')), None)
            if record is None:
                raise ValueError('transcript has no imported metadata')
            manifest['candidates'].append(candidate_for(record, manifest['envelope'], source))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded(manifest))
    print('Saved metadata discovery queue; human review required:', args.output)


if __name__ == '__main__':
    main()
